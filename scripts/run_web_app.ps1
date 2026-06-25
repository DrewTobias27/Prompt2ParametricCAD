$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$env:PYTHONPATH = "src"

if (-not $env:OPENAI_API_KEY) {
    Write-Host "Warning: OPENAI_API_KEY is not set in this terminal."
    Write-Host "The web page will load, but Generate CAD will fail until the key is set."
    Write-Host ""
}

..\..\..\work\cadquery-env\Scripts\python.exe -m uvicorn prompt2cad.web_app:app --host 127.0.0.1 --port 8000
