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
        ("generated\solidworks-release-v9-" + $timestamp)
}
$OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
if (Test-Path -LiteralPath $OutputRoot) {
    throw (
        "Refusing to overwrite an existing native release directory: " +
        $OutputRoot
    )
}

if ($DownloadedPackagePath) {
    if (-not (Test-Path -LiteralPath $DownloadedPackagePath -PathType Leaf)) {
        throw "Downloaded SolidWorks package was not found: $DownloadedPackagePath"
    }
    $DownloadedPackagePath = (Resolve-Path -LiteralPath $DownloadedPackagePath).Path
    if ([System.IO.Path]::GetExtension($DownloadedPackagePath) -ne ".zip") {
        throw "DownloadedPackagePath must point to a ZIP file."
    }
}
New-Item -ItemType Directory -Path $OutputRoot | Out-Null
$transcriptPath = Join-Path $OutputRoot "solidworks-release-transcript.txt"

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
    $packageVersionText = (& $pythonExe -c (
        "from prompt2cad.solidworks_package import " +
        "SOLIDWORKS_PACKAGE_VERSION; print(SOLIDWORKS_PACKAGE_VERSION)"
    ) | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $packageVersionText -notmatch '^\d+$') {
        throw "Could not resolve the current SolidWorks package version."
    }
    $packageVersion = [int]$packageVersionText

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

        $mutationPath = Join-Path `
            $OutputRoot `
            "downloaded-package-mutation.json"
        Invoke-NativeReleaseStep "Selecting a safe public-package edit" {
            & $pythonExe -m prompt2cad.solidworks_package_check mutation `
                --package-root $downloadedRoot `
                --output $mutationPath
        }

        $editedOutput = Join-Path `
            $OutputRoot `
            "downloaded-package-edited.SLDPRT"
        $editedResult = "$editedOutput.result.json"
        $editArguments = @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", (Join-Path $downloadedRoot "solidworks_replay.ps1"),
            "-PlanPath", (
                Join-Path $downloadedRoot "solidworks-replay-plan.json"
            ),
            "-ExistingPartPath", $downloadedOutput,
            "-MutationPath", $mutationPath,
            "-OutputPath", $editedOutput
        )
        if ($Visible.IsPresent) {
            $editArguments += "-Visible"
        }
        Invoke-NativeReleaseStep "Editing and reopening the public package" {
            $editResultText = (& powershell.exe @editArguments | Out-String).Trim()
            $editExitCode = $LASTEXITCODE
            if ($editExitCode -ne 0) {
                throw (
                    "Downloaded-package edit failed with exit code " +
                    "$editExitCode."
                )
            }
            if (-not $editResultText) {
                throw "Downloaded-package edit returned no verification result."
            }
            $editResultText |
                Set-Content -LiteralPath $editedResult -Encoding UTF8
        }

        $editVerificationReport = Join-Path `
            $OutputRoot `
            "downloaded-package-edit-verification.json"
        Invoke-NativeReleaseStep "Verifying the public package edit" {
            & $pythonExe -m prompt2cad.solidworks_package_check verify-edit `
                --package-root $downloadedRoot `
                --mutation $mutationPath `
                --source $downloadedOutput `
                --result $editedResult `
                --output $editVerificationReport
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
    $smokeReportPath = Join-Path $OutputRoot "smoke\report.json"
    $smokeReport = Get-Content -LiteralPath $smokeReportPath -Raw |
        ConvertFrom-Json
    if (-not $smokeReport.release_gate_passed -or
        -not $smokeReport.native_gate_coverage.passed) {
        throw (
            "Native smoke cases passed without complete replay-family " +
            "coverage. Add a gate fixture before release."
        )
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

    $publicReleaseReady = [bool]$DownloadedPackagePath
    $releaseStatus = "native_suite_pass_public_package_pending"
    $downloadedEvidence = $null
    if ($publicReleaseReady) {
        $releaseStatus = "pass"
        $downloadedEvidence = [ordered]@{
            source_zip = $DownloadedPackagePath
            source_zip_sha256 = (
                Get-FileHash `
                    -LiteralPath $DownloadedPackagePath `
                    -Algorithm SHA256
            ).Hash.ToLowerInvariant()
            integrity = $extractionReport
            initial_part = $downloadedOutput
            initial_result = $downloadedResult
            initial_verification = $verificationReport
            mutation = $mutationPath
            edited_part = $editedOutput
            edited_result = $editedResult
            edit_verification = $editVerificationReport
        }
    }
    $releaseSummaryPath = Join-Path $OutputRoot "release-summary.json"
    [ordered]@{
        format = "prompt2cad.solidworks-release-evidence"
        version = 1
        status = $releaseStatus
        completed_at_utc = [DateTime]::UtcNow.ToString("o")
        package_version = $packageVersion
        public_release_ready = $publicReleaseReady
        portable_package_native_cases = 2
        native_smoke_cases = 10
        native_smoke_coverage = $smokeReport.native_gate_coverage
        native_golden_cases = 7
        downloaded_package = $downloadedEvidence
        smoke_report = $smokeReportPath
        golden_report = (Join-Path $OutputRoot "golden\report.json")
        transcript = $transcriptPath
    } | ConvertTo-Json -Depth 8 |
        Set-Content -LiteralPath $releaseSummaryPath -Encoding UTF8

    Write-Host ""
    Write-Host "Installed-SolidWorks release checks passed." -ForegroundColor Green
    if (-not $publicReleaseReady) {
        Write-Host (
            "Public release is still pending a fresh downloaded package run."
        ) -ForegroundColor Yellow
    }
    Write-Host "Evidence: $OutputRoot"
    Write-Host "Summary:  $releaseSummaryPath"
}
finally {
    $env:P2P_RUN_SOLIDWORKS_NATIVE = $previousNativeSetting
    $env:PYTHONPATH = $previousPythonPath
    if ($transcriptStarted) {
        Stop-Transcript | Out-Null
    }
    Set-Location $previousLocation
}
