$ErrorActionPreference = "Stop"

$venvPython = ".\.venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "Virtual environment was not found. Run .\scripts\setup.ps1 first." -ForegroundColor Yellow
    exit 1
}

& $venvPython -m tarkov_ammo_scanner
