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
from prompt2cad.solidworks_replay import build_solidworks_replay_plan


SOLIDWORKS_PACKAGE_FORMAT = "prompt2cad.solidworks-package"
SOLIDWORKS_PACKAGE_VERSION = 1
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
        "README.txt": _readme_text(native_filename).encode("utf-8"),
        "Build-SolidWorks-Part.ps1": _launcher_script(native_filename).encode(
            "utf-8"
        ),
        "source-model.json": _json_bytes(model_data),
        "editable-model.json": _json_bytes(document.to_dict()),
        "solidworks-replay-plan.json": _json_bytes(replay_plan.to_dict()),
        "solidworks_replay.ps1": replay_script_path.read_bytes(),
        "solidworks_replay_runner.cs": replay_runner_path.read_bytes(),
    }
    manifest = {
        "format": SOLIDWORKS_PACKAGE_FORMAT,
        "version": SOLIDWORKS_PACKAGE_VERSION,
        "native_output": native_filename,
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
        filename=f"{stem}-solidworks.zip",
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
            [switch]$Visible
        )

        $ErrorActionPreference = "Stop"
        Set-StrictMode -Version Latest

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

        & (Join-Path $PSScriptRoot "solidworks_replay.ps1") @arguments
        Write-Host "Created editable SolidWorks part: $OutputPath"
        """
    ).lstrip()


def _readme_text(native_filename: str) -> str:
    return dedent(
        f"""
        Prompt2ParametricCAD SolidWorks Package
        =======================================

        This bundle contains the validated feature history used to create the
        STEP model. It does not contain a prebuilt SLDPRT file because native
        SolidWorks files must be created through an installed SolidWorks copy.

        Requirements
        ------------
        - Windows
        - An installed and licensed copy of SolidWorks
        - Windows PowerShell 5.1 or newer

        Build the editable part
        -----------------------
        1. Extract every file in this ZIP into one folder.
        2. Open PowerShell in that folder.
        3. Run:

           powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\Build-SolidWorks-Part.ps1 -Visible

        The expected output is:

           {native_filename}

        Keep the files together. The launcher validates the replay-plan version,
        opens SolidWorks, creates named sketches and ordered native features,
        rebuilds the model, and saves the SLDPRT file. If replay fails, the
        terminal reports the feature that could not be created and no successful
        native export should be assumed.
        """
    ).lstrip()
