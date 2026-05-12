$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "Installing required Python packages..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

Write-Host "Cleaning old build outputs..."
if (Test-Path ".\build") {
    Remove-Item ".\build" -Recurse -Force
}

Write-Host "Building one-file Windows exe..."
python -m PyInstaller --clean --noconfirm ".\多功能圖片影音製作器V5.spec"

Write-Host ""
Write-Host "Build completed:"
Write-Host (Join-Path $ProjectRoot "dist\多功能圖片影音製作器V5.2.exe")
