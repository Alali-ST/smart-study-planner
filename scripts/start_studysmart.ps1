param([switch]$NoBrowser)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $projectRoot "backend"
$venvRoot = Join-Path $backendRoot ".venv"
$venvPython = Join-Path $venvRoot "Scripts\python.exe"
$requirements = Join-Path $backendRoot "requirements.txt"
$dependencyMarker = Join-Path $venvRoot ".studysmart-dependencies"
$modelPath = Join-Path $backendRoot "instance\oulad_random_forest.joblib"
$rawDataPath = Join-Path $backendRoot "data\oulad\raw"
$datasetPath = Join-Path $backendRoot "data\oulad\processed\training_data.csv"
$environmentFile = Join-Path $backendRoot ".env"
$healthUrl = "http://127.0.0.1:5000/api/v1/health"
$appUrl = "http://127.0.0.1:5000"

function Test-StudySmartServer {
    try {
        $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

try {
    Write-Host ""
    Write-Host "  StudySmart" -ForegroundColor Green
    Write-Host "  Preparing your intelligent study workspace..." -ForegroundColor DarkGray
    Write-Host ""

    if (Test-StudySmartServer) {
        Write-Host "  StudySmart is already running." -ForegroundColor Green
        if (-not $NoBrowser) { Start-Process $appUrl }
        exit 0
    }

    if (-not (Test-Path -LiteralPath $venvPython)) {
        Write-Host "  Creating the private Python environment (first launch only)..."
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if (-not $pythonCommand) {
            throw "Python was not found. Install Python 3.11 or newer from python.org, then run this launcher again."
        }
        & $pythonCommand.Source -m venv $venvRoot
        if ($LASTEXITCODE -ne 0) { throw "Python could not create the application environment." }
    }

    $requirementsStamp = (Get-FileHash -LiteralPath $requirements -Algorithm SHA256).Hash
    $installedStamp = if (Test-Path -LiteralPath $dependencyMarker) { (Get-Content -Raw -LiteralPath $dependencyMarker).Trim() } else { "" }
    if ($installedStamp -ne $requirementsStamp) {
        Write-Host "  Installing verified application components (first launch may take a few minutes)..."
        & $venvPython -m pip install --disable-pip-version-check --upgrade pip
        if ($LASTEXITCODE -ne 0) { throw "The Python installer could not update itself." }
        & $venvPython -m pip install --disable-pip-version-check -r $requirements
        if ($LASTEXITCODE -ne 0) { throw "Application components could not be installed. Check your internet connection and try again." }
        Set-Content -LiteralPath $dependencyMarker -Value $requirementsStamp -Encoding ASCII
    }

    if (-not (Test-Path -LiteralPath $environmentFile)) {
        $secretBytes = New-Object byte[] 32
        $jwtBytes = New-Object byte[] 32
        $random = [Security.Cryptography.RandomNumberGenerator]::Create()
        try {
            $random.GetBytes($secretBytes)
            $random.GetBytes($jwtBytes)
        } finally {
            $random.Dispose()
        }
        $secret = [Convert]::ToBase64String($secretBytes)
        $jwtSecret = [Convert]::ToBase64String($jwtBytes)
        $environmentLines = @(
            "FLASK_ENV=development",
            "SECRET_KEY=$secret",
            "JWT_SECRET_KEY=$jwtSecret",
            "DATABASE_URL=sqlite:///smart_study_planner.db",
            "MODEL_PATH=instance/oulad_random_forest.joblib",
            "SESSION_HOURS=8",
            "CORS_ORIGINS=http://127.0.0.1:5000,http://localhost:5000"
        )
        Set-Content -LiteralPath $environmentFile -Value $environmentLines -Encoding ASCII
    } else {
        $environmentText = Get-Content -Raw -LiteralPath $environmentFile
        if ($environmentText -match '(?m)^MODEL_PATH=') {
            $environmentText = $environmentText -replace '(?m)^MODEL_PATH=.*$', 'MODEL_PATH=instance/oulad_random_forest.joblib'
        } else {
            $environmentText = $environmentText.TrimEnd() + [Environment]::NewLine + 'MODEL_PATH=instance/oulad_random_forest.joblib' + [Environment]::NewLine
        }
        Set-Content -LiteralPath $environmentFile -Value $environmentText -Encoding ASCII -NoNewline
    }

    Push-Location $backendRoot
    try {
        Write-Host "  Checking the database..."
        & $venvPython -m flask --app run.py init-db
        if ($LASTEXITCODE -ne 0) { throw "The StudySmart database could not be initialized." }

        if (-not (Test-Path -LiteralPath $datasetPath)) {
            Write-Host "  Downloading the official OULAD research data (first launch only)..."
            & $venvPython -m flask --app run.py download-oulad --output-dir $rawDataPath
            if ($LASTEXITCODE -ne 0) { throw "OULAD could not be downloaded. Check your internet connection and try again." }
            Write-Host "  Structuring first-60-day OULAD assessment records..."
            & $venvPython -m flask --app run.py prepare-oulad --raw-dir $rawDataPath --output $datasetPath --cutoff-day 60
            if ($LASTEXITCODE -ne 0) { throw "The OULAD training records could not be prepared." }
        }

        if (-not (Test-Path -LiteralPath $modelPath)) {
            Write-Host "  Training and evaluating the OULAD Random Forest model..."
            & $venvPython -m flask --app run.py train-model --dataset $datasetPath
            if ($LASTEXITCODE -ne 0) { throw "The academic prediction model could not be prepared." }
        }

        Write-Host "  Starting StudySmart..."
        $server = Start-Process -FilePath $venvPython -ArgumentList "run.py" -WorkingDirectory $backendRoot -WindowStyle Hidden -PassThru
    } finally {
        Pop-Location
    }

    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 500
        if (Test-StudySmartServer) { $ready = $true; break }
        if ($server.HasExited) { break }
    }
    if (-not $ready) { throw "The StudySmart server did not start correctly." }

    if ($NoBrowser) {
        Write-Host "  Ready. StudySmart is running at $appUrl" -ForegroundColor Green
    } else {
        Write-Host "  Ready. Opening StudySmart in your browser." -ForegroundColor Green
        Start-Process $appUrl
    }
    Start-Sleep -Seconds 2
    exit 0
} catch {
    Write-Host ""
    Write-Host "  StudySmart could not start:" -ForegroundColor Red
    Write-Host "  $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}
