# Wi-Fi SSID 搜尋器

Windows 10／11 的 Python 程式，搜尋附近 Wi-Fi 名稱（SSID）。提供視窗版與 Console 版，均顯示訊號品質、RSSI、安全性及連線狀態。此專案是 Windows 桌面程式，GitHub Pages 無法執行；原始碼放在 repository，編譯好的執行檔放在 [Releases](https://github.com/ckQQQ/wifi-ssid-scanner/releases/latest)。

## 下載與使用

從最新版 Release 下載適用於 64 位元 Windows 的 `WiFiScannerRSSI.exe`（視窗版）或 `WiFiScannerConsoleRSSI.exe`（Console 版），不必安裝 Python。

Release 也附有 `SHA256SUMS.txt`。下載後可在 PowerShell 計算檔案雜湊，與清單中的 SHA-256 比對，確認下載檔案完整：

```powershell
Get-FileHash .\WiFiScannerRSSI.exe -Algorithm SHA256
Get-FileHash .\WiFiScannerConsoleRSSI.exe -Algorithm SHA256
```

視窗版開啟後會自動掃描。上方輸入框可依 SSID 篩選；「重新掃描」更新清單。選取項目後可複製 SSID，並可開啟 Windows Wi-Fi／定位設定。

Console 版直接雙擊會顯示互動選單：`1` 重新掃描、`2` 搜尋目前清單、`3` 顯示全部、`0` 離開。也能在 PowerShell 掃描一次或指定搜尋文字：

```powershell
.\WiFiScannerConsoleRSSI.exe --once
.\WiFiScannerConsoleRSSI.exe --search "Example-WiFi"
.\WiFiScannerConsoleRSSI.exe --interactive --search "Example-WiFi"
```

「訊號品質」是 Windows 回報的 0–100%，不是 RSSI。RSSI 直接取自網卡回報的 `lRssi`，單位為 dBm；例如 `-40 dBm` 比 `-70 dBm` 強，並非由百分比換算。[Microsoft WLAN_BSS_ENTRY 說明](https://learn.microsoft.com/en-us/windows/win32/api/wlanapi/ns-wlanapi-wlan_bss_entry)。若相同 SSID 有多個基地台，顯示其中最強的 RSSI，可能與目前連線的基地台不同；讀取失敗時顯示「—」。隱藏的網路不會廣播可搜尋的名稱。

需要有啟用的 Wi-Fi 網卡。若 Windows 回傳存取拒絕（錯誤 5），開啟 Windows 定位設定，允許定位與桌面應用程式存取後重新掃描。[Microsoft Wi-Fi 存取與定位說明](https://learn.microsoft.com/en-us/windows/win32/nativewifi/wi-fi-access-location-changes)。程式只讀取本機 Wi-Fi 掃描結果，不會自動連線或上傳 SSID。

## 執行原始碼

需要 Windows、Python 3.10 以上；視窗版還需 Python 包含 Tkinter。`wifi_native.py` 是兩版共用的 Windows Wi-Fi API 模組。

```powershell
python wifi_scanner.py
python wifi_scanner_console.py
python wifi_scanner_console.py --search "Example-WiFi"
```

## 重新建置 EXE

在 repository 根目錄的 PowerShell 執行：

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
powershell -ExecutionPolicy Bypass -File .\build_console.ps1
```

腳本在 `.venv` 安裝 `requirements-build.txt` 中固定版本的 PyInstaller，再輸出 `dist\WiFiScannerRSSI.exe` 及 `dist\WiFiScannerConsoleRSSI.exe`。首次建置需要下載套件。Conda Python 的視窗版打包腳本會一併收錄對應的 Tcl/Tk DLL。

## 驗證方法

先在 Windows 上執行自動化測試；九項測試涵蓋搜尋、互動選單、RSSI 數值與 Windows BSS 結構：

```powershell
python -m unittest test_console.py test_wifi_native.py
New-Item -ItemType Directory -Force verification | Out-Null
python wifi_scanner.py --smoke-test verification\gui.json
Get-Content verification\gui.json
```

`gui.json` 應顯示 `"ok": true` 並包含 `"rssi_column"`。建置後可驗證兩個 EXE；診斷 JSON 只記錄網路數量與 RSSI 筆數，不包含 SSID：

```powershell
.\dist\WiFiScannerRSSI.exe --smoke-test "$PWD\verification\gui-exe.json"
.\dist\WiFiScannerRSSI.exe --diagnose "$PWD\verification\gui-scan.json"
.\dist\WiFiScannerConsoleRSSI.exe --diagnose "$PWD\verification\console-scan.json"
Get-Content verification\gui-exe.json,verification\gui-scan.json,verification\console-scan.json
```

在有 Wi-Fi 網卡且已允許存取的電腦上，兩個掃描 JSON 應顯示 `"ok": true`；有可見網路時，`network_count` 與 `rssi_count` 應大於零。網路數量會隨環境改變。也可執行 `python check_console_exe.py`，驗證 EXE 的單次掃描、真實 SSID 搜尋與互動選單；此腳本不保存或列印 SSID。

## 發布方式

`.gitignore` 排除 `dist/`、虛擬環境、建置產物、診斷結果與常見憑證檔。提交原始碼與測試到 GitHub repository；兩個 EXE 作為 GitHub Release 附件提供下載。要更新版本時，先執行上述測試與建置，再提交原始碼、建立新版本標籤並上傳對應 EXE。勿將 `.env`、金鑰、憑證或本機掃描結果加入版本控制。

若要確認公開 repository 的內容，可複製其網址執行 `git clone https://github.com/ckQQQ/wifi-ssid-scanner.git`，再執行 `git -C wifi-ssid-scanner ls-files`；清單應包含本頁所列的原始碼、測試與腳本，不應包含 `dist/`、`.venv/` 或 `verification/`。

## 驗證紀錄

- 2026-09-29：視窗版及 Console 版完成；RSSI 結構、搜尋與介面測試通過。在當時的桌面環境中，兩版皆成功取得附近網路的 RSSI。即時網路數量不是固定測試基準。
