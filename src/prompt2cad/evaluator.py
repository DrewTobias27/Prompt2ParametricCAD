"""Evaluate generated CAD model data against lightweight expected features."""

from dataclasses import dataclass


SPECIAL_EXPECTED_KEYS = {"position_count"}


@dataclass
class EvaluationResult:
    """Result of checking generated model data against one eval case."""

    passed: bool
    failures: list[str]


def count_positions(operation: dict) -> int:
    """Return how many repeated feature positions an operation defines."""
    return len(operation.get("positions", []))


def values_match(actual_value: object, expected_value: object) -> bool:
    """Return whether an actual field value satisfies an expected field value."""
    if isinstance(actual_value, (int, float)) and isinstance(
        expected_value, (int, float)
    ):
        return abs(actual_value - expected_value) < 1e-6

    return actual_value == expected_value


def operation_field_failures(
    operation: dict,
    expected_operation: dict,
    operation_label: str,
) -> list[str]:
    """Return field-level failures for one operation."""
    failures = []

    for key, expected_value in expected_operation.items():
        if key in SPECIAL_EXPECTED_KEYS:
            continue

        actual_value = operation.get(key)
        if not values_match(actual_value, expected_value):
            failures.append(
                f"Expected {operation_label} {key} {expected_value}, "
                f"but found {actual_value}."
            )

    expected_position_count = expected_operation.get("position_count")
    if expected_position_count is not None:
        actual_position_count = count_positions(operation)
        if actual_position_count != expected_position_count:
            failures.append(
                f"Expected {operation_label} position_count "
                f"{expected_position_count}, "
                f"but found {actual_position_count}."
            )

    return failures


def operation_matches_expected(
    operation: dict,
    expected_operation: dict,
) -> bool:
    """Return whether one operation satisfies an expected operation pattern."""
    failures = operation_field_failures(
        operation,
        expected_operation,
        "operation",
    )
    return failures == []


def describe_expected_operation(expected_operation: dict) -> str:
    """Return a compact text description of an expected operation."""
    expected_parts = []

    for key, expected_value in expected_operation.items():
        expected_parts.append(f"{key}={expected_value}")

    return ", ".join(expected_parts)


def get_bounding_box_dimensions(part) -> dict[str, float]:
    """Return the x, y, and z dimensions of a CAD part's bounding box."""
    bounding_box = part.val().BoundingBox()
    return {
        "x": bounding_box.xlen,
        "y": bounding_box.ylen,
        "z": bounding_box.zlen,
    }


def bounding_box_failures(part, expected_bounding_box: dict) -> list[str]:
    """Return failures for bounding box dimensions of a CAD part."""
    failures = []
    actual_bounding_box = get_bounding_box_dimensions(part)

    for axis, expected_value in expected_bounding_box.items():
        actual_value = actual_bounding_box[axis]
        if not values_match(actual_value, expected_value):
            failures.append(
                f"Expected bounding box {axis} {expected_value}, "
                f"but found {actual_value}."
            )

    return failures


def evaluate_model_data(
    model_data: dict,
    eval_case: dict,
    part=None,
) -> EvaluationResult:
    """Evaluate generated model data against one eval case."""
    failures = []
    operations = model_data.get("operations", [])
    expected = eval_case["expected"]

    expected_operation_count = expected.get("operation_count")
    if expected_operation_count is not None:
        actual_operation_count = len(operations)
        if actual_operation_count != expected_operation_count:
            failures.append(
                "Expected "
                f"{expected_operation_count} operations, "
                f"but found {actual_operation_count}."
            )

    if not operations:
        failures.append("Model data has no operations.")
        return EvaluationResult(passed=False, failures=failures)

    base_operation = operations[0]
    expected_base = expected.get("base", {})
    failures.extend(
        operation_field_failures(
            base_operation,
            expected_base,
            "base",
        )
    )

    for expected_operation in expected.get("required_operations", []):
        matching_operation = None

        for operation in operations[1:]:
            if operation_matches_expected(operation, expected_operation):
                matching_operation = operation
                break

        if matching_operation is None:
            failures.append(
                "Missing expected operation: "
                f"{describe_expected_operation(expected_operation)}."
            )

    expected_bounding_box = expected.get("bounding_box")
    if expected_bounding_box is not None:
        if part is None:
            failures.append("Bounding box check requires a built CAD part.")
        else:
            failures.extend(
                bounding_box_failures(
                    part,
                    expected_bounding_box,
                )
            )

    return EvaluationResult(
        passed=len(failures) == 0,
        failures=failures,
    )
