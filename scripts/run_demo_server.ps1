$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$env:PYTHONPATH = "src"
$pythonExe = "python"
if ($env:PROMPT2CAD_PYTHON) {
    $pythonExe = $env:PROMPT2CAD_PYTHON
}

Write-Host "Starting Prompt2CAD demo server..."
Write-Host ""

if (-not $env:OPENAI_API_KEY) {
    Write-Host "Warning: OPENAI_API_KEY is not set in this terminal."
    Write-Host "Prompt generation will fail, but saved demo examples still work."
    Write-Host ""
}

Write-Host "Open this computer at:"
Write-Host "  http://127.0.0.1:8000/"
Write-Host ""
Write-Host "To open from another laptop on the same network:"
Write-Host "  1. Run ipconfig in another PowerShell window."
Write-Host "  2. Find this computer's IPv4 Address."
Write-Host "  3. On the laptop, open http://YOUR-IPV4-ADDRESS:8000/"
Write-Host ""
Write-Host "If Windows Firewall asks, allow Python on private networks."
Write-Host "Press Ctrl+C here to stop the server."
Write-Host ""

& $pythonExe -m uvicorn prompt2cad.web_app:app --host 0.0.0.0 --port 8000
