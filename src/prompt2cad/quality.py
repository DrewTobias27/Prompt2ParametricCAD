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


def check_model_quality(model_data: dict | None) -> dict[str, Any]:
    """Run the current quality gate and return a structured report."""
    issues: list[QualityIssue] = []
    issues.extend(check_schema(model_data))
    issues.extend(check_structure(model_data))

    return quality_report(issues)


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


def quality_report(issues: list[QualityIssue]) -> dict[str, Any]:
    """Build a JSON-friendly quality report from issues."""
    issue_dicts = [quality_issue.to_dict() for quality_issue in issues]
    error_count = sum(1 for item in issues if item.severity == "error")
    warning_count = sum(1 for item in issues if item.severity == "warning")

    return {
        "passed": error_count == 0,
        "status": report_status(error_count, warning_count),
        "summary": {
            "errors": error_count,
            "warnings": warning_count,
            "infos": sum(1 for item in issues if item.severity == "info"),
        },
        "issues": issue_dicts,
    }


def report_status(error_count: int, warning_count: int) -> str:
    """Return pass/warning/fail from issue counts."""
    if error_count:
        return "fail"
    if warning_count:
        return "warning"
    return "pass"


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
    args = parser.parse_args()

    with args.model_json.open("r", encoding="utf-8") as file:
        model_data = json.load(file)

    print(json.dumps(check_model_quality(model_data), indent=2))


if __name__ == "__main__":
    main()
