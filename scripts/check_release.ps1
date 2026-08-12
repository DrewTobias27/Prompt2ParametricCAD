param(
    [switch]$FullMatrix,
    [switch]$CompileSolidWorksPackage
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendRoot = Join-Path $repoRoot "frontend"
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

function Invoke-ReleaseStep {
    param(
        [string]$Name,
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "[Prompt2CAD] $Name" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE."
    }
}

Set-Location $repoRoot
$env:PYTHONPATH = "src"

Invoke-ReleaseStep "Running Python regression suite" {
    & $pythonExe -m pytest -q
}

Invoke-ReleaseStep "Running frontend behavior checks" {
    Push-Location $frontendRoot
    try {
        & $pnpmExe qa
    }
    finally {
        Pop-Location
    }
}

Invoke-ReleaseStep "Building production frontend" {
    Push-Location $frontendRoot
    try {
        & $pnpmExe build
    }
    finally {
        Pop-Location
    }
}

Invoke-ReleaseStep "Running golden CAD release matrix" {
    & $pythonExe -m prompt2cad.release_matrix `
        --output-root generated\release-matrix-final
}

if ($CompileSolidWorksPackage) {
    $previousCompileSetting = $env:P2P_RUN_SOLIDWORKS_COMPILE
    try {
        $env:P2P_RUN_SOLIDWORKS_COMPILE = "1"
        Invoke-ReleaseStep "Compiling downloaded SolidWorks package runner" {
            & $pythonExe -m pytest `
                tests\test_solidworks_package.py::test_extracted_package_setup_check_compiles_runner `
                -q
        }
    }
    finally {
        $env:P2P_RUN_SOLIDWORKS_COMPILE = $previousCompileSetting
    }
}

if ($FullMatrix) {
    Invoke-ReleaseStep "Running all 292 generated capability cases" {
        & $pythonExe -m prompt2cad.capability_audit `
            --output-root generated\capability-release-final
    }
}

Write-Host ""
Write-Host "Deterministic release checks passed." -ForegroundColor Green
Write-Host (
    "Native SolidWorks create/edit/reopen checks remain explicit; " +
    "follow docs\hosting.md before a public release."
)
