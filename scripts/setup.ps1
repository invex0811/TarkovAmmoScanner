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
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }

    return $null
}

$python = $null
if (Get-Command py.exe -ErrorAction SilentlyContinue) {
    $python = "py"
} elseif (Get-Command python.exe -ErrorAction SilentlyContinue) {
    $python = "python"
}

if (-not $python) {
    throw "Python 3.11 or newer was not found. Install Python and run this script again."
}

Write-Host "Using Python:" -ForegroundColor Cyan
& $python --version

if (-not (Test-Path -LiteralPath ".\.venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    & $python -m venv .venv
}

$venvPython = ".\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Virtual environment creation failed: $venvPython was not created."
}

Write-Host "Upgrading pip..." -ForegroundColor Cyan
& $venvPython -m pip install --upgrade pip

Write-Host "Installing project dependencies..." -ForegroundColor Cyan
& $venvPython -m pip install -r requirements.txt

$tesseract = Find-Tesseract
if (-not $tesseract) {
    Write-Host "Tesseract was not found. Trying to install it with winget..." -ForegroundColor Yellow

    if (Get-Command winget.exe -ErrorAction SilentlyContinue) {
        winget install --id UB-Mannheim.TesseractOCR --exact --accept-package-agreements --accept-source-agreements
        $tesseract = Find-Tesseract
    }
}

if ($tesseract) {
    Write-Host "Tesseract: $tesseract" -ForegroundColor Green

    $tessdata = Join-Path (Split-Path $tesseract) "tessdata"
    $rus = Join-Path $tessdata "rus.traineddata"

    if (-not (Test-Path -LiteralPath $rus)) {
        Write-Host "Downloading the Russian OCR model..." -ForegroundColor Yellow
        New-Item -ItemType Directory -Force -Path $tessdata | Out-Null
        Invoke-WebRequest `
            -Uri "https://github.com/tesseract-ocr/tessdata_fast/raw/main/rus.traineddata" `
            -OutFile $rus
    }
} else {
    Write-Host "Tesseract could not be installed automatically." -ForegroundColor Red
    Write-Host "Install it manually with:" -ForegroundColor Yellow
    Write-Host "winget install --id UB-Mannheim.TesseractOCR --exact"
}

Write-Host "Setup complete. Start the app with: .\run.ps1" -ForegroundColor Green
