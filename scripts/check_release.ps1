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
$nodeExe = if ($env:PROMPT2CAD_NODE) {
    $env:PROMPT2CAD_NODE
}
else {
    "node"
}
$frontendChecks = @(
    "manual-assistance-smoke.mjs",
    "preview-qa.mjs",
    "generated-review-smoke.mjs",
    "refinement-smoke.mjs",
    "editable-parameters-smoke.mjs",
    "solidworks-package-smoke.mjs"
)

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

Invoke-ReleaseStep "Scanning tracked files for credentials" {
    & $pythonExe scripts\check_secrets.py
}

Invoke-ReleaseStep "Running Python regression suite" {
    & $pythonExe -m pytest -q
}

Invoke-ReleaseStep "Running frontend behavior checks" {
    Push-Location $frontendRoot
    try {
        foreach ($check in $frontendChecks) {
            & $nodeExe (Join-Path "scripts" $check)
            if ($LASTEXITCODE -ne 0) {
                throw "Frontend check $check failed with exit code $LASTEXITCODE."
            }
        }
    }
    finally {
        Pop-Location
    }
}

Invoke-ReleaseStep "Building production frontend" {
    Push-Location $frontendRoot
    try {
        & $nodeExe `
            (Join-Path "node_modules" "vite\bin\vite.js") `
            build `
            --configLoader runner
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
                tests\test_solidworks_package.py::test_setup_check_rejects_conflicting_canonical_revolve_axis `
                tests\test_solidworks_package.py::test_setup_check_rejects_a_malformed_geometry_oracle `
                tests\test_solidworks_package.py::test_setup_check_rejects_duplicate_native_names `
                tests\test_solidworks_package.py::test_setup_check_rejects_unknown_semantic_datum_plane `
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
            --export-steps `
            --output-root generated\capability-release-final
    }
}

Write-Host ""
Write-Host "Deterministic release checks passed." -ForegroundColor Green
Write-Host (
    "Native SolidWorks create/edit/reopen checks remain explicit; " +
    "follow docs\hosting.md before a public release."
)
