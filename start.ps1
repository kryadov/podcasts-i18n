$ErrorActionPreference = "Stop"

if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $pair = $line -split "=", 2
        if ($pair.Count -lt 2) { return }
        $name = $pair[0].Trim()
        $value = $pair[1].Trim()
        if ($name) {
            $env:$name = $value
        }
    }
}

if (-not $env:GOOGLE_API_KEY) {
    Write-Error "GOOGLE_API_KEY is not set. Set it before starting."
    exit 1
}

if (-not $env:APP_DATA_DIR) {
    $env:APP_DATA_DIR = "./data"
}

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload