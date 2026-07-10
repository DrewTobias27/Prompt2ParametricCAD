"""Structured quality checks for generated Prompt2ParametricCAD model data.

This module is intended to become the central quality gate for API-generated
CAD JSON.  It starts with deterministic schema and structural checks, and is
designed so later build, geometry, export, and prompt-intent checks can return
the same issue format.
"""

from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from prompt2cad.schema import PROFILE_REQUIRED_FIELDS
from prompt2cad.schema import validate_model_data


BASE_OPERATION_TYPES = {"extrude", "revolve"}
FEATURE_OPERATION_TYPES = {
    "add_extrude",
    "cut",
    "add_revolve",
    "cut_revolve",
    "chamfer",
    "fillet",
}
EDGE_OPERATION_TYPES = {"chamfer", "fillet"}
FACE_OPERATION_TYPES = {"add_extrude", "cut", "add_revolve", "cut_revolve"}
PROFILE_DIMENSION_FIELDS = {
    "rectangle": ["width", "height"],
    "circle": ["diameter"],
    "polygon": ["diameter", "sides"],
}
BASE_TARGETS = {
    "base.top",
    "base.bottom",
    "base.front",
    "base.back",
    "base.left",
    "base.right",
    "base.top_outer_edges",
    "base.bottom_outer_edges",
    "base.vertical_edges",
    "base.all_edges",
}


@dataclass(frozen=True)
class QualityIssue:
    """One structured issue found by a quality check stage."""

    severity: str
    stage: str
    code: str
    title: str
    message: str
    suggestion: str = ""
    operation_number: int | None = None
    operation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly issue dictionary."""
        return asdict(self)


def check_model_quality(
    model_data: dict | None,
    *,
    include_build: bool = False,
    build_succeeded: bool = False,
    build_error: str | None = None,
    built_part: Any | None = None,
    exported_path: str | Path | None = None,
    localize_build_failure: bool = True,
) -> dict[str, Any]:
    """Run the current quality gate and return a structured report."""
    issues: list[QualityIssue] = []
    checked_stages = ["schema", "structure"]
    geometry_summary = None
    issues.extend(check_schema(model_data))
    issues.extend(check_structure(model_data))

    if build_error and not stage_has_errors(issues, "schema"):
        checked_stages.append("build")
        issues.extend(
            build_failure_issues(
                model_data,
                build_error,
                localize_build_failure=localize_build_failure,
            )
        )
    elif build_succeeded:
        checked_stages.append("build")
        if built_part is not None:
            checked_stages.append("geometry")
            geometry_summary = summarize_geometry(built_part)
    elif include_build and model_data is not None and not has_errors(issues):
        checked_stages.append("build")
        try:
            from prompt2cad.interpreter import build_model

            built_part = build_model(model_data)
            checked_stages.append("geometry")
            geometry_summary = summarize_geometry(built_part)
        except Exception as error:
            issues.extend(
                build_failure_issues(
                    model_data,
                    str(error),
                    localize_build_failure=localize_build_failure,
                )
            )

    if exported_path is not None:
        checked_stages.append("export")
        issues.extend(check_exported_path(exported_path))

    return quality_report(
        issues,
        checked_stages,
        geometry_summary=geometry_summary,
    )


def check_schema(model_data: dict | None) -> list[QualityIssue]:
    """Validate model data against the JSON schema."""
    if model_data is None:
        return [
            issue(
                severity="error",
                stage="schema",
                code="missing_model_data",
                title="No model data provided",
                message="There is no CAD JSON to validate.",
                suggestion="Generate or load a model_data object with an operations array.",
            )
        ]

    try:
        validate_model_data(model_data)
    except Exception as error:
        return [
            issue(
                severity="error",
                stage="schema",
                code="schema_validation_failed",
                title="Model data does not match schema",
                message=str(error),
                suggestion="Fix the JSON structure before running build or geometry checks.",
            )
        ]

    return []


def check_structure(model_data: dict | None) -> list[QualityIssue]:
    """Check build-order and operation-level structure."""
    if model_data is None:
        return []

    operations = model_data.get("operations")
    if not isinstance(operations, list) or len(operations) == 0:
        return [
            issue(
                severity="error",
                stage="structure",
                code="missing_operations",
                title="No CAD operations found",
                message="The model does not include a non-empty operations list.",
                suggestion="Start with a base extrude or revolve operation.",
            )
        ]

    issues: list[QualityIssue] = []
    known_feature_ids = {"base"}
    known_targets = set(BASE_TARGETS)
    seen_ids: set[str] = set()

    first_operation = operations[0]
    if not isinstance(first_operation, dict):
        issues.append(
            issue(
                severity="error",
                stage="structure",
                code="operation_not_object",
                title="Operation 1 is not an object",
                message="Each operation should be a JSON object.",
                suggestion="Replace this entry with a valid base operation object.",
                operation_number=1,
            )
        )
        return issues

    if first_operation.get("type") not in BASE_OPERATION_TYPES:
        issues.append(
            issue_for_operation(
                first_operation,
                1,
                severity="error",
                stage="structure",
                code="first_operation_not_base",
                title="First operation is not a base feature",
                message=(
                    f"Operation 1 is '{first_operation.get('type')}', but the first "
                    "operation should create the root solid."
                ),
                suggestion="Start the model with an extrude or revolve operation.",
            )
        )

    for operation_number, operation in enumerate(operations, start=1):
        if not isinstance(operation, dict):
            issues.append(
                issue(
                    severity="error",
                    stage="structure",
                    code="operation_not_object",
                    title=f"Operation {operation_number} is not an object",
                    message="Each operation should be a JSON object.",
                    suggestion="Replace this entry with a valid CAD operation object.",
                    operation_number=operation_number,
                )
            )
            continue

        if operation_number > 1 and operation.get("type") not in FEATURE_OPERATION_TYPES:
            issues.append(
                issue_for_operation(
                    operation,
                    operation_number,
                    severity="error",
                    stage="structure",
                    code="unsupported_feature_type",
                    title=f"Operation {operation_number} uses an unsupported feature type",
                    message=(
                        f"'{operation.get('type')}' is not a supported feature "
                        "operation after the base."
                    ),
                    suggestion=(
                        "Use add_extrude, cut, add_revolve, cut_revolve, "
                        "chamfer, or fillet."
                    ),
                )
            )

        issues.extend(check_operation_id(operation, operation_number, seen_ids))
        issues.extend(
            check_operation_target(
                operation,
                operation_number,
                known_feature_ids,
                known_targets,
            )
        )
        issues.extend(check_operation_dimensions(operation, operation_number))
        issues.extend(check_operation_positions(operation, operation_number))
        register_operation_references(
            operation,
            operation_number,
            known_feature_ids,
            known_targets,
        )

    return issues


def check_operation_id(
    operation: dict[str, Any],
    operation_number: int,
    seen_ids: set[str],
) -> list[QualityIssue]:
    """Check feature id uniqueness and basic naming."""
    operation_id = operation.get("id")
    if not operation_id:
        return []

    issues: list[QualityIssue] = []
    if operation_id in seen_ids:
        issues.append(
            issue_for_operation(
                operation,
                operation_number,
                severity="error",
                stage="structure",
                code="duplicate_feature_id",
                title=f"Operation {operation_number} reuses feature id '{operation_id}'",
                message="Feature ids should be unique so later targets are unambiguous.",
                suggestion="Rename this feature id or merge duplicate operations intentionally.",
            )
        )
    seen_ids.add(operation_id)

    if operation_number == 1 and operation_id != "base":
        issues.append(
            issue_for_operation(
                operation,
                operation_number,
                severity="warning",
                stage="structure",
                code="base_id_not_base",
                title="Base feature id is not 'base'",
                message=(
                    f"The root operation id is '{operation_id}', but most "
                    "targets and examples assume the base id is 'base'."
                ),
                suggestion="Use id: 'base' for the first operation unless there is a specific reason not to.",
            )
        )

    return issues


def check_operation_target(
    operation: dict[str, Any],
    operation_number: int,
    known_feature_ids: set[str],
    known_targets: set[str],
) -> list[QualityIssue]:
    """Check operation target existence and target-kind compatibility."""
    if operation.get("type") in BASE_OPERATION_TYPES:
        return []

    operation_type = operation.get("type")
    target = operation.get("target")
    if not target:
        return [
            issue_for_operation(
                operation,
                operation_number,
                severity="error",
                stage="structure",
                code="missing_target",
                title=f"Operation {operation_number} is missing a target",
                message=f"{operation_type} needs a face or edge-group target.",
                suggestion=target_suggestion(operation_type),
            )
        ]

    issues: list[QualityIssue] = []
    target_owner = str(target).split(".")[0]
    if target_owner not in known_feature_ids:
        issues.append(
            issue_for_operation(
                operation,
                operation_number,
                severity="error",
                stage="structure",
                code="target_before_parent",
                title=f"Operation {operation_number} targets a future or missing feature",
                message=f"{target} is not available before operation {operation_number} runs.",
                suggestion="Move the parent feature earlier or target an already-created feature.",
            )
        )
        return issues

    if target not in known_targets:
        issues.append(
            issue_for_operation(
                operation,
                operation_number,
                severity="warning",
                stage="structure",
                code="unknown_target_reference",
                title=f"Operation {operation_number} targets an unknown reference",
                message=f"{target} is not in the known reference set inferred so far.",
                suggestion=(
                    "Use a registered face or edge group, or add registry "
                    "metadata if this is a valid advanced reference."
                ),
            )
        )

    target_looks_like_edge = "edge" in str(target)
    if operation_type in EDGE_OPERATION_TYPES and not target_looks_like_edge:
        issues.append(
            issue_for_operation(
                operation,
                operation_number,
                severity="warning",
                stage="structure",
                code="edge_operation_targets_face",
                title=f"Operation {operation_number} may need an edge target",
                message=f"{operation_type} usually expects an edge group, but targets {target}.",
                suggestion="Use a target like base.top_outer_edges or feature_1.vertical_edges.",
            )
        )

    if operation_type in FACE_OPERATION_TYPES and target_looks_like_edge:
        issues.append(
            issue_for_operation(
                operation,
                operation_number,
                severity="warning",
                stage="structure",
                code="face_operation_targets_edge",
                title=f"Operation {operation_number} may need a face target",
                message=f"{operation_type} usually starts from a face, but targets {target}.",
                suggestion="Use a target like base.top, base.front, or feature_1.top.",
            )
        )

    return issues


def check_operation_dimensions(
    operation: dict[str, Any],
    operation_number: int,
) -> list[QualityIssue]:
    """Check common dimensions and profile-required fields."""
    issues: list[QualityIssue] = []
    operation_type = operation.get("type")

    if operation_type in {"extrude", "add_extrude"}:
        issues.extend(check_positive_number(operation, "distance", operation_number))
    if operation_type == "cut" and operation.get("depth") != "through":
        issues.extend(check_positive_number(operation, "depth", operation_number))
    if operation_type == "chamfer":
        issues.extend(check_positive_number(operation, "distance", operation_number))
    if operation_type == "fillet":
        issues.extend(check_positive_number(operation, "radius", operation_number))
    if operation_type in {"revolve", "add_revolve", "cut_revolve"}:
        if "angle" in operation:
            issues.extend(check_positive_number(operation, "angle", operation_number))
        issues.extend(check_revolve_axis(operation, operation_number))

    profile = operation.get("profile")
    for field_name in PROFILE_REQUIRED_FIELDS.get(profile, []):
        if field_name == "close":
            continue
        issues.extend(check_required_profile_field(operation, field_name, operation_number))

    for field_name in PROFILE_DIMENSION_FIELDS.get(profile, []):
        issues.extend(check_positive_number(operation, field_name, operation_number))

    return issues


def check_operation_positions(
    operation: dict[str, Any],
    operation_number: int,
) -> list[QualityIssue]:
    """Check positioned sketch instances for add/cut features."""
    if operation.get("type") not in {"add_extrude", "cut"}:
        return []

    positions = operation.get("positions")
    if not isinstance(positions, list) or len(positions) == 0:
        return [
            issue_for_operation(
                operation,
                operation_number,
                severity="warning",
                stage="structure",
                code="missing_positions",
                title=f"Operation {operation_number} has no explicit position",
                message=(
                    f"{operation.get('type')} should usually include at least "
                    "one sketch position on the target face."
                ),
                suggestion="Add positions like [[0, 0]] for centered features.",
            )
        ]

    issues: list[QualityIssue] = []
    for position_index, position in enumerate(positions, start=1):
        if not is_point(position):
            issues.append(
                issue_for_operation(
                    operation,
                    operation_number,
                    severity="error",
                    stage="structure",
                    code="invalid_position",
                    title=f"Operation {operation_number} has an invalid position",
                    message=f"Position {position_index} should be a two-number [x, y] pair.",
                    suggestion="Use positions like [[0, 0], [20, 10]].",
                )
            )

    return issues


def check_required_profile_field(
    operation: dict[str, Any],
    field_name: str,
    operation_number: int,
) -> list[QualityIssue]:
    """Check whether a profile-specific required field exists."""
    value = operation.get(field_name)
    if value not in (None, "") and not (isinstance(value, list) and len(value) == 0):
        return []

    return [
        issue_for_operation(
            operation,
            operation_number,
            severity="error",
            stage="structure",
            code="missing_profile_field",
            title=f"Operation {operation_number} is missing {field_name}",
            message=f"The {operation.get('profile')} profile requires {field_name}.",
            suggestion=f"Add {field_name} to operation {operation_number}.",
        )
    ]


def check_positive_number(
    operation: dict[str, Any],
    field_name: str,
    operation_number: int,
) -> list[QualityIssue]:
    """Check a field is a positive number when present or required by context."""
    value = operation.get(field_name)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return [
            issue_for_operation(
                operation,
                operation_number,
                severity="error",
                stage="structure",
                code="invalid_positive_number",
                title=f"Operation {operation_number} has invalid {field_name}",
                message=(
                    f"{field_name} should be a positive number, but received "
                    f"{json.dumps(value)}."
                ),
                suggestion=f"Set {field_name} to a practical positive dimension.",
            )
        ]

    return []


def check_revolve_axis(
    operation: dict[str, Any],
    operation_number: int,
) -> list[QualityIssue]:
    """Check that a revolved operation has a usable axis."""
    axis_start = operation.get("axis_start")
    axis_end = operation.get("axis_end")
    if not is_point(axis_start) or not is_point(axis_end):
        return [
            issue_for_operation(
                operation,
                operation_number,
                severity="error",
                stage="structure",
                code="missing_revolve_axis",
                title=f"Operation {operation_number} is missing a revolve axis",
                message="Revolved features need axis_start and axis_end points.",
                suggestion="Add axis_start and axis_end as two different 2D points.",
            )
        ]

    if axis_start == axis_end:
        return [
            issue_for_operation(
                operation,
                operation_number,
                severity="error",
                stage="structure",
                code="degenerate_revolve_axis",
                title=f"Operation {operation_number} has a zero-length revolve axis",
                message="axis_start and axis_end cannot be the same point.",
                suggestion="Use two distinct points to define the revolve axis.",
            )
        ]

    return []


def register_operation_references(
    operation: dict[str, Any],
    operation_number: int,
    known_feature_ids: set[str],
    known_targets: set[str],
) -> None:
    """Add references created by this operation to the known target set."""
    operation_id = operation.get("id")
    if not operation_id:
        if operation_number == 1:
            operation_id = "base"
        else:
            return

    known_feature_ids.add(operation_id)
    known_targets.update(
        {
            f"{operation_id}.top",
            f"{operation_id}.bottom",
            f"{operation_id}.top_outer_edges",
            f"{operation_id}.bottom_outer_edges",
            f"{operation_id}.vertical_edges",
            f"{operation_id}.all_edges",
        }
    )

    if operation.get("profile") == "rectangle":
        known_targets.update(
            {
                f"{operation_id}.front",
                f"{operation_id}.back",
                f"{operation_id}.left",
                f"{operation_id}.right",
            }
        )

    if operation.get("type") in {"revolve", "add_revolve"}:
        known_targets.update(
            {
                f"{operation_id}.axis",
                f"{operation_id}.outer_surface",
                f"{operation_id}.start_face",
                f"{operation_id}.end_face",
                f"{operation_id}.end_edges",
            }
        )


def check_exported_path(exported_path: str | Path) -> list[QualityIssue]:
    """Check that an exported artifact exists and is non-empty."""
    path = Path(exported_path)
    if not path.exists():
        return [
            issue(
                severity="error",
                stage="export",
                code="export_file_missing",
                title="STEP export file was not created",
                message=f"Expected exported file at {path}, but it does not exist.",
                suggestion="Check the exporter path and CadQuery export call.",
            )
        ]

    if path.stat().st_size == 0:
        return [
            issue(
                severity="error",
                stage="export",
                code="export_file_empty",
                title="STEP export file is empty",
                message=f"The exported file at {path} exists but has zero bytes.",
                suggestion="Re-run export and verify the built part is valid before writing the STEP file.",
            )
        ]

    return []


def summarize_geometry(part: Any) -> dict[str, Any]:
    """Return measurable geometry facts from a built CadQuery part."""
    shape = part.val()
    bounding_box = shape.BoundingBox()
    solids = part.solids().vals()

    return {
        "solid_count": len(solids),
        "valid_solid_count": sum(1 for solid in solids if solid.isValid()),
        "invalid_solid_count": sum(1 for solid in solids if not solid.isValid()),
        "volume": round_float(sum(solid.Volume() for solid in solids)),
        "bounding_box": {
            "xmin": round_float(bounding_box.xmin),
            "xmax": round_float(bounding_box.xmax),
            "ymin": round_float(bounding_box.ymin),
            "ymax": round_float(bounding_box.ymax),
            "zmin": round_float(bounding_box.zmin),
            "zmax": round_float(bounding_box.zmax),
            "xlen": round_float(bounding_box.xlen),
            "ylen": round_float(bounding_box.ylen),
            "zlen": round_float(bounding_box.zlen),
        },
        "face_count": safe_shape_count(shape, "Faces"),
        "edge_count": safe_shape_count(shape, "Edges"),
    }


def safe_shape_count(shape: Any, method_name: str) -> int | None:
    """Return count for a CadQuery/OCP shape collection when available."""
    try:
        return len(getattr(shape, method_name)())
    except Exception:
        return None


def round_float(value: float, digits: int = 6) -> float:
    """Round float metadata to stable JSON-friendly precision."""
    return round(float(value), digits)


def build_failure_issues(
    model_data: dict | None,
    error_message: str,
    *,
    localize_build_failure: bool,
) -> list[QualityIssue]:
    """Return build failure issues, localized to an operation when possible."""
    if localize_build_failure and model_data is not None:
        localized_issue = localize_build_failure_issue(model_data, error_message)
        if localized_issue is not None:
            return [localized_issue]

    return [
        issue(
            severity="error",
            stage="build",
            code="build_failed",
            title="CadQuery build failed",
            message=error_message,
            suggestion=build_failure_suggestion(error_message),
        )
    ]


def localize_build_failure_issue(
    model_data: dict,
    fallback_error_message: str,
) -> QualityIssue | None:
    """Find the first operation prefix that fails during CadQuery build."""
    operations = model_data.get("operations")
    if not isinstance(operations, list) or len(operations) == 0:
        return None

    try:
        from prompt2cad.interpreter import build_model
    except Exception:
        return None

    for operation_number in range(1, len(operations) + 1):
        prefix_model_data = {"operations": operations[:operation_number]}

        try:
            build_model(prefix_model_data)
        except Exception as error:
            operation = operations[operation_number - 1]
            message = str(error) or fallback_error_message
            if not isinstance(operation, dict):
                return issue(
                    severity="error",
                    stage="build",
                    code="operation_build_failed",
                    title=f"Operation {operation_number} failed during build",
                    message=message,
                    suggestion=build_failure_suggestion(message),
                    operation_number=operation_number,
                )

            return issue_for_operation(
                operation,
                operation_number,
                severity="error",
                stage="build",
                code="operation_build_failed",
                title=f"Operation {operation_number} failed during build",
                message=message,
                suggestion=build_failure_suggestion(message),
            )

    return None


def quality_report(
    issues: list[QualityIssue],
    checked_stages: list[str] | None = None,
    geometry_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a JSON-friendly quality report from issues."""
    issue_dicts = [quality_issue.to_dict() for quality_issue in issues]
    error_count = sum(1 for item in issues if item.severity == "error")
    warning_count = sum(1 for item in issues if item.severity == "warning")
    checked_stages = checked_stages or ["schema", "structure"]

    report = {
        "passed": error_count == 0,
        "status": report_status(error_count, warning_count),
        "stages": stage_statuses(issues, checked_stages),
        "summary": {
            "errors": error_count,
            "warnings": warning_count,
            "infos": sum(1 for item in issues if item.severity == "info"),
        },
        "issues": issue_dicts,
    }
    if geometry_summary is not None:
        report["geometry_summary"] = geometry_summary

    return report


def report_status(error_count: int, warning_count: int) -> str:
    """Return pass/warning/fail from issue counts."""
    if error_count:
        return "fail"
    if warning_count:
        return "warning"
    return "pass"


def stage_statuses(
    issues: list[QualityIssue],
    checked_stages: list[str],
) -> dict[str, str]:
    """Return pass/warning/fail status for each checked stage."""
    statuses: dict[str, str] = {}
    for stage in checked_stages:
        stage_issues = [item for item in issues if item.stage == stage]
        if any(item.severity == "error" for item in stage_issues):
            statuses[stage] = "fail"
        elif any(item.severity == "warning" for item in stage_issues):
            statuses[stage] = "warning"
        else:
            statuses[stage] = "pass"

    return statuses


def has_errors(issues: list[QualityIssue]) -> bool:
    """Return whether any quality issue is an error."""
    return any(item.severity == "error" for item in issues)


def stage_has_errors(issues: list[QualityIssue], stage: str) -> bool:
    """Return whether a quality stage has any error issue."""
    return any(item.stage == stage and item.severity == "error" for item in issues)


def build_failure_suggestion(error_message: str) -> str:
    """Return a concise suggestion for a build error."""
    if "Expected one connected solid" in error_message:
        return "Move or resize added features so they overlap the existing solid, or add connecting material."
    if "target" in error_message and "not found" in error_message:
        return "Use an existing target or create the parent feature before targeting it."
    if "Sketch" in error_message or "arc" in error_message:
        return "Simplify the sketch and ensure it forms one valid closed profile."
    return "Check feature order, targets, dimensions, and whether all additions remain connected."


def issue_for_operation(
    operation: dict[str, Any],
    operation_number: int,
    *,
    severity: str,
    stage: str,
    code: str,
    title: str,
    message: str,
    suggestion: str = "",
) -> QualityIssue:
    """Create an issue attached to an operation."""
    return issue(
        severity=severity,
        stage=stage,
        code=code,
        title=title,
        message=message,
        suggestion=suggestion,
        operation_number=operation_number,
        operation_id=operation.get("id"),
    )


def issue(
    *,
    severity: str,
    stage: str,
    code: str,
    title: str,
    message: str,
    suggestion: str = "",
    operation_number: int | None = None,
    operation_id: str | None = None,
) -> QualityIssue:
    """Create a quality issue."""
    return QualityIssue(
        severity=severity,
        stage=stage,
        code=code,
        title=title,
        message=message,
        suggestion=suggestion,
        operation_number=operation_number,
        operation_id=operation_id,
    )


def target_suggestion(operation_type: str | None) -> str:
    """Suggest a target style for an operation type."""
    if operation_type in EDGE_OPERATION_TYPES:
        return "Use an edge-group target like base.top_outer_edges."
    return "Use a face target like base.top or feature_1.front."


def is_point(value: Any) -> bool:
    """Return whether value is a two-number point."""
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(isinstance(coordinate, (int, float)) for coordinate in value)
    )


def main() -> None:
    """Run a quality check on a model JSON file and print the report."""
    import argparse

    parser = argparse.ArgumentParser(description="Check Prompt2CAD model quality.")
    parser.add_argument("model_json", type=Path, help="Path to model_data JSON.")
    parser.add_argument(
        "--include-build",
        action="store_true",
        help="Run the CadQuery build stage as part of the quality check.",
    )
    parser.add_argument(
        "--exported-path",
        type=Path,
        help="Optional exported STEP path to check for existence and non-empty output.",
    )
    args = parser.parse_args()

    with args.model_json.open("r", encoding="utf-8") as file:
        model_data = json.load(file)

    print(
        json.dumps(
            check_model_quality(
                model_data,
                include_build=args.include_build,
                exported_path=args.exported_path,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
