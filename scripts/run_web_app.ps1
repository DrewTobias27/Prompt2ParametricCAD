$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$env:PYTHONPATH = "src"
$pythonExe = "python"
if ($env:PROMPT2CAD_PYTHON) {
    $pythonExe = $env:PROMPT2CAD_PYTHON
}

if (-not $env:OPENAI_API_KEY) {
    Write-Host "Warning: OPENAI_API_KEY is not set in this terminal."
    Write-Host "The web page will load, but Generate CAD will fail until the key is set."
    Write-Host ""
}

& $pythonExe -m uvicorn prompt2cad.web_app:app --host 127.0.0.1 --port 8000
