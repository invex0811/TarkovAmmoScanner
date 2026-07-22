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

$projectRoot = Split-Path -Parent $PSScriptRoot
$venvDir = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$requirements = Join-Path $projectRoot "requirements.txt"
$localTessdata = Join-Path $projectRoot "local-data\tessdata"

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

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    & $python -m venv $venvDir
}

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Virtual environment creation failed: $venvPython was not created."
}

Write-Host "Upgrading pip..." -ForegroundColor Cyan
& $venvPython -m pip install --upgrade pip

Write-Host "Installing project dependencies..." -ForegroundColor Cyan
& $venvPython -m pip install -r $requirements

$tesseract = Find-Tesseract
if (-not $tesseract) {
    Write-Host "Tesseract was not found. Trying to install it with winget..." -ForegroundColor Yellow

    if (Get-Command winget.exe -ErrorAction SilentlyContinue) {
        winget install --id UB-Mannheim.TesseractOCR --exact --accept-package-agreements --accept-source-agreements
        $tesseract = Find-Tesseract
    }
}

if (-not $tesseract) {
    Write-Host "Tesseract could not be installed automatically." -ForegroundColor Red
    Write-Host "Install it manually with:" -ForegroundColor Yellow
    Write-Host "winget install --id UB-Mannheim.TesseractOCR --exact"
    exit 1
}

Write-Host "Tesseract: $tesseract" -ForegroundColor Green
Write-Host "Preparing local OCR language models..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $localTessdata | Out-Null

foreach ($language in @("eng", "rus")) {
    $modelPath = Join-Path $localTessdata "$language.traineddata"
    if (-not (Test-Path -LiteralPath $modelPath)) {
        Write-Host "Downloading $language.traineddata..." -ForegroundColor Yellow
        Invoke-WebRequest `
            -UseBasicParsing `
            -Uri "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/$language.traineddata" `
            -OutFile $modelPath
    }

    if (-not (Test-Path -LiteralPath $modelPath)) {
        throw "OCR model download failed: $modelPath"
    }
}

Write-Host "Local tessdata: $localTessdata" -ForegroundColor Green
Write-Host "Setup complete. Start the app with: .\run.ps1" -ForegroundColor Green
