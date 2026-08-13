"""Verify an exported SolidWorks package and its native build evidence."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
from zipfile import BadZipFile, ZipFile, ZipInfo

from prompt2cad.editable_model import model_data_to_editable_document
from prompt2cad.interpreter import build_model
from prompt2cad.solidworks_editability import native_parameter_coverage
from prompt2cad.solidworks_package import SOLIDWORKS_PACKAGE_FORMAT
from prompt2cad.solidworks_package import SOLIDWORKS_PACKAGE_PAYLOAD_FILES
from prompt2cad.solidworks_package import SOLIDWORKS_PACKAGE_VERSION
from prompt2cad.solidworks_package import solidworks_package_editability_summary
from prompt2cad.solidworks_replay import SolidWorksReplayPlan
from prompt2cad.solidworks_replay import build_solidworks_replay_plan
from prompt2cad.solidworks_verification import compare_geometry_metrics
from prompt2cad.solidworks_verification import geometry_metrics
from prompt2cad.solidworks_verification import validate_native_build_result
from prompt2cad.solidworks_verification import validate_published_references


MAX_ARCHIVE_FILES = 32
MAX_ARCHIVE_FILE_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_TOTAL_BYTES = 24 * 1024 * 1024


@dataclass(frozen=True)
class VerifiedSolidWorksPackage:
    """Reconstructed source of truth for one intact package."""

    root: Path
    manifest: dict
    model_data: dict
    plan: SolidWorksReplayPlan

    def summary(self) -> dict:
        return {
            "status": "success",
            "verification_scope": "package",
            "package_format": self.manifest["format"],
            "package_version": self.manifest["version"],
            "payload_file_count": len(self.manifest["files"]),
            "feature_count": len(self.plan.features),
            "build_order": list(self.plan.source_build_order),
        }


def extract_verified_solidworks_package(
    archive_path: Path,
    destination: Path,
) -> VerifiedSolidWorksPackage:
    """Safely extract one package, then verify its complete payload."""
    archive_path = archive_path.resolve()
    destination = destination.resolve()
    if not archive_path.is_file():
        raise RuntimeError(f"SolidWorks package ZIP was not found: {archive_path}")
    if archive_path.suffix.casefold() != ".zip":
        raise RuntimeError("SolidWorks package must be a ZIP file")
    if destination.exists():
        raise RuntimeError(
            f"Refusing to overwrite extraction destination: {destination}"
        )
    if not destination.parent.is_dir():
        raise RuntimeError(
            f"Extraction parent directory does not exist: {destination.parent}"
        )

    try:
        archive = ZipFile(archive_path)
    except BadZipFile as error:
        raise RuntimeError("SolidWorks package is not a readable ZIP file") from error

    with archive:
        entries = _validated_archive_entries(archive.infolist())
        with tempfile.TemporaryDirectory(
            prefix=f".{destination.name}-extracting-",
            dir=destination.parent,
        ) as temporary_directory:
            staging_root = Path(temporary_directory)
            for entry, relative_path in entries:
                output_path = staging_root.joinpath(*relative_path.parts)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as source, output_path.open("wb") as target:
                    shutil.copyfileobj(source, target)
            verified = verify_solidworks_package(staging_root)
            os.replace(staging_root, destination)

    return VerifiedSolidWorksPackage(
        root=destination,
        manifest=verified.manifest,
        model_data=verified.model_data,
        plan=verified.plan,
    )


def verify_solidworks_package(
    package_root: Path,
) -> VerifiedSolidWorksPackage:
    """Verify hashes and regenerate every derived package artifact."""
    root = package_root.resolve()
    if not root.is_dir():
        raise RuntimeError(f"SolidWorks package folder was not found: {root}")

    manifest = _load_json(root / "manifest.json", "package manifest")
    _validate_manifest_identity(manifest)
    _validate_payload_files(root, manifest)

    model_data = _load_json(root / "source-model.json", "source model")
    document = model_data_to_editable_document(model_data)
    expected_editable_model = _normalized_json(document.to_dict())
    actual_editable_model = _load_json(
        root / "editable-model.json",
        "editable model",
    )
    if actual_editable_model != expected_editable_model:
        raise RuntimeError(
            "Editable model does not match the packaged source model"
        )

    plan = build_solidworks_replay_plan(document)
    actual_plan = _load_json(
        root / "solidworks-replay-plan.json",
        "SolidWorks replay plan",
    )
    if actual_plan != _normalized_json(plan.to_dict()):
        raise RuntimeError(
            "SolidWorks replay plan does not match the packaged source model"
        )

    coverage = native_parameter_coverage(
        model_data,
        plan,
        document=document,
    )
    actual_coverage = _load_json(
        root / "editability-coverage.json",
        "editability coverage",
    )
    if actual_coverage != _normalized_json(coverage):
        raise RuntimeError(
            "Editability coverage does not match the packaged source model"
        )

    expected_replay_manifest = {
        "format": plan.format_name,
        "version": plan.format_version,
        "feature_count": len(plan.features),
        "build_order": list(plan.source_build_order),
    }
    if manifest.get("replay_plan") != expected_replay_manifest:
        raise RuntimeError("Manifest replay metadata does not match the replay plan")
    if manifest.get("editability") != solidworks_package_editability_summary(
        coverage
    ):
        raise RuntimeError(
            "Manifest editability metadata does not match the source model"
        )
    _validate_native_output_names(manifest)

    return VerifiedSolidWorksPackage(
        root=root,
        manifest=manifest,
        model_data=model_data,
        plan=plan,
    )


def verify_solidworks_package_result(
    package_root: Path,
    result_path: Path,
) -> dict:
    """Verify an intact package plus the SLDPRT/report produced from it."""
    verified = verify_solidworks_package(package_root)
    result_path = result_path.resolve()
    native_result = _load_json(result_path, "native SolidWorks result")
    output_value = native_result.get("output_path")
    if not isinstance(output_value, str) or not output_value.strip():
        raise RuntimeError("Native SolidWorks result has no output_path")
    native_output = Path(output_value).resolve()
    if native_output.suffix.casefold() != ".sldprt":
        raise RuntimeError("Native SolidWorks output_path must end in .SLDPRT")
    if not native_output.is_file() or native_output.stat().st_size <= 0:
        raise RuntimeError(
            f"Native SolidWorks output is missing or empty: {native_output}"
        )
    expected_result_path = Path(f"{native_output}.result.json").resolve()
    if expected_result_path != result_path:
        raise RuntimeError(
            "Native result filename does not correspond to its output_path"
        )

    context = "downloaded SolidWorks package"
    contract = validate_native_build_result(
        verified.plan,
        native_result,
        context=context,
    )
    references = validate_published_references(
        verified.plan,
        native_result,
        context=context,
    )
    cadquery_geometry = geometry_metrics(build_model(verified.model_data))
    native_geometry = native_result.get("geometry")
    if not isinstance(native_geometry, dict):
        raise RuntimeError("Native SolidWorks result has no geometry report")
    comparison = compare_geometry_metrics(
        cadquery_geometry,
        native_geometry,
    )

    return {
        **verified.summary(),
        "verification_scope": "package_and_native_result",
        "native_output": str(native_output),
        "native_output_size_bytes": native_output.stat().st_size,
        "native_contract": contract,
        "persistent_references": references,
        "geometry_comparison": comparison,
    }


def _validated_archive_entries(
    entries: list[ZipInfo],
) -> list[tuple[ZipInfo, PurePosixPath]]:
    files = [entry for entry in entries if not entry.is_dir()]
    if not files or len(files) > MAX_ARCHIVE_FILES:
        raise RuntimeError(
            f"SolidWorks package contains an invalid file count: {len(files)}"
        )

    expected_names = set(SOLIDWORKS_PACKAGE_PAYLOAD_FILES) | {"manifest.json"}
    names: list[str] = []
    validated: list[tuple[ZipInfo, PurePosixPath]] = []
    total_size = 0
    for entry in files:
        name = entry.filename
        if "\\" in name:
            raise RuntimeError(f"Unsafe ZIP entry path: {name}")
        relative_path = PurePosixPath(name)
        if (
            relative_path.is_absolute()
            or not relative_path.parts
            or any(part in {"", ".", ".."} for part in relative_path.parts)
        ):
            raise RuntimeError(f"Unsafe ZIP entry path: {name}")
        unix_mode = entry.external_attr >> 16
        if unix_mode and stat.S_ISLNK(unix_mode):
            raise RuntimeError(f"Symbolic links are not allowed in package: {name}")
        if entry.flag_bits & 0x1:
            raise RuntimeError(f"Encrypted package files are not supported: {name}")
        if entry.file_size > MAX_ARCHIVE_FILE_BYTES:
            raise RuntimeError(f"Package file is unexpectedly large: {name}")
        total_size += entry.file_size
        if total_size > MAX_ARCHIVE_TOTAL_BYTES:
            raise RuntimeError("SolidWorks package expands beyond the size limit")
        names.append(name)
        validated.append((entry, relative_path))

    if len(set(names)) != len(names):
        raise RuntimeError("SolidWorks package contains duplicate ZIP entries")
    if set(names) != expected_names:
        missing = sorted(expected_names - set(names))
        unexpected = sorted(set(names) - expected_names)
        raise RuntimeError(
            "SolidWorks package payload is incomplete; "
            f"missing={missing}, unexpected={unexpected}"
        )
    return validated


def _validate_manifest_identity(manifest: object) -> None:
    if not isinstance(manifest, dict):
        raise RuntimeError("SolidWorks package manifest must be a JSON object")
    if manifest.get("format") != SOLIDWORKS_PACKAGE_FORMAT:
        raise RuntimeError("SolidWorks package format is not supported")
    if manifest.get("version") != SOLIDWORKS_PACKAGE_VERSION:
        raise RuntimeError(
            "SolidWorks package version is not supported; download a fresh "
            f"v{SOLIDWORKS_PACKAGE_VERSION} package"
        )


def _validate_payload_files(root: Path, manifest: dict) -> None:
    records = manifest.get("files")
    if not isinstance(records, list):
        raise RuntimeError("SolidWorks package manifest has no payload file list")
    expected_paths = set(SOLIDWORKS_PACKAGE_PAYLOAD_FILES)
    actual_paths: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            raise RuntimeError("SolidWorks package file record is invalid")
        relative_path = _safe_manifest_path(record.get("path"))
        path_text = relative_path.as_posix()
        actual_paths.append(path_text)
        payload_path = root.joinpath(*relative_path.parts).resolve()
        if not payload_path.is_relative_to(root) or not payload_path.is_file():
            raise RuntimeError(f"Package payload file is missing: {path_text}")
        content = payload_path.read_bytes()
        if record.get("size_bytes") != len(content):
            raise RuntimeError(f"Package payload size mismatch: {path_text}")
        if record.get("sha256") != sha256(content).hexdigest():
            raise RuntimeError(f"Package payload hash mismatch: {path_text}")

    if len(set(actual_paths)) != len(actual_paths):
        raise RuntimeError("SolidWorks package manifest repeats a payload path")
    if set(actual_paths) != expected_paths:
        missing = sorted(expected_paths - set(actual_paths))
        unexpected = sorted(set(actual_paths) - expected_paths)
        raise RuntimeError(
            "SolidWorks package manifest payload is incomplete; "
            f"missing={missing}, unexpected={unexpected}"
        )


def _safe_manifest_path(value: object) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise RuntimeError(f"Unsafe manifest payload path: {value!r}")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise RuntimeError(f"Unsafe manifest payload path: {value!r}")
    return path


def _validate_native_output_names(manifest: dict) -> None:
    native_output = manifest.get("native_output")
    if (
        not isinstance(native_output, str)
        or Path(native_output).name != native_output
        or Path(native_output).suffix.casefold() != ".sldprt"
    ):
        raise RuntimeError("Manifest native_output must be one safe SLDPRT filename")
    if manifest.get("native_result") != f"{native_output}.result.json":
        raise RuntimeError("Manifest native_result does not match native_output")


def _load_json(path: Path, label: str) -> dict:
    if not path.is_file():
        raise RuntimeError(f"Missing {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not read {label}: {path}") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"{label.capitalize()} must be a JSON object")
    return value


def _normalized_json(value):
    """Compare generated artifacts using their serialized JSON value types."""
    return json.loads(json.dumps(value, sort_keys=True))


def _write_summary(summary: dict, output_path: Path | None) -> None:
    text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if output_path is None:
        print(text, end="")
        return
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    print(f"WROTE {output_path}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify a Prompt2ParametricCAD SolidWorks package.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract_parser = subparsers.add_parser(
        "extract",
        help="Safely extract and verify a downloaded package ZIP.",
    )
    extract_parser.add_argument("--package-zip", required=True, type=Path)
    extract_parser.add_argument("--extract-to", required=True, type=Path)
    extract_parser.add_argument("--output", type=Path)

    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify an extracted package and optional native result.",
    )
    verify_parser.add_argument("--package-root", required=True, type=Path)
    verify_parser.add_argument("--result", type=Path)
    verify_parser.add_argument("--output", type=Path)
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        if args.command == "extract":
            verified = extract_verified_solidworks_package(
                args.package_zip,
                args.extract_to,
            )
            summary = verified.summary()
            summary["extracted_to"] = str(verified.root)
        elif args.result is not None:
            summary = verify_solidworks_package_result(
                args.package_root,
                args.result,
            )
        else:
            summary = verify_solidworks_package(args.package_root).summary()
    except RuntimeError as error:
        raise SystemExit(f"SolidWorks package verification failed: {error}") from error
    _write_summary(summary, args.output)


if __name__ == "__main__":
    main()
