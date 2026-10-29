# Dirt Gear Windows build — run from the Dirt-Gear folder in PowerShell:
#   powershell -ExecutionPolicy Bypass -File build\build.ps1
# Produces release\Dirt Gear v1.0 Setup.exe (single friend-facing installer).
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Version = (Get-Content VERSION.txt).Trim()

if (-not (Test-Path .venv)) { py -3.12 -m venv .venv }
$Py = Join-Path $Root '.venv\Scripts\python.exe'
& $Py -m pip install --upgrade pip
& $Py -m pip install -r source\requirements.txt pyinstaller scipy scikit-image aggdraw

# 1. Application folder (dist\Dirt Gear\Dirt Gear.exe + _internal)
& $Py -m PyInstaller --noconfirm --distpath dist --workpath work 'build\Dirt Gear.spec'
# 2. Payload zip
& $Py build\build_payload.py
# 3. Single-file installer
& $Py -m PyInstaller --noconfirm --onefile --windowed --name "Dirt Gear v$Version Setup" `
    --icon "$Root\source\icon.ico" --add-data "$Root\build\payload.zip;." `
    --distpath release --workpath work\installer --specpath work\installer "$Root\build\installer.py"

Write-Host "Built release\Dirt Gear v$Version Setup.exe"
