$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Cannot create Python virtual environment.' }
}
& .\.venv\Scripts\python.exe -m pip --isolated install --index-url https://pypi.org/simple -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed.' }
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --console --name WiFiScannerConsoleRSSI --exclude-module tkinter --exclude-module numpy --exclude-module scipy --exclude-module pandas wifi_scanner_console.py
if ($LASTEXITCODE -ne 0) { throw 'Console executable build failed.' }
Write-Host "Ready: $PSScriptRoot\dist\WiFiScannerConsoleRSSI.exe"
