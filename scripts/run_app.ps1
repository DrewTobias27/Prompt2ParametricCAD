param (
    [switch]$Network,
    [switch]$SkipFrontendBuild,
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $repoRoot "frontend"
Set-Location $repoRoot

$pythonExe = if ($env:PROMPT2CAD_PYTHON) {
    $env:PROMPT2CAD_PYTHON
}
else {
    "python"
}

$pnpmExe = if ($env:PROMPT2CAD_PNPM) {
    $env:PROMPT2CAD_PNPM
}
else {
    "pnpm"
}

if (-not $SkipFrontendBuild) {
    Write-Host "Building the React frontend..."
    Push-Location $frontendRoot
    try {
        & $pnpmExe build
        if ($LASTEXITCODE -ne 0) {
            throw "Frontend build failed."
        }
    }
    finally {
        Pop-Location
    }
}

$env:PYTHONPATH = "src"
$hostAddress = if ($Network) { "0.0.0.0" } else { "127.0.0.1" }

if (-not $env:OPENAI_API_KEY) {
    Write-Warning "OPENAI_API_KEY is not set; AI generation will fail."
}

Write-Host ""
Write-Host "Starting Prompt2ParametricCAD at http://127.0.0.1:$Port/"
if ($Network) {
    Write-Host "Network access is enabled. Use this computer's IPv4 address from another device."
}
Write-Host "Press Ctrl+C to stop the server."

& $pythonExe -m uvicorn prompt2cad.web_app:app --host $hostAddress --port $Port
