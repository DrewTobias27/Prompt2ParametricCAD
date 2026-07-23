$ErrorActionPreference = "Continue"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$pythonExe = "python"
if ($env:PROMPT2CAD_PYTHON) {
    $pythonExe = $env:PROMPT2CAD_PYTHON
}

$env:PYTHONPATH = "src"
$failed = $false

function Write-Check {
    param (
        [bool]$Passed,
        [string]$Message
    )

    if ($Passed) {
        Write-Host "[OK] $Message" -ForegroundColor Green
    }
    else {
        Write-Host "[FAIL] $Message" -ForegroundColor Red
        $script:failed = $true
    }
}

function Write-Warn {
    param ([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

Write-Host "Checking Prompt2ParametricCAD setup..."
Write-Host "Repository: $repoRoot"
Write-Host "Python: $pythonExe"
Write-Host ""

& $pythonExe --version
Write-Check ($LASTEXITCODE -eq 0) "Python command is available"

$importCheck = @'
import importlib

packages = [
    "cadquery",
    "fastapi",
    "uvicorn",
    "openai",
    "jsonschema",
    "pytest",
    "pydantic",
]

missing = []
for package in packages:
    try:
        importlib.import_module(package)
    except Exception as error:
        missing.append(f"{package}: {error}")

if missing:
    raise SystemExit("\n".join(missing))

print("Required packages imported successfully")
'@

$importCheck | & $pythonExe -
Write-Check ($LASTEXITCODE -eq 0) "Required Python packages import"

$smokeCheck = @'
from prompt2cad.interpreter import build_model
from prompt2cad.schema import validate_model_data

model_data = {
    "operations": [
        {
            "type": "extrude",
            "id": "base",
            "plane": "XY",
            "profile": "rectangle",
            "width": 20,
            "height": 10,
            "distance": 4,
        }
    ]
}

validate_model_data(model_data)
part = build_model(model_data)
solids = part.solids().vals()

if len(solids) != 1:
    raise SystemExit(f"Expected one solid, found {len(solids)}")

if not solids[0].isValid():
    raise SystemExit("Smoke-test solid is invalid")

bounding_box = part.val().BoundingBox()
print(
    "Built smoke-test model "
    f"({bounding_box.xlen:.1f} x {bounding_box.ylen:.1f} x {bounding_box.zlen:.1f})"
)
'@

$smokeCheck | & $pythonExe -
Write-Check ($LASTEXITCODE -eq 0) "Prompt2CAD can build a simple CadQuery model"

$pnpmExe = if ($env:PROMPT2CAD_PNPM) {
    $env:PROMPT2CAD_PNPM
}
else {
    "pnpm"
}
$pnpmCommand = Get-Command $pnpmExe -ErrorAction SilentlyContinue
if ($pnpmCommand) {
    & $pnpmExe --version
    Write-Check ($LASTEXITCODE -eq 0) "pnpm is available for the React frontend"
}
else {
    Write-Warn "pnpm is unavailable; set PROMPT2CAD_PNPM to the full pnpm.cmd path"
}

if ($env:OPENAI_API_KEY) {
    Write-Check $true "OPENAI_API_KEY is set for prompt generation"
}
else {
    Write-Warn "OPENAI_API_KEY is not set; prompt generation will fail until it is configured"
}

Write-Host ""
if ($failed) {
    Write-Host "Setup check failed. See the messages above for what to fix." -ForegroundColor Red
    exit 1
}

Write-Host "Setup check passed." -ForegroundColor Green
