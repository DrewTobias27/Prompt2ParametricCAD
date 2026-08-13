param(
    [string]$OutputRoot,
    [string]$TemplatePath,
    [switch]$Visible
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = if ($env:PROMPT2CAD_PYTHON) {
    $env:PROMPT2CAD_PYTHON
}
else {
    "python"
}

if (-not $OutputRoot) {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutputRoot = Join-Path `
        $repoRoot `
        ("generated\solidworks-release-v8-" + $timestamp)
}
$OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
if (Test-Path -LiteralPath $OutputRoot) {
    throw (
        "Refusing to overwrite an existing native release directory: " +
        $OutputRoot
    )
}
New-Item -ItemType Directory -Path $OutputRoot | Out-Null

function Invoke-NativeReleaseStep {
    param(
        [string]$Name,
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "[Prompt2CAD native] $Name" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE."
    }
}

Set-Location $repoRoot
$previousNativeSetting = $env:P2P_RUN_SOLIDWORKS_NATIVE
$previousPythonPath = $env:PYTHONPATH
try {
    $env:P2P_RUN_SOLIDWORKS_NATIVE = "1"
    $env:PYTHONPATH = "src"

    Invoke-NativeReleaseStep "Running downloaded-package native checks" {
        & $pythonExe -m pytest `
            tests\test_solidworks_package.py::test_extracted_package_builds_verified_native_part `
            tests\test_solidworks_package.py::test_curved_side_attachment_matches_cadquery_in_native_solidworks `
            -q
    }

    $smokeArguments = @(
        "-m", "prompt2cad.solidworks_smoke",
        "--execute",
        "--verify-editability",
        "--output-root", (Join-Path $OutputRoot "smoke")
    )
    if ($Visible.IsPresent) {
        $smokeArguments += "--visible"
    }
    if ($TemplatePath) {
        $smokeArguments += @("--template", $TemplatePath)
    }
    Invoke-NativeReleaseStep "Running ten-case native smoke and edit gate" {
        & $pythonExe @smokeArguments
    }

    $goldenArguments = @(
        "-m", "prompt2cad.release_matrix",
        "--execute-native",
        "--verify-native-editability",
        "--output-root", (Join-Path $OutputRoot "golden")
    )
    if ($Visible.IsPresent) {
        $goldenArguments += "--visible"
    }
    if ($TemplatePath) {
        $goldenArguments += @("--template", $TemplatePath)
    }
    Invoke-NativeReleaseStep "Running seven-case golden native and edit gate" {
        & $pythonExe @goldenArguments
    }

    Write-Host ""
    Write-Host "Installed-SolidWorks release checks passed." -ForegroundColor Green
    Write-Host "Evidence: $OutputRoot"
}
finally {
    $env:P2P_RUN_SOLIDWORKS_NATIVE = $previousNativeSetting
    $env:PYTHONPATH = $previousPythonPath
}
