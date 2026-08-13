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

from prompt2cad.editable_model import model_data_to_editable_document
from prompt2cad.solidworks_editability import native_parameter_coverage
from prompt2cad.solidworks_replay import build_solidworks_replay_plan


SOLIDWORKS_PACKAGE_FORMAT = "prompt2cad.solidworks-package"
SOLIDWORKS_PACKAGE_VERSION = 6
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
    document = model_data_to_editable_document(model_data)
    replay_plan = build_solidworks_replay_plan(document)
    editability_coverage = native_parameter_coverage(
        model_data,
        replay_plan,
        document=document,
    )
    stem = _safe_package_stem(filename_hint, model_data)
    native_filename = f"{stem}.SLDPRT"

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

    files = {
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
        "source-model.json": _json_bytes(model_data),
        "editable-model.json": _json_bytes(document.to_dict()),
        "editability-coverage.json": _json_bytes(editability_coverage),
        "solidworks-replay-plan.json": _json_bytes(replay_plan.to_dict()),
        "solidworks_replay.ps1": replay_script_path.read_bytes(),
        "solidworks_replay_runner.cs": replay_runner_path.read_bytes(),
    }
    manifest = {
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
        "editability": {
            "numeric_parameter_count": editability_coverage[
                "numeric_source_count"
            ],
            "named_binding_count": editability_coverage["bound_count"],
            "relation_controlled_count": editability_coverage[
                "relation_controlled_count"
            ],
            "derived_geometry_count": editability_coverage[
                "derived_geometry_count"
            ],
            "derived_geometry_parameter_ids": editability_coverage[
                "derived_geometry_parameter_ids"
            ],
            "derived_geometry_parameters": editability_coverage[
                "derived_geometry_parameters"
            ],
            "represented_count": editability_coverage["represented_count"],
            "representation_coverage_ratio": editability_coverage[
                "representation_coverage_ratio"
            ],
            "unsupported_count": len(
                editability_coverage["unsupported_parameter_ids"]
            ),
            "control_coverage_ratio": editability_coverage[
                "control_coverage_ratio"
            ],
            "unsupported_parameter_ids": editability_coverage[
                "unsupported_parameter_ids"
            ],
            "unsupported_parameters": editability_coverage[
                "unsupported_parameters"
            ],
            "restricted_count": len(
                editability_coverage["restricted_parameter_ids"]
            ),
            "restricted_parameter_ids": editability_coverage[
                "restricted_parameter_ids"
            ],
            "restricted_parameters": editability_coverage[
                "restricted_parameters"
            ],
        },
        "files": [
            {
                "path": path,
                "sha256": sha256(content).hexdigest(),
                "size_bytes": len(content),
            }
            for path, content in sorted(files.items())
        ],
    }
    files["manifest.json"] = _json_bytes(manifest)

    return SolidWorksPackage(
        filename=(
            f"{stem}-v{SOLIDWORKS_PACKAGE_VERSION}-solidworks.zip"
        ),
        content=_zip_bytes(files),
        manifest=manifest,
    )


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

        Write-Stage "Checking package files"
        $manifestPath = Join-Path $PSScriptRoot "manifest.json"
        $requiredFiles = @(
            $manifestPath,
            (Join-Path $PSScriptRoot "solidworks-replay-plan.json"),
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
            PlanPath = (Join-Path $PSScriptRoot "solidworks-replay-plan.json")
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
            Write-Host "Run Build-SolidWorks-Part.cmd to create the editable part."
            return
        }}

        Write-Stage "Building editable SolidWorks part"
        $resultText = (& (Join-Path $PSScriptRoot "solidworks_replay.ps1") @arguments |
            Out-String).Trim()
        try {{
            $result = $resultText | ConvertFrom-Json
        }}
        catch {{
            throw "SolidWorks returned an unreadable build result: $resultText"
        }}
        if ($result.status -ne "success") {{
            throw "SolidWorks did not report a successful build."
        }}

        $resultPath = "$OutputPath.result.json"
        $result | ConvertTo-Json -Depth 20 |
            Set-Content -LiteralPath $resultPath -Encoding UTF8
        Write-Host ""
        Write-Host "Created editable SolidWorks part" -ForegroundColor Green
        Write-Host "  Part:   $OutputPath"
        Write-Host "  Report: $resultPath"
        Write-Host "  Features: $($result.feature_count)"
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

        The runner will not overwrite an existing SLDPRT. Move or rename the
        prior output before rebuilding the package.

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
        geometry, feature health, and semantic face/edge references; rebuilds;
        and publishes the SLDPRT from a temporary staged file only after those
        checks pass. The JSON report records the verified native result. If any
        stage fails, the staged file is removed, the window identifies the
        failing condition, and no successful native export should be assumed.
        """
    ).lstrip()
