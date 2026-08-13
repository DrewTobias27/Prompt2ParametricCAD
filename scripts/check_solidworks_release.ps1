param(
    [string]$OutputRoot,
    [string]$TemplatePath,
    [string]$DownloadedPackagePath,
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
$transcriptPath = Join-Path $OutputRoot "solidworks-release-transcript.txt"

if ($DownloadedPackagePath) {
    if (-not (Test-Path -LiteralPath $DownloadedPackagePath -PathType Leaf)) {
        throw "Downloaded SolidWorks package was not found: $DownloadedPackagePath"
    }
    $DownloadedPackagePath = (Resolve-Path -LiteralPath $DownloadedPackagePath).Path
    if ([System.IO.Path]::GetExtension($DownloadedPackagePath) -ne ".zip") {
        throw "DownloadedPackagePath must point to a ZIP file."
    }
}

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

$previousLocation = Get-Location
$previousNativeSetting = $env:P2P_RUN_SOLIDWORKS_NATIVE
$previousPythonPath = $env:PYTHONPATH
$transcriptStarted = $false
try {
    Set-Location $repoRoot
    Start-Transcript -LiteralPath $transcriptPath | Out-Null
    $transcriptStarted = $true
    $env:P2P_RUN_SOLIDWORKS_NATIVE = "1"
    $env:PYTHONPATH = "src"

    Invoke-NativeReleaseStep "Running portable-package native checks" {
        & $pythonExe -m pytest `
            tests\test_solidworks_package.py::test_extracted_package_builds_verified_native_part `
            tests\test_solidworks_package.py::test_curved_side_attachment_matches_cadquery_in_native_solidworks `
            -q
    }

    if ($DownloadedPackagePath) {
        $downloadedRoot = Join-Path $OutputRoot "downloaded-package"
        $extractionReport = Join-Path `
            $OutputRoot `
            "downloaded-package-integrity.json"
        Invoke-NativeReleaseStep "Extracting and verifying public package" {
            & $pythonExe -m prompt2cad.solidworks_package_check extract `
                --package-zip $DownloadedPackagePath `
                --extract-to $downloadedRoot `
                --output $extractionReport
        }

        $downloadedOutput = Join-Path `
            $OutputRoot `
            "downloaded-package.SLDPRT"
        $downloadedResult = "$downloadedOutput.result.json"
        $launcherPath = Join-Path `
            $downloadedRoot `
            "Build-SolidWorks-Part.ps1"
        $launcherArguments = @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", $launcherPath,
            "-OutputPath", $downloadedOutput
        )
        if ($Visible.IsPresent) {
            $launcherArguments += "-Visible"
        }
        if ($TemplatePath) {
            $launcherArguments += @("-TemplatePath", $TemplatePath)
        }
        Invoke-NativeReleaseStep "Building the public downloaded package" {
            & powershell.exe @launcherArguments
        }

        $verificationReport = Join-Path `
            $OutputRoot `
            "downloaded-package-native-verification.json"
        Invoke-NativeReleaseStep "Verifying the public package result" {
            & $pythonExe -m prompt2cad.solidworks_package_check verify `
                --package-root $downloadedRoot `
                --result $downloadedResult `
                --output $verificationReport
        }
    }
    else {
        Write-Host ""
        Write-Host (
            "No downloaded package was supplied; the public-package gate " +
            "was not run. Use -DownloadedPackagePath before release."
        ) -ForegroundColor Yellow
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
    if ($transcriptStarted) {
        Stop-Transcript | Out-Null
    }
    Set-Location $previousLocation
}
