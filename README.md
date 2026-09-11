# 🪰 FlyBrain Pong

以 **Janelia MaleCNS v1.0 果蠅中樞神經連線組（connectome）**作為固定神經連線／動態骨架的 Pong + Roguelike 實驗遊戲。

> **重要科學註記**：這不是「真實果蠅理解 Pong」或完整生物腦模擬。遊戲使用 MaleCNS connectome 作為固定 wiring / dynamics backbone，並在其外加入工程化感覺介面、運動讀出、獎勵學習與選卡策略層。

## 最新版本

**V0.7.2**

- Windows 單檔啟動架構
- MaleCNS runtime：165,122 個 traced neurons
- 25,563,197 條 neuron-to-neuron edges
- CUDA / PyTorch edge-scatter（可用時）
- CPU / SciPy fallback
- Classic Pong / Roguelike Pong
- 主動進攻、極限救球、比分差 Reward
- 每總分 10 分進入雙方三選一卡牌 Draft
- 流派、Combo、Counter、Splash、Pivot
- 果蠅專屬 Neural / Control 卡，玩家完全不會看到
- Motor / Strategy / Aggressive 三種訓練
- 遊戲內 F10「設定 / 訓練」可直接自由輸入訓練輪數，不必操作 BAT
- 可匯入舊版訓練成果與 checkpoint

## 遊戲內訓練

按 **F10** 或點右下角 **設定 / 訓練**：

- `Motor`：實際球拍控制、追球、高速／反彈應對、進攻落點
- `Strategy`：選卡、流派、Counter、Pivot、對手構築判斷
- `Aggressive`：遠距離／極限救球與 never-give-up 行為

輪數可以自由輸入任意正整數，例如：

```text
500
20000
50000
100000
250000
```

支援「新增 N 輪」與「訓練到累積 N 輪」。

## 已驗證項目

- MaleCNS neural path：UP / DOWN signal PASS
- 25,563,197 edge runtime PASS
- 高速球、多次反彈幾何預測 PASS
- 5,000 次 shared-rarity 公平性檢查 PASS
- 玩家 Neural 卡洩漏：0
- Counter / Pivot policy 測試 PASS
- Windows x64 PE launcher build PASS

## 資料來源與 Attribution

MaleCNS dataset：Janelia Research Campus

- 官方網站：https://male-cns.janelia.org/
- Download：https://male-cns.janelia.org/download/
- Dataset：MaleCNS v1.0 adult male *Drosophila* CNS connectome
- Dataset license：CC-BY

本專案使用由官方 connectome / annotations 資料衍生的 runtime 表示。遊戲介面、神經動態近似、CUDA adapter、reward learning 與 card policy 為本專案工程層，不應與實驗量測的完整果蠅神經生理等同。

## 執行環境

最低需要：

- Windows 10 / 11 x64
- Python 3
- NumPy / SciPy

建議：

- NVIDIA GPU
- PyTorch CUDA

沒有 CUDA 時仍可使用 CPU / SciPy backend。

## SHA-256

V0.7.2 Complete EXE：

```text
fa8b41aaa6af23c9098257f844f1ce6ba2f51407674b196f1416c422c586663f
```

## Repository 內容

這個 repository 公開保存 FlyBrain Pong 的遊戲程式碼、研究／訓練邏輯、資料 attribution 與 Windows launcher。大型 MaleCNS 衍生 runtime 不會以未說明來源的方式冒充原始生物資料。

## Disclaimer

這是一個遊戲／研究型專案，不宣稱已重建完整果蠅大腦，也不宣稱果蠅具有人類式理解、意識或 Pong 概念。
