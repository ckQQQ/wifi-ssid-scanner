$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Cannot create Python virtual environment.' }
}
& .\.venv\Scripts\python.exe -m pip --isolated install --index-url https://pypi.org/simple -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed.' }
$buildArguments = @('-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--windowed', '--name', 'WiFiScannerRSSI', '--exclude-module', 'numpy', '--exclude-module', 'scipy', '--exclude-module', 'pandas')
$pythonBase = & .\.venv\Scripts\python.exe -c "import sys; print(sys.base_prefix)"
# Conda may otherwise resolve Tcl/Tk DLLs from another environment on PATH.
$condaRuntime = Join-Path $pythonBase 'Library\bin'
foreach ($dllName in @('tcl86t.dll', 'tk86t.dll')) {
    $dllPath = Join-Path $condaRuntime $dllName
    if (Test-Path -LiteralPath $dllPath) {
        $buildArguments += @('--add-binary', "$dllPath;.")
    }
}
$buildArguments += 'wifi_scanner.py'
& .\.venv\Scripts\python.exe @buildArguments
if ($LASTEXITCODE -ne 0) { throw 'Executable build failed.' }
Write-Host "Ready: $PSScriptRoot\dist\WiFiScannerRSSI.exe"
