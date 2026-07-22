$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Виртуальное окружение не найдено. Сначала запустите .\scripts\setup.ps1" -ForegroundColor Yellow
    exit 1
}

& ".\.venv\Scripts\python.exe" -m tarkov_ammo_scanner
