"""Build portable native-SolidWorks replay bundles for web downloads."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
from textwrap import dedent
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from prompt2cad.editable_model import build_editable_model_document
from prompt2cad.solidworks_editability import native_parameter_coverage
from prompt2cad.solidworks_replay import build_solidworks_replay_plan
from prompt2cad.solidworks_verification import geometry_metrics


SOLIDWORKS_PACKAGE_FORMAT = "prompt2cad.solidworks-package"
SOLIDWORKS_PACKAGE_VERSION = 11
SOLIDWORKS_PACKAGE_PAYLOAD_FILES = (
    "Build-SolidWorks-Part.cmd",
    "Build-SolidWorks-Part.ps1",
    "Check-SolidWorks-Setup.cmd",
    "README.txt",
    "editable-model.json",
    "editability-coverage.json",
    "solidworks-replay-plan.json",
    "solidworks_replay.ps1",
    "solidworks_replay_runner.cs",
    "source-model.json",
)
_FIXED_ZIP_TIMESTAMP = (2026, 1, 1, 0, 0, 0)


@dataclass(frozen=True)
class SolidWorksPackage:
    """One validated, deterministic ZIP ready for browser download."""

    filename: str
    content: bytes
    manifest: dict


def create_solidworks_package(
    model_data: dict,
    filename_hint: str,
) -> SolidWorksPackage:
    """Create a local replay bundle without opening SolidWorks.

    Planning is performed before any bytes are returned, so an unsupported
    model fails on the server rather than after the user downloads a bundle.
    The actual SLDPRT is still created by the included runner on a Windows
    computer with SolidWorks installed.
    """
    part, document = build_editable_model_document(model_data)
    expected_geometry = geometry_metrics(part)
    replay_plan = build_solidworks_replay_plan(
        document,
        expected_geometry=expected_geometry,
    )
    editability_coverage = native_parameter_coverage(
        model_data,
        replay_plan,
        document=document,
    )
    stem = _safe_package_stem(filename_hint, model_data)
    native_filename = f"{stem}.SLDPRT"

    files = {
        **solidworks_package_static_payload(
            native_filename,
            editability_coverage,
        ),
        "source-model.json": _json_bytes(model_data),
        "editable-model.json": _json_bytes(document.to_dict()),
        "editability-coverage.json": _json_bytes(editability_coverage),
        "solidworks-replay-plan.json": _json_bytes(replay_plan.to_dict()),
    }
    if set(files) != set(SOLIDWORKS_PACKAGE_PAYLOAD_FILES):
        raise RuntimeError("SolidWorks package payload contract is incomplete")
    manifest = solidworks_package_manifest(
        native_filename,
        replay_plan,
        editability_coverage,
        files,
    )
    files["manifest.json"] = _json_bytes(manifest)

    return SolidWorksPackage(
        filename=(
            f"{stem}-v{SOLIDWORKS_PACKAGE_VERSION}-solidworks.zip"
        ),
        content=_zip_bytes(files),
        manifest=manifest,
    )


def solidworks_package_manifest(
    native_filename: str,
    replay_plan,
    editability_coverage: dict,
    files: dict[str, bytes],
) -> dict:
    """Build the canonical, fully verifiable package manifest."""
    return {
        "format": SOLIDWORKS_PACKAGE_FORMAT,
        "version": SOLIDWORKS_PACKAGE_VERSION,
        "native_output": native_filename,
        "native_result": f"{native_filename}.result.json",
        "requirements": {
            "operating_system": "Windows",
            "solidworks": "Installed and licensed SolidWorks",
            "powershell": "Windows PowerShell 5.1 or newer",
        },
        "replay_plan": {
            "format": replay_plan.format_name,
            "version": replay_plan.format_version,
            "feature_count": len(replay_plan.features),
            "build_order": list(replay_plan.source_build_order),
        },
        "editability": solidworks_package_editability_summary(
            editability_coverage
        ),
        "files": [
            {
                "path": path,
                "sha256": sha256(content).hexdigest(),
                "size_bytes": len(content),
            }
            for path, content in sorted(files.items())
        ],
    }


def solidworks_package_editability_summary(coverage: dict) -> dict:
    """Return the manifest projection of a full editability report."""
    return {
        "numeric_parameter_count": coverage["numeric_source_count"],
        "named_binding_count": coverage["bound_count"],
        "relation_controlled_count": coverage["relation_controlled_count"],
        "derived_geometry_count": coverage["derived_geometry_count"],
        "derived_geometry_parameter_ids": coverage[
            "derived_geometry_parameter_ids"
        ],
        "derived_geometry_parameters": coverage[
            "derived_geometry_parameters"
        ],
        "represented_count": coverage["represented_count"],
        "representation_coverage_ratio": coverage[
            "representation_coverage_ratio"
        ],
        "unsupported_count": len(coverage["unsupported_parameter_ids"]),
        "control_coverage_ratio": coverage["control_coverage_ratio"],
        "unsupported_parameter_ids": coverage["unsupported_parameter_ids"],
        "unsupported_parameters": coverage["unsupported_parameters"],
        "restricted_count": len(coverage["restricted_parameter_ids"]),
        "restricted_parameter_ids": coverage["restricted_parameter_ids"],
        "restricted_parameters": coverage["restricted_parameters"],
    }


def solidworks_package_static_payload(
    native_filename: str,
    editability_coverage: dict,
) -> dict[str, bytes]:
    """Return the canonical launchers, instructions, and replay engine."""
    replay_script_path = Path(__file__).with_name("solidworks_replay.ps1")
    replay_runner_path = Path(__file__).with_name("solidworks_replay_runner.cs")
    missing_assets = [
        path
        for path in (replay_script_path, replay_runner_path)
        if not path.is_file()
    ]
    if missing_assets:
        raise FileNotFoundError(
            "SolidWorks replay assets were not found: "
            + ", ".join(str(path) for path in missing_assets)
        )
    return {
        "README.txt": _readme_text(
            native_filename,
            editability_coverage,
        ).encode("utf-8"),
        "Build-SolidWorks-Part.ps1": _launcher_script(native_filename).encode(
            "utf-8"
        ),
        "Build-SolidWorks-Part.cmd": _cmd_launcher_script().encode("utf-8"),
        "Check-SolidWorks-Setup.cmd": _check_cmd_launcher_script().encode(
            "utf-8"
        ),
        "solidworks_replay.ps1": replay_script_path.read_bytes(),
        "solidworks_replay_runner.cs": replay_runner_path.read_bytes(),
    }


def _safe_package_stem(filename_hint: str, model_data: dict) -> str:
    readable = re.sub(r"[^a-z0-9]+", "-", filename_hint.lower()).strip("-")
    readable = readable[:52].rstrip("-") or "prompt2cad-model"
    model_digest = sha256(
        json.dumps(
            model_data,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:8]
    return f"{readable}-{model_digest}"


def _json_bytes(value: dict) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with ZipFile(
        buffer,
        mode="w",
        compression=ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path, content in sorted(files.items()):
            entry = ZipInfo(path, date_time=_FIXED_ZIP_TIMESTAMP)
            entry.compress_type = ZIP_DEFLATED
            entry.create_system = 3
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, content, compress_type=ZIP_DEFLATED, compresslevel=9)
    return buffer.getvalue()


def _launcher_script(native_filename: str) -> str:
    return dedent(
        f"""
        param(
            [string]$OutputPath = (Join-Path $PSScriptRoot "{native_filename}"),
            [string]$TemplatePath,
            [switch]$Visible,
            [switch]$CheckOnly,
            [switch]$SkipIntegrityCheck
        )

        $ErrorActionPreference = "Stop"
        Set-StrictMode -Version Latest

        function Write-Stage([string]$Message) {{
            Write-Host "[Prompt2CAD] $Message" -ForegroundColor Cyan
        }}

        function Assert-ExactSequence(
            [string]$Label,
            [object[]]$Expected,
            [object[]]$Actual
        ) {{
            $expectedItems = @($Expected)
            $actualItems = @($Actual)
            if ($expectedItems.Count -ne $actualItems.Count) {{
                throw "$Label count does not match the replay plan."
            }}
            for ($index = 0; $index -lt $expectedItems.Count; $index++) {{
                if ([string]$expectedItems[$index] -cne
                    [string]$actualItems[$index]) {{
                    throw "$Label order does not match the replay plan."
                }}
            }}
        }}

        Write-Stage "Checking package files"
        $manifestPath = Join-Path $PSScriptRoot "manifest.json"
        $planPath = Join-Path $PSScriptRoot "solidworks-replay-plan.json"
        $requiredFiles = @(
            $manifestPath,
            $planPath,
            (Join-Path $PSScriptRoot "solidworks_replay.ps1"),
            (Join-Path $PSScriptRoot "solidworks_replay_runner.cs")
        )
        foreach ($requiredFile in $requiredFiles) {{
            if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {{
                throw "Required package file is missing: $requiredFile"
            }}
        }}

        $manifest = Get-Content -LiteralPath $manifestPath -Raw |
            ConvertFrom-Json
        if ($manifest.format -ne "{SOLIDWORKS_PACKAGE_FORMAT}" -or
            [int]$manifest.version -ne {SOLIDWORKS_PACKAGE_VERSION}) {{
            throw "This launcher requires Prompt2ParametricCAD SolidWorks package version {SOLIDWORKS_PACKAGE_VERSION}. Download a fresh package and try again."
        }}
        if (-not $SkipIntegrityCheck.IsPresent) {{
            foreach ($file in $manifest.files) {{
                $path = Join-Path $PSScriptRoot $file.path
                if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {{
                    throw "Integrity check failed; package file is missing: $($file.path)"
                }}
                $actualHash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
                if ($actualHash -ne $file.sha256) {{
                    throw "Integrity check failed for $($file.path). Extract a fresh package and try again."
                }}
            }}
        }}
        $plan = Get-Content -LiteralPath $planPath -Raw | ConvertFrom-Json
        $expectedFeatureNames = @(
            $plan.features | ForEach-Object {{ [string]$_.feature_name }}
        )
        $expectedSketchNames = @(
            $plan.features |
                Where-Object {{ -not [string]::IsNullOrWhiteSpace(
                    [string]$_.sketch_name
                ) }} |
                ForEach-Object {{ [string]$_.sketch_name }}
        )
        $expectedBindings = @(
            $plan.features | ForEach-Object {{ @($_.parameter_bindings) }}
        )
        $expectedParameterIds = @(
            $expectedBindings | ForEach-Object {{ [string]$_.parameter_id }}
        )
        $expectedDimensionCount = @(
            $expectedBindings |
                Where-Object {{ $_.binding_kind -eq "named_dimension" }}
        ).Count
        $expectedHelperNames = @()
        foreach ($feature in @($plan.features)) {{
            if ($feature.support.kind -eq "offset_plane") {{
                $expectedHelperNames += [string]$feature.support.name
            }}
            $pattern = $feature.pattern
            if ($null -eq $pattern) {{
                continue
            }}
            $expectedHelperNames += [string]$pattern.seed_feature_name
            if ($pattern.kind -eq "circular_pattern" -or
                $pattern.kind -eq "linear_pattern") {{
                $expectedHelperNames += [string]$pattern.reference_sketch_name
            }}
            if ($pattern.kind -eq "circular_pattern") {{
                $expectedHelperNames += [string]$pattern.axis_name
            }}
            elseif ($pattern.kind -eq "mirror_pattern") {{
                $expectedHelperNames += [string]$pattern.placement_sketch_name
            }}
        }}
        $expectedReferenceIds = @(
            $plan.features |
                ForEach-Object {{ @($_.publish_references) }} |
                ForEach-Object {{ [string]$_.reference_id }}
        )
        if ([int]$manifest.replay_plan.feature_count -ne
            $expectedFeatureNames.Count -or
            [int]$manifest.editability.named_binding_count -ne
            $expectedParameterIds.Count) {{
            throw "Package manifest does not match its replay plan."
        }}

        if (-not [Environment]::Is64BitProcess) {{
            throw "Use 64-bit Windows PowerShell so it can load the SolidWorks API."
        }}
        if ($null -eq [Type]::GetTypeFromProgID("SldWorks.Application")) {{
            throw "SolidWorks is not registered on this computer. Install and activate SolidWorks, then try again."
        }}

        $OutputPath = [System.IO.Path]::GetFullPath($OutputPath)
        if ([System.IO.Path]::GetExtension($OutputPath) -ne ".SLDPRT") {{
            throw "OutputPath must end in .SLDPRT: $OutputPath"
        }}
        $outputDirectory = [System.IO.Path]::GetDirectoryName($OutputPath)
        if ($outputDirectory) {{
            New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
        }}

        $arguments = @{{
            PlanPath = $planPath
            OutputPath = $OutputPath
        }}
        if ($TemplatePath) {{
            $arguments.TemplatePath = $TemplatePath
        }}
        if ($Visible.IsPresent) {{
            $arguments.Visible = $true
        }}

        if ($CheckOnly.IsPresent) {{
            $arguments.CompileOnly = $true
            Write-Stage "Compiling the SolidWorks replay engine"
            $checkText = (& (Join-Path $PSScriptRoot "solidworks_replay.ps1") @arguments |
                Out-String).Trim()
            try {{
                $check = $checkText | ConvertFrom-Json
            }}
            catch {{
                throw "SolidWorks setup check returned an unreadable result: $checkText"
            }}
            if ($check.status -ne "success" -or -not $check.compile_only -or
                -not $check.plan_validated) {{
                throw "SolidWorks setup check did not report success."
            }}
            Write-Host ""
            Write-Host "SolidWorks setup is ready" -ForegroundColor Green
            Write-Host ("SolidWorks API root: " + $check.solidworks_api_root)
            Write-Host ("Interop version: " + $check.solidworks_interop_version)
            Write-Host "Run Build-SolidWorks-Part.cmd to create the editable part."
            return
        }}

        if (Test-Path -LiteralPath $OutputPath) {{
            throw "Refusing to overwrite existing SolidWorks part: $OutputPath"
        }}
        $resultPath = "$OutputPath.result.json"
        if (Test-Path -LiteralPath $resultPath) {{
            throw "Refusing to overwrite existing verification report: $resultPath"
        }}

        Write-Stage "Building editable SolidWorks part"
        try {{
            $resultText = (& (Join-Path $PSScriptRoot "solidworks_replay.ps1") @arguments |
                Out-String).Trim()
            try {{
                $result = $resultText | ConvertFrom-Json
            }}
            catch {{
                throw "SolidWorks returned an unreadable build result: $resultText"
            }}
            if ($result.status -ne "success" -or -not $result.reopened -or
                -not $result.verification_passed -or
                -not $result.geometry_verification_passed) {{
                throw "SolidWorks did not return a complete verified-build receipt."
            }}
            if ([string]::IsNullOrWhiteSpace([string]$result.output_path)) {{
                throw "SolidWorks verification receipt does not identify an output part."
            }}
            $reportedOutputPath = [System.IO.Path]::GetFullPath(
                [string]$result.output_path
            )
            if ($reportedOutputPath -ne $OutputPath) {{
                throw "SolidWorks verification receipt identifies a different output part."
            }}

            if ([int]$result.feature_count -ne $expectedFeatureNames.Count) {{
                throw "Verified feature count does not match the replay plan."
            }}
            Assert-ExactSequence "Native feature history" `
                $expectedFeatureNames @($result.native_features)
            if ([int]$result.declared_parameter_count -ne
                $expectedParameterIds.Count -or
                [int]$result.verified_parameter_count -ne
                $expectedParameterIds.Count -or
                [int]$result.verified_dimension_count -ne
                $expectedDimensionCount) {{
                throw "Native parameter verification is incomplete."
            }}
            Assert-ExactSequence "Verified parameter identities" `
                $expectedParameterIds @($result.verified_parameter_ids)
            if ([int]$result.declared_helper_count -ne
                $expectedHelperNames.Count -or
                [int]$result.verified_helper_count -ne
                $expectedHelperNames.Count) {{
                throw "Native helper verification is incomplete."
            }}
            Assert-ExactSequence "Verified helper identities" `
                $expectedHelperNames @($result.verified_helper_names)

            if ($null -eq $result.health -or
                [int]$result.health.feature_error_count -ne 0) {{
                throw "SolidWorks reports unhealthy native feature history."
            }}
            Assert-ExactSequence "Feature health records" `
                $expectedFeatureNames @(
                    $result.health.features |
                        ForEach-Object {{ [string]$_.feature_name }}
                )
            Assert-ExactSequence "Sketch health records" `
                $expectedSketchNames @(
                    $result.health.sketches |
                        ForEach-Object {{ [string]$_.sketch_name }}
                )
            $invalidFeatures = @(
                $result.health.features | Where-Object {{
                    $null -ne $_.error_code -and
                    [int]$_.error_code -ne 0 -and
                    $_.is_warning -ne $true
                }}
            )
            $invalidSketches = @(
                $result.health.sketches |
                    Where-Object {{ $_.is_valid -ne $true }}
            )
            if ($invalidFeatures.Count -gt 0 -or
                $invalidSketches.Count -gt 0) {{
                throw "SolidWorks reports unhealthy native features or sketches."
            }}

            $actualReferences = @($result.published_references)
            Assert-ExactSequence "Persistent reference identities" `
                $expectedReferenceIds @(
                    $actualReferences |
                        ForEach-Object {{ [string]$_.reference_id }}
                )
            $invalidReferences = @(
                $actualReferences | Where-Object {{
                    $_.resolved -ne $true -or
                    [string]::IsNullOrWhiteSpace(
                        [string]$_.persistent_id_base64
                    ) -or
                    [int]$_.resolution_error_code -ne 0
                }}
            )
            $persistentIds = @(
                $actualReferences |
                    ForEach-Object {{ [string]$_.persistent_id_base64 }}
            )
            if ($invalidReferences.Count -gt 0 -or
                @($persistentIds | Select-Object -Unique).Count -ne
                $persistentIds.Count) {{
                throw "Persistent reference verification is incomplete."
            }}

            $temporaryResultPath = (
                "$resultPath.prompt2cad-" +
                [Guid]::NewGuid().ToString("N") + ".tmp"
            )
            try {{
                $result | ConvertTo-Json -Depth 20 |
                    Set-Content -LiteralPath $temporaryResultPath -Encoding UTF8
                Move-Item -LiteralPath $temporaryResultPath `
                    -Destination $resultPath
            }}
            finally {{
                if (Test-Path -LiteralPath $temporaryResultPath) {{
                    Remove-Item -LiteralPath $temporaryResultPath `
                        -Force -ErrorAction SilentlyContinue
                }}
            }}
        }}
        catch {{
            Remove-Item -LiteralPath $OutputPath `
                -Force -ErrorAction SilentlyContinue
            Remove-Item -LiteralPath $resultPath `
                -Force -ErrorAction SilentlyContinue
            throw
        }}
        Write-Host ""
        Write-Host "Created editable SolidWorks part" -ForegroundColor Green
        Write-Host "  Part:   $OutputPath"
        Write-Host "  Report: $resultPath"
        Write-Host "  Features: $($result.feature_count)"
        Write-Host "  Saved file reopened: $($result.reopened)"
        Write-Host "  CadQuery geometry matched: $($result.geometry_verification_passed)"
        Write-Host "  Verified parameters: $($result.verified_parameter_count)"
        Write-Host "  Verified helpers: $($result.verified_helper_count)"
        Write-Host "  Persistent references: $($result.published_references.Count)"
        """
    ).lstrip()


def _cmd_launcher_script() -> str:
    return dedent(
        r"""
        @echo off
        setlocal
        powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Build-SolidWorks-Part.ps1" -Visible
        set "P2P_EXIT_CODE=%ERRORLEVEL%"
        echo.
        if not "%P2P_EXIT_CODE%"=="0" (
          echo Prompt2ParametricCAD could not build the SolidWorks part.
          echo Read the error above, then press any key to close this window.
        ) else (
          echo Build complete. Press any key to close this window.
        )
        pause >nul
        exit /b %P2P_EXIT_CODE%
        """
    ).lstrip()


def _check_cmd_launcher_script() -> str:
    return dedent(
        r"""
        @echo off
        setlocal
        powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Build-SolidWorks-Part.ps1" -CheckOnly
        set "P2P_EXIT_CODE=%ERRORLEVEL%"
        echo.
        if not "%P2P_EXIT_CODE%"=="0" (
          echo SolidWorks setup is not ready.
          echo Read the error above, then press any key to close this window.
        ) else (
          echo Setup check complete. Press any key to close this window.
        )
        pause >nul
        exit /b %P2P_EXIT_CODE%
        """
    ).lstrip()


def _readme_text(native_filename: str, editability_coverage: dict) -> str:
    parameter_count = editability_coverage["numeric_source_count"]
    named_count = editability_coverage["bound_count"]
    relation_count = editability_coverage["relation_controlled_count"]
    derived_count = editability_coverage["derived_geometry_count"]
    unsupported_count = len(
        editability_coverage["unsupported_parameter_ids"]
    )
    restricted_count = len(
        editability_coverage["restricted_parameter_ids"]
    )
    return dedent(
        f"""
        Prompt2ParametricCAD SolidWorks Package v{SOLIDWORKS_PACKAGE_VERSION}
        ==========================================

        This bundle contains the validated feature history used to create the
        STEP model. It does not contain a prebuilt SLDPRT file because native
        SolidWorks files must be created through an installed SolidWorks copy.

        Requirements
        ------------
        - Windows
        - An installed and licensed copy of SolidWorks
        - Windows PowerShell 5.1 or newer

        Editability summary
        -------------------
        - Source numeric parameters: {parameter_count}
        - Named automated edit bindings: {named_count}
        - Zero coordinates held by sketch relations: {relation_count}
        - Derived coordinates retained as native reference geometry: {derived_count}
        - Parameters without automated mutation bindings: {unsupported_count}
        - Coordinate controls limited to their current origin side: {restricted_count}

        Every operation is replayed as native SolidWorks history. The counts
        above distinguish stable automated controls from redundant geometry
        retained in native sketches; they do not prevent normal manual
        feature-tree editing. See editability-coverage.json for the exact
        parameter IDs.
        A side-limited coordinate remains editable in its current direction;
        regenerate the package to move it across or onto the sketch origin.

        Build the editable part
        -----------------------
        1. Extract every file in this ZIP into one folder.
        2. Optional: double-click Check-SolidWorks-Setup.cmd. It checks the
           package and compiles the replay engine without creating a part.
        3. Double-click Build-SolidWorks-Part.cmd.
        4. Keep the window open while SolidWorks creates and verifies the part.

        If more than one SolidWorks version is installed, the setup check
        prints the API folder and interop version it selected. To choose a
        different installation for the current PowerShell window, set:

           $env:P2P_SOLIDWORKS_ROOT = "C:\\Program Files\\SOLIDWORKS Corp\\SOLIDWORKS"

        The runner will not overwrite an existing SLDPRT or verification
        report. Move or rename prior outputs before rebuilding the package.

        PowerShell alternative
        ----------------------
        Open PowerShell in the extracted folder and run:

           powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\Build-SolidWorks-Part.ps1 -Visible

        Expected outputs
        ----------------

           {native_filename}
           {native_filename}.result.json

        Keep the files together. Before opening SolidWorks, the launcher checks
        that the package files match their recorded SHA-256 hashes and that the
        required 64-bit SolidWorks API is available. It then creates named,
        constrained sketches and ordered native features; verifies parameters,
        feature health, and semantic face/edge references; compares the saved
        body's count, volume, surface area, envelope, and center of mass with
        the source CadQuery result; rebuilds; and publishes the SLDPRT from a
        temporary staged file only after those checks pass. The JSON report
        records the verified native result. If any stage fails, the staged file
        is removed, the window identifies the failing condition, and a
        `<part>.SLDPRT.replay.log` file retains the completed stage history for
        troubleshooting. Successful runs remove this diagnostic log. Failed
        retries append a timestamped attempt instead of erasing the preceding
        evidence. No successful native export should be assumed after a
        reported failure.
        """
    ).lstrip()
