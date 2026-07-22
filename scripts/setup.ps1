$ErrorActionPreference = "Stop"

function Find-Tesseract {
    $command = Get-Command tesseract.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }

    $candidates = @(
        "$env:ProgramFiles\Tesseract-OCR\tesseract.exe",
        "${env:ProgramFiles(x86)}\Tesseract-OCR\tesseract.exe",
        "$env:LOCALAPPDATA\Programs\Tesseract-OCR\tesseract.exe"
    )

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path $candidate)) { return $candidate }
    }

    return $null
}

if (-not (Get-Command py.exe -ErrorAction SilentlyContinue) -and -not (Get-Command python.exe -ErrorAction SilentlyContinue)) {
    throw "Python 3.11+ не найден. Установите Python с python.org или через winget."
}

$python = if (Get-Command py.exe -ErrorAction SilentlyContinue) { "py" } else { "python" }

if (-not (Test-Path ".\.venv")) {
    & $python -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

$tesseract = Find-Tesseract
if (-not $tesseract) {
    Write-Host "Tesseract не найден. Пробую установить через winget..." -ForegroundColor Yellow
    if (Get-Command winget.exe -ErrorAction SilentlyContinue) {
        winget install --id UB-Mannheim.TesseractOCR --exact --accept-package-agreements --accept-source-agreements
        $tesseract = Find-Tesseract
    }
}

if ($tesseract) {
    Write-Host "Tesseract: $tesseract" -ForegroundColor Green

    $tessdata = Join-Path (Split-Path $tesseract) "tessdata"
    $rus = Join-Path $tessdata "rus.traineddata"
    if (-not (Test-Path $rus)) {
        Write-Host "Русская модель OCR не найдена. Загружаю rus.traineddata..." -ForegroundColor Yellow
        New-Item -ItemType Directory -Force -Path $tessdata | Out-Null
        Invoke-WebRequest `
            -Uri "https://github.com/tesseract-ocr/tessdata_fast/raw/main/rus.traineddata" `
            -OutFile $rus
    }
} else {
    Write-Host "Tesseract автоматически установить не удалось." -ForegroundColor Red
    Write-Host "Установите его вручную: winget install --id UB-Mannheim.TesseractOCR --exact"
}

Write-Host "Готово. Запуск: .\run.ps1" -ForegroundColor Green
