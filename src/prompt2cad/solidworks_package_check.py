"""Verify an exported SolidWorks package and its native build evidence."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
import json
import math
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
from zipfile import BadZipFile, ZipFile, ZipInfo

from prompt2cad.editable_model import EditableModelDocument
from prompt2cad.editable_model import model_data_to_editable_document
from prompt2cad.editable_model import rebuild_with_parameter_updates
from prompt2cad.interpreter import build_model
from prompt2cad.solidworks_editability import native_parameter_coverage
from prompt2cad.solidworks_package import SOLIDWORKS_PACKAGE_FORMAT
from prompt2cad.solidworks_package import SOLIDWORKS_PACKAGE_PAYLOAD_FILES
from prompt2cad.solidworks_package import SOLIDWORKS_PACKAGE_VERSION
from prompt2cad.solidworks_package import solidworks_package_editability_summary
from prompt2cad.solidworks_package import solidworks_package_static_payload
from prompt2cad.solidworks_replay import SolidWorksReplayPlan
from prompt2cad.solidworks_replay import build_solidworks_replay_plan
from prompt2cad.solidworks_replay import validate_solidworks_mutations
from prompt2cad.solidworks_verification import compare_geometry_metrics
from prompt2cad.solidworks_verification import geometry_metrics
from prompt2cad.solidworks_verification import validate_native_build_result
from prompt2cad.solidworks_verification import validate_native_editability_result
from prompt2cad.solidworks_verification import validate_published_references


MAX_ARCHIVE_FILES = 32
MAX_ARCHIVE_FILE_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_TOTAL_BYTES = 24 * 1024 * 1024
SOLIDWORKS_MUTATION_FORMAT = "prompt2cad.solidworks-mutations"
SOLIDWORKS_MUTATION_VERSION = 1


@dataclass(frozen=True)
class VerifiedSolidWorksPackage:
    """Reconstructed source of truth for one intact package."""

    root: Path
    manifest: dict
    model_data: dict
    document: EditableModelDocument
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
        document=verified.document,
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
    _validate_native_output_names(manifest)

    model_data = _load_json(root / "source-model.json", "source model")
    document = model_data_to_editable_document(model_data)
    expected_editable_model = _normalized_json(document.to_dict())
    actual_editable_model = _load_json(
        root / "editable-model.json",
        "editable model",
    )
    if not _json_values_equal(actual_editable_model, expected_editable_model):
        raise RuntimeError(
            "Editable model does not match the packaged source model"
        )

    plan = build_solidworks_replay_plan(document)
    actual_plan = _load_json(
        root / "solidworks-replay-plan.json",
        "SolidWorks replay plan",
    )
    if not _json_values_equal(actual_plan, _normalized_json(plan.to_dict())):
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
    if not _json_values_equal(actual_coverage, _normalized_json(coverage)):
        raise RuntimeError(
            "Editability coverage does not match the packaged source model"
        )

    expected_replay_manifest = {
        "format": plan.format_name,
        "version": plan.format_version,
        "feature_count": len(plan.features),
        "build_order": list(plan.source_build_order),
    }
    if not _json_values_equal(
        manifest.get("replay_plan"),
        expected_replay_manifest,
    ):
        raise RuntimeError("Manifest replay metadata does not match the replay plan")
    if not _json_values_equal(
        manifest.get("editability"),
        solidworks_package_editability_summary(coverage),
    ):
        raise RuntimeError(
            "Manifest editability metadata does not match the source model"
        )
    expected_static_payload = solidworks_package_static_payload(
        manifest["native_output"],
        coverage,
    )
    for relative_path, expected_content in expected_static_payload.items():
        actual_content = (root / relative_path).read_bytes()
        if _normalized_text_bytes(actual_content) != _normalized_text_bytes(
            expected_content
        ):
            raise RuntimeError(
                "Package executable or instruction file does not match the "
                f"current release: {relative_path}"
            )

    return VerifiedSolidWorksPackage(
        root=root,
        manifest=manifest,
        model_data=model_data,
        document=document,
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


def propose_solidworks_package_mutation(package_root: Path) -> dict:
    """Select one safe native-bound edit that changes validated geometry."""
    verified = verify_solidworks_package(package_root)
    original_geometry = geometry_metrics(build_model(verified.model_data))
    bindings = {
        binding["parameter_id"]: binding
        for feature in verified.plan.features
        for binding in feature.parameter_bindings
    }
    candidate_ids = sorted(
        bindings,
        key=lambda parameter_id: (
            _mutation_priority(parameter_id, bindings[parameter_id]),
            parameter_id,
        ),
    )
    attempted = 0
    rejected: list[str] = []
    for parameter_id in candidate_ids:
        parameter = verified.document.parameter(parameter_id)
        if parameter is None or isinstance(parameter.value, (bool, str)):
            continue
        binding = bindings[parameter_id]
        for value in _candidate_mutation_values(parameter.value, binding):
            if value == parameter.value:
                continue
            attempted += 1
            mutation = {parameter_id: value}
            try:
                validate_solidworks_mutations(verified.plan, mutation)
                edited_part, _ = rebuild_with_parameter_updates(
                    verified.document,
                    mutation,
                )
                edited_geometry = geometry_metrics(edited_part)
                if not _geometry_materially_changed(
                    original_geometry,
                    edited_geometry,
                ):
                    rejected.append(f"{parameter_id}: geometry did not change")
                    continue
            except Exception as error:
                rejected.append(f"{parameter_id}: {error}")
                continue
            return {
                "format": SOLIDWORKS_MUTATION_FORMAT,
                "version": SOLIDWORKS_MUTATION_VERSION,
                "mutations": [
                    {
                        "parameter_id": parameter_id,
                        "value": value,
                        "unit": binding["unit"],
                    }
                ],
            }

    detail = rejected[-1] if rejected else "no numeric native bindings"
    raise RuntimeError(
        "Could not find a safe geometry-changing native edit after "
        f"{attempted} candidates ({detail})"
    )


def verify_solidworks_package_editability_result(
    package_root: Path,
    mutation_path: Path,
    source_path: Path,
    result_path: Path,
) -> dict:
    """Verify a downloaded part after a native edit and second save/reopen."""
    verified = verify_solidworks_package(package_root)
    mutation_document = _load_json(mutation_path.resolve(), "mutation document")
    mutations = _validated_mutation_document(
        mutation_document,
        verified.plan,
        verified.document,
    )
    expected_edited_part, _ = rebuild_with_parameter_updates(
        verified.document,
        mutations,
    )
    original_geometry = geometry_metrics(build_model(verified.model_data))
    edited_geometry = geometry_metrics(expected_edited_part)
    if not _geometry_materially_changed(original_geometry, edited_geometry):
        raise RuntimeError("Mutation document does not materially change geometry")

    result_path = result_path.resolve()
    native_result = _load_json(result_path, "native SolidWorks edit result")
    expected_source_path = source_path.resolve()
    source_path = _result_sldprt_path(native_result, "source_path", require_file=True)
    output_path = _result_sldprt_path(native_result, "output_path", require_file=True)
    if source_path != expected_source_path:
        raise RuntimeError(
            "Native edit result does not reference the verified source SLDPRT"
        )
    if source_path == output_path:
        raise RuntimeError("Native edit result reused its source output path")
    if Path(f"{output_path}.result.json").resolve() != result_path:
        raise RuntimeError(
            "Native edit result filename does not correspond to its output_path"
        )

    context = "downloaded SolidWorks package edit"
    contract = validate_native_editability_result(
        verified.plan,
        native_result,
        expected_mutation_ids=mutations,
        context=context,
    )
    references = validate_published_references(
        verified.plan,
        native_result,
        context=context,
    )
    before_geometry = native_result.get("before_geometry")
    after_geometry = native_result.get("after_geometry")
    if not isinstance(before_geometry, dict) or not isinstance(after_geometry, dict):
        raise RuntimeError(
            "Native SolidWorks edit result is missing before/after geometry"
        )
    before_comparison = compare_geometry_metrics(
        original_geometry,
        before_geometry,
    )
    after_comparison = compare_geometry_metrics(
        edited_geometry,
        after_geometry,
    )

    return {
        **verified.summary(),
        "verification_scope": "package_native_editability",
        "source_native_output": str(source_path),
        "edited_native_output": str(output_path),
        "mutations": mutations,
        "native_contract": contract,
        "persistent_references": references,
        "before_geometry_comparison": before_comparison,
        "after_geometry_comparison": after_comparison,
    }


def _mutation_priority(parameter_id: str, binding: dict) -> int:
    if binding.get("mutation_mode") == "absolute_same_side":
        return 80
    if ".feature." in parameter_id and binding.get("unit") == "mm":
        return 0
    if ".sketch." in parameter_id and binding.get("unit") == "mm":
        return 10
    if ".pattern.spacing_" in parameter_id:
        return 20
    if binding.get("unit") == "deg":
        return 30
    if binding.get("unit") == "count":
        return 40
    return 60


def _candidate_mutation_values(current, binding: dict) -> tuple[int | float, ...]:
    numeric = float(current)
    if binding.get("integer_only"):
        integer = int(round(numeric))
        return (integer + 1, integer - 1)
    if binding.get("mutation_mode") == "absolute_same_side":
        return (_scaled_value(numeric, 1.1), _scaled_value(numeric, 0.9))
    if abs(numeric) <= 1e-12:
        return (1.0,)
    return (_scaled_value(numeric, 1.1), _scaled_value(numeric, 0.9))


def _scaled_value(value: float, factor: float) -> float:
    """Keep deterministic probes readable without discarding precision."""
    return float(f"{value * factor:.12g}")


def _geometry_materially_changed(before: dict, after: dict) -> bool:
    scalar_pairs = (
        (before["volume_mm3"], after["volume_mm3"]),
        (before["surface_area_mm2"], after["surface_area_mm2"]),
    )
    vector_pairs = (
        (before["bounding_box_mm"], after["bounding_box_mm"]),
        (before["center_of_mass_mm"], after["center_of_mass_mm"]),
    )
    flattened: list[tuple[float, float]] = list(scalar_pairs)
    for before_values, after_values in vector_pairs:
        flattened.extend(zip(before_values, after_values))
    return any(
        abs(float(left) - float(right)) > max(1e-6, abs(float(left)) * 1e-6)
        for left, right in flattened
    )


def _validated_mutation_document(
    document: dict,
    plan: SolidWorksReplayPlan,
    editable_document: EditableModelDocument,
) -> dict[str, int | float]:
    if document.get("format") != SOLIDWORKS_MUTATION_FORMAT:
        raise RuntimeError("Mutation document format is not supported")
    if document.get("version") != SOLIDWORKS_MUTATION_VERSION:
        raise RuntimeError("Mutation document version is not supported")
    records = document.get("mutations")
    if not isinstance(records, list) or not records:
        raise RuntimeError("Mutation document contains no parameter changes")
    bindings = {
        binding["parameter_id"]: binding
        for feature in plan.features
        for binding in feature.parameter_bindings
    }
    mutations: dict[str, int | float] = {}
    for record in records:
        if not isinstance(record, dict):
            raise RuntimeError("Mutation record must be a JSON object")
        parameter_id = record.get("parameter_id")
        if not isinstance(parameter_id, str) or parameter_id not in bindings:
            raise RuntimeError(f"Unknown native mutation parameter: {parameter_id!r}")
        if parameter_id in mutations:
            raise RuntimeError(f"Mutation document repeats {parameter_id}")
        if record.get("unit") != bindings[parameter_id]["unit"]:
            raise RuntimeError(f"Mutation unit does not match {parameter_id}")
        value = record.get("value")
        parameter = editable_document.parameter(parameter_id)
        if parameter is None:
            raise RuntimeError(f"Mutation parameter is absent from {parameter_id}")
        if parameter.value_type in {"pattern_count", "pattern_axis_count"}:
            if isinstance(value, bool) or not isinstance(value, int):
                raise RuntimeError(f"Mutation {parameter_id} requires an integer")
        elif isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RuntimeError(f"Mutation {parameter_id} requires a number")
        mutations[parameter_id] = value
    validate_solidworks_mutations(plan, mutations)
    return mutations


def _result_sldprt_path(
    native_result: dict,
    field_name: str,
    *,
    require_file: bool,
) -> Path:
    value = native_result.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"Native SolidWorks result has no {field_name}")
    path = Path(value).resolve()
    if path.suffix.casefold() != ".sldprt":
        raise RuntimeError(f"Native SolidWorks {field_name} must end in .SLDPRT")
    if require_file and (not path.is_file() or path.stat().st_size <= 0):
        raise RuntimeError(f"Native SolidWorks {field_name} is missing or empty")
    return path


def _validated_archive_entries(
    entries: list[ZipInfo],
) -> list[tuple[ZipInfo, PurePosixPath]]:
    directory_entries = [entry.filename for entry in entries if entry.is_dir()]
    if directory_entries:
        raise RuntimeError(
            "SolidWorks package must use the flat release layout; unexpected "
            f"directories={directory_entries}"
        )
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


def _json_values_equal(left, right) -> bool:
    """Compare regenerated JSON with tolerance only for numeric kernel noise."""
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(
            float(left),
            float(right),
            rel_tol=1e-10,
            abs_tol=1e-8,
        )
    if isinstance(left, dict) and isinstance(right, dict):
        return set(left) == set(right) and all(
            _json_values_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _json_values_equal(left_value, right_value)
            for left_value, right_value in zip(left, right)
        )
    return type(left) is type(right) and left == right


def _normalized_text_bytes(content: bytes) -> bytes:
    """Ignore checkout line-ending differences in canonical text assets."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise RuntimeError("SolidWorks package text asset is not valid UTF-8") from error
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


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

    mutation_parser = subparsers.add_parser(
        "mutation",
        help="Create one safe geometry-changing native edit probe.",
    )
    mutation_parser.add_argument("--package-root", required=True, type=Path)
    mutation_parser.add_argument("--output", required=True, type=Path)

    edit_parser = subparsers.add_parser(
        "verify-edit",
        help="Verify a native mutation result from an extracted package.",
    )
    edit_parser.add_argument("--package-root", required=True, type=Path)
    edit_parser.add_argument("--mutation", required=True, type=Path)
    edit_parser.add_argument("--source", required=True, type=Path)
    edit_parser.add_argument("--result", required=True, type=Path)
    edit_parser.add_argument("--output", type=Path)
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
        elif args.command == "mutation":
            summary = propose_solidworks_package_mutation(args.package_root)
        elif args.command == "verify-edit":
            summary = verify_solidworks_package_editability_result(
                args.package_root,
                args.mutation,
                args.source,
                args.result,
            )
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
