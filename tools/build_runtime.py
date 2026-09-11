from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pyarrow.feather as feather

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "build_data"
RUNTIME = ROOT / "runtime"

ANNOT = DATA / "body-annotations-male-cns-v1.0-minconf-0.5.feather"
CONNECTOME = DATA / "connectome-weights-male-cns-v1.0-minconf-0.5.feather"

EXPECTED_NEURONS = 165_122
EXPECTED_EDGES = 25_563_197
EXPECTED_WEIGHT_SUM = 124_025_046
EXPECTED_MAX_WEIGHT = 2_591


def _pick_column(names: list[str], candidates: tuple[str, ...], label: str) -> str:
    lower = {name.lower(): name for name in names}
    for cand in candidates:
        if cand.lower() in lower:
            return lower[cand.lower()]
    raise RuntimeError(f"Could not find {label} column. Available columns: {names}")


def load_traced_ids() -> np.ndarray:
    schema = feather.read_table(ANNOT, memory_map=True).schema
    names = schema.names
    body_col = _pick_column(names, ("bodyid", "bodyId", "body", "id"), "body ID")
    status_col = _pick_column(names, ("status", "statusLabel", "status_label"), "status")
    print(f"Annotation columns: body={body_col!r} status={status_col!r}", flush=True)

    table = feather.read_table(ANNOT, columns=[body_col, status_col], memory_map=True)
    body = table.column(body_col).to_numpy(zero_copy_only=False)
    status = table.column(status_col).to_pylist()
    mask = np.fromiter((str(x).strip().lower() == "traced" for x in status), dtype=bool, count=len(status))
    node_ids = np.sort(np.asarray(body[mask], dtype=np.int64))
    if node_ids.size != EXPECTED_NEURONS:
        from collections import Counter
        counts = Counter(str(x) for x in status)
        raise RuntimeError(
            f"Unexpected traced neuron count: {node_ids.size:,} != {EXPECTED_NEURONS:,}. "
            f"Status counts: {counts.most_common(12)}"
        )
    if np.unique(node_ids).size != node_ids.size:
        raise RuntimeError("Duplicate traced body IDs detected")
    return node_ids


def get_index(node_ids: np.ndarray, bodies: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    pos = np.searchsorted(node_ids, bodies)
    valid = pos < node_ids.size
    safe = np.minimum(pos, node_ids.size - 1)
    valid &= node_ids[safe] == bodies
    return pos.astype(np.int32, copy=False), valid


def build_edges(node_ids: np.ndarray):
    print("Reading connectome Feather columns (body_pre, body_post, weight)...", flush=True)
    table = feather.read_table(
        CONNECTOME,
        columns=["body_pre", "body_post", "weight"],
        memory_map=True,
        use_threads=True,
    )
    names = table.schema.names
    if names != ["body_pre", "body_post", "weight"]:
        raise RuntimeError(f"Unexpected connectome schema: {names}")

    batches = table.to_batches(max_chunksize=1_000_000)
    pres: list[np.ndarray] = []
    posts: list[np.ndarray] = []
    weights: list[np.ndarray] = []
    raw_rows = 0
    kept = 0

    for batch_i, batch in enumerate(batches, start=1):
        pre_body = np.asarray(batch.column(0).to_numpy(zero_copy_only=False), dtype=np.int64)
        post_body = np.asarray(batch.column(1).to_numpy(zero_copy_only=False), dtype=np.int64)
        w = np.asarray(batch.column(2).to_numpy(zero_copy_only=False))
        raw_rows += len(w)

        pre_idx, vpre = get_index(node_ids, pre_body)
        post_idx, vpost = get_index(node_ids, post_body)
        valid = vpre & vpost
        if np.any(valid):
            p = pre_idx[valid].astype(np.int32, copy=False)
            q = post_idx[valid].astype(np.int32, copy=False)
            ww = w[valid].astype(np.uint16, copy=False)
            pres.append(p.copy())
            posts.append(q.copy())
            weights.append(ww.copy())
            kept += len(ww)
        if batch_i == 1 or batch_i % 10 == 0 or batch_i == len(batches):
            print(f"batch {batch_i}/{len(batches)}: raw={raw_rows:,} kept={kept:,}", flush=True)

    del table, batches

    pre = np.concatenate(pres)
    post = np.concatenate(posts)
    weight = np.concatenate(weights)
    del pres, posts, weights

    if len(weight) != EXPECTED_EDGES:
        raise RuntimeError(f"Unexpected retained edge count: {len(weight):,} != {EXPECTED_EDGES:,}")
    total_weight = int(weight.astype(np.uint64).sum())
    if total_weight != EXPECTED_WEIGHT_SUM:
        raise RuntimeError(f"Unexpected retained weight sum: {total_weight:,} != {EXPECTED_WEIGHT_SUM:,}")
    max_weight = int(weight.max())
    if max_weight != EXPECTED_MAX_WEIGHT:
        raise RuntimeError(f"Unexpected max weight: {max_weight:,} != {EXPECTED_MAX_WEIGHT:,}")

    print("Sorting retained graph into CSR receiver rows...", flush=True)
    order = np.argsort(post, kind="stable")
    post_sorted = post[order]
    col_idx = pre[order].astype(np.int32, copy=False)
    weight_sorted = weight[order].astype(np.uint16, copy=False)

    counts = np.bincount(post_sorted, minlength=node_ids.size).astype(np.int64)
    row_ptr = np.empty(node_ids.size + 1, dtype=np.int64)
    row_ptr[0] = 0
    np.cumsum(counts, out=row_ptr[1:])
    row_weight_sum = np.bincount(
        post_sorted,
        weights=weight_sorted.astype(np.float64),
        minlength=node_ids.size,
    ).astype(np.float32)
    # BrainEngine normalizes every receiver row by this value. Neurons with no
    # retained incoming edges must use a neutral divisor of 1 rather than 0,
    # otherwise 0/0 propagates NaNs through the recurrent dynamics.
    zero_rows = int(np.count_nonzero(row_weight_sum == 0))
    row_weight_sum[row_weight_sum == 0] = 1.0
    print(f"CSR rows with no retained incoming edges: {zero_rows:,} (divisor set to 1)", flush=True)
    return col_idx, weight_sorted, row_ptr, row_weight_sum, raw_rows


def main() -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    node_ids = load_traced_ids()
    col_idx, weight, row_ptr, row_weight_sum, raw_rows = build_edges(node_ids)

    np.save(RUNTIME / "node_ids.npy", node_ids.astype(np.int64, copy=False))
    np.save(RUNTIME / "col_idx.npy", col_idx)
    np.save(RUNTIME / "weight.npy", weight)
    np.save(RUNTIME / "row_ptr.npy", row_ptr)
    np.save(RUNTIME / "row_weight_sum.npy", row_weight_sum)

    meta = {
        "dataset": "Janelia MaleCNS v1.0",
        "filter": "status == Traced; both endpoints retained",
        "neurons": int(node_ids.size),
        "edges": int(col_idx.size),
        "raw_edge_rows": int(raw_rows),
        "retained_weight": int(weight.astype(np.uint64).sum()),
        "max_weight": int(weight.max()),
        "csr_semantics": "row=receiver(post), col=sender(pre)",
        "zero_incoming_row_divisor": 1.0,
    }
    (RUNTIME / "runtime_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (RUNTIME / "version_v0.7.json").write_text(json.dumps({"game":"FlyBrain Pong","version":"0.7.2"}, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2), flush=True)


if __name__ == "__main__":
    main()
