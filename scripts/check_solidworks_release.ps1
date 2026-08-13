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

$versionPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $repoRoot "src"
    $packageVersionText = (& $pythonExe -c (
        "from prompt2cad.solidworks_package import " +
        "SOLIDWORKS_PACKAGE_VERSION; print(SOLIDWORKS_PACKAGE_VERSION)"
    ) | Out-String).Trim()
    $packageVersionExitCode = $LASTEXITCODE
}
finally {
    if ($null -eq $versionPythonPath) {
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
    }
    else {
        $env:PYTHONPATH = $versionPythonPath
    }
}
if ($packageVersionExitCode -ne 0 -or $packageVersionText -notmatch '^\d+$') {
    throw "Could not resolve the current SolidWorks package version."
}
$packageVersion = [int]$packageVersionText

if (-not $OutputRoot) {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutputRoot = Join-Path `
        $repoRoot `
        ("generated\solidworks-release-v{0}-{1}" -f `
            $packageVersion, `
            $timestamp)
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

    $portablePackageReport = Join-Path `
        $OutputRoot `
        "portable-package-native-tests.xml"
    Invoke-NativeReleaseStep "Running portable-package native checks" {
        & $pythonExe -m pytest `
            -m solidworks_native `
            tests\test_solidworks_package.py `
            --junitxml $portablePackageReport `
            -q
    }
    [xml]$portableJUnit = Get-Content `
        -LiteralPath $portablePackageReport `
        -Raw
    $portableSuites = @($portableJUnit.testsuites.testsuite)
    $portablePackageNativeCases = [int](
        ($portableSuites | Measure-Object -Property tests -Sum).Sum
    )
    $portablePackageFailures = [int](
        ($portableSuites | Measure-Object -Property failures -Sum).Sum
    ) + [int](
        ($portableSuites | Measure-Object -Property errors -Sum).Sum
    ) + [int](
        ($portableSuites | Measure-Object -Property skipped -Sum).Sum
    )
    if ($portablePackageNativeCases -le 0 -or
        $portablePackageFailures -ne 0) {
        throw "Portable-package native test evidence is incomplete."
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
    Invoke-NativeReleaseStep "Running native smoke and edit gate" {
        & $pythonExe @smokeArguments
    }
    $smokeReportPath = Join-Path $OutputRoot "smoke\report.json"
    $smokeReport = Get-Content -LiteralPath $smokeReportPath -Raw |
        ConvertFrom-Json
    if (-not $smokeReport.release_gate_passed -or
        -not $smokeReport.native_gate_coverage.passed -or
        -not $smokeReport.native_edit_coverage.passed) {
        throw (
            "Native smoke cases passed without complete replay or edit " +
            "coverage. Add a gate fixture or mutation before release."
        )
    }
    $nativeSmokeCases = @($smokeReport.results).Count
    if ($nativeSmokeCases -le 0 -or
        [int]$smokeReport.passed -ne $nativeSmokeCases -or
        [int]$smokeReport.failed -ne 0) {
        throw "Native smoke report does not prove every selected case passed."
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
    Invoke-NativeReleaseStep "Running golden native and edit gate" {
        & $pythonExe @goldenArguments
    }
    $goldenReportPath = Join-Path $OutputRoot "golden\report.json"
    $goldenReport = Get-Content -LiteralPath $goldenReportPath -Raw |
        ConvertFrom-Json
    $nativeGoldenCases = @($goldenReport.results).Count
    $missingGoldenEdits = @(
        $goldenReport.results | Where-Object {
            $_.status -ne "pass" -or
            $_.checks.solidworks_native.passed -ne $true -or
            $_.checks.solidworks_native.editability.passed -ne $true
        }
    )
    if ($goldenReport.mode -ne "native" -or
        $nativeGoldenCases -le 0 -or
        [int]$goldenReport.case_count -ne $nativeGoldenCases -or
        [int]$goldenReport.passed -ne $nativeGoldenCases -or
        [int]$goldenReport.failed -ne 0 -or
        $missingGoldenEdits.Count -ne 0) {
        throw "Golden report does not prove native create and edit parity."
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
        portable_package_native_cases = $portablePackageNativeCases
        portable_package_report = $portablePackageReport
        native_smoke_cases = $nativeSmokeCases
        native_smoke_coverage = $smokeReport.native_gate_coverage
        native_edit_coverage = $smokeReport.native_edit_coverage
        native_golden_cases = $nativeGoldenCases
        downloaded_package = $downloadedEvidence
        smoke_report = $smokeReportPath
        golden_report = $goldenReportPath
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
    try {
        if ($transcriptStarted) {
            Stop-Transcript | Out-Null
        }
    }
    finally {
        if ($null -eq $previousNativeSetting) {
            Remove-Item Env:P2P_RUN_SOLIDWORKS_NATIVE `
                -ErrorAction SilentlyContinue
        }
        else {
            $env:P2P_RUN_SOLIDWORKS_NATIVE = $previousNativeSetting
        }
        if ($null -eq $previousPythonPath) {
            Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
        }
        else {
            $env:PYTHONPATH = $previousPythonPath
        }
        Set-Location $previousLocation
    }
}
