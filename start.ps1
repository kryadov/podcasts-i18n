$ErrorActionPreference = "Stop"

if (-not $env:GOOGLE_API_KEY) {
    Write-Error "GOOGLE_API_KEY is not set. Set it before starting."
    exit 1
}

if (-not $env:APP_DATA_DIR) {
    $env:APP_DATA_DIR = "./data"
}

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload