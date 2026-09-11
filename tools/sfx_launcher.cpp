#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdint>
#include <fstream>
#include <string>
#include <vector>

static const char FOOTER_MAGIC[8] = {'F','B','P','0','7','2','2','!'};

static std::wstring exe_path() {
    wchar_t buf[32768] = {};
    DWORD n = GetModuleFileNameW(nullptr, buf, static_cast<DWORD>(std::size(buf)));
    return std::wstring(buf, n);
}

static std::wstring env(const wchar_t* name) {
    DWORD n = GetEnvironmentVariableW(name, nullptr, 0);
    if (!n) return L"";
    std::vector<wchar_t> b(n + 2);
    GetEnvironmentVariableW(name, b.data(), static_cast<DWORD>(b.size()));
    return std::wstring(b.data());
}

static std::wstring join(const std::wstring& a, const std::wstring& b) {
    if (a.empty()) return b;
    wchar_t c = a.back();
    return (c == L'\\' || c == L'/') ? a + b : a + L"\\" + b;
}

static bool exists(const std::wstring& p) {
    DWORD a = GetFileAttributesW(p.c_str());
    return a != INVALID_FILE_ATTRIBUTES && !(a & FILE_ATTRIBUTE_DIRECTORY);
}

static void error_box(const std::wstring& s) {
    MessageBoxW(nullptr, s.c_str(), L"FlyBrain Pong V0.7.2", MB_OK | MB_ICONERROR | MB_SETFOREGROUND);
}

static std::wstring ps_quote(const std::wstring& s) {
    std::wstring out = L"'";
    for (wchar_t c : s) {
        if (c == L'\'') out += L"''";
        else out.push_back(c);
    }
    out += L"'";
    return out;
}

static bool run_and_wait(const std::wstring& exe, const std::wstring& args, DWORD flags = CREATE_NO_WINDOW) {
    std::wstring cmd = L"\"" + exe + L"\" " + args;
    std::vector<wchar_t> buf(cmd.begin(), cmd.end());
    buf.push_back(L'\0');
    STARTUPINFOW si{}; si.cb = sizeof(si);
    PROCESS_INFORMATION pi{};
    BOOL ok = CreateProcessW(exe.c_str(), buf.data(), nullptr, nullptr, FALSE, flags, nullptr, nullptr, &si, &pi);
    if (!ok) return false;
    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD code = 1;
    GetExitCodeProcess(pi.hProcess, &code);
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return code == 0;
}

static bool extract_payload(const std::wstring& self, const std::wstring& dest) {
    std::ifstream f(self, std::ios::binary);
    if (!f) return false;
    f.seekg(0, std::ios::end);
    std::streamoff total = f.tellg();
    if (total < 24) return false;
    f.seekg(total - 24);
    char magic[8] = {};
    uint64_t offset = 0, length = 0;
    f.read(magic, 8);
    f.read(reinterpret_cast<char*>(&offset), 8);
    f.read(reinterpret_cast<char*>(&length), 8);
    if (!f || memcmp(magic, FOOTER_MAGIC, 8) != 0) return false;
    if (offset + length + 24ULL != static_cast<uint64_t>(total)) return false;

    std::wstring temp = join(env(L"TEMP"), L"FlyBrainPong_v0722_payload_" + std::to_wstring(GetCurrentProcessId()) + L".zip");
    std::ofstream out(temp, std::ios::binary | std::ios::trunc);
    if (!out) return false;
    f.seekg(static_cast<std::streamoff>(offset));
    const size_t CHUNK = 4 * 1024 * 1024;
    std::vector<char> buffer(CHUNK);
    uint64_t left = length;
    while (left) {
        size_t want = static_cast<size_t>(left > CHUNK ? CHUNK : left);
        f.read(buffer.data(), static_cast<std::streamsize>(want));
        if (static_cast<size_t>(f.gcount()) != want) return false;
        out.write(buffer.data(), static_cast<std::streamsize>(want));
        if (!out) return false;
        left -= want;
    }
    out.close();

    wchar_t sysdir[MAX_PATH] = {};
    GetSystemDirectoryW(sysdir, MAX_PATH);
    std::wstring powershell = join(sysdir, L"WindowsPowerShell\\v1.0\\powershell.exe");
    if (!exists(powershell)) powershell = L"powershell.exe";

    std::wstring command =
        L"-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command \"" 
        L"$ErrorActionPreference='Stop'; "
        L"$d=" + ps_quote(dest) + L"; $z=" + ps_quote(temp) + L"; "
        L"if(Test-Path -LiteralPath $d){Remove-Item -LiteralPath $d -Recurse -Force}; "
        L"New-Item -ItemType Directory -Force -Path $d | Out-Null; "
        L"Expand-Archive -LiteralPath $z -DestinationPath $d -Force; "
        L"Remove-Item -LiteralPath $z -Force; "
        L"Set-Content -LiteralPath (Join-Path $d '.payload_ok') -Value 'FlyBrain Pong V0.7.2' -Encoding ASCII\"";

    bool ok = run_and_wait(powershell, command);
    if (!ok) DeleteFileW(temp.c_str());
    return ok;
}

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int) {
    const std::wstring self = exe_path();
    std::wstring local = env(L"LOCALAPPDATA");
    if (local.empty()) local = env(L"APPDATA");
    if (local.empty()) {
        error_box(L"找不到 Windows 使用者資料目錄。");
        return 2;
    }

    const std::wstring dest = join(join(local, L"FlyBrainPong"), L"0.7.2");
    const std::wstring marker = join(dest, L".payload_ok");
    const std::wstring app = join(join(dest, L"FlyBrainPongApp"), L"FlyBrainPongApp.exe");

    if (!exists(marker) || !exists(app)) {
        MessageBoxW(nullptr,
            L"FlyBrain Pong 第一次啟動會準備完整 MaleCNS 遊戲環境。\n\n只需要進行一次，完成後以後會直接進入遊戲。",
            L"FlyBrain Pong V0.7.2", MB_OK | MB_ICONINFORMATION | MB_SETFOREGROUND);
        if (!extract_payload(self, dest)) {
            error_box(L"第一次啟動解壓失敗。\n\n請確認磁碟空間足夠，或暫時允許 PowerShell 執行後再試一次。");
            return 3;
        }
    }

    if (!exists(app)) {
        error_box(L"遊戲檔案不完整，找不到 FlyBrainPongApp.exe。請重新下載。");
        return 4;
    }

    std::wstring cmd = L"\"" + app + L"\"";
    std::vector<wchar_t> mutable_cmd(cmd.begin(), cmd.end());
    mutable_cmd.push_back(L'\0');
    STARTUPINFOW si{}; si.cb = sizeof(si);
    PROCESS_INFORMATION pi{};
    BOOL ok = CreateProcessW(app.c_str(), mutable_cmd.data(), nullptr, nullptr, FALSE, 0, nullptr, join(dest, L"FlyBrainPongApp").c_str(), &si, &pi);
    if (!ok) {
        error_box(L"遊戲啟動失敗。Windows 錯誤碼：" + std::to_wstring(GetLastError()));
        return 5;
    }
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return 0;
}
