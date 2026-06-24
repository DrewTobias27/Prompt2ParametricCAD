"""Evaluate generated CAD model data against lightweight expected features."""

from dataclasses import dataclass


@dataclass
class EvaluationResult:
    """Result of checking generated model data against one eval case."""

    passed: bool
    failures: list[str]


def count_positions(operation: dict) -> int:
    """Return how many repeated feature positions an operation defines."""
    return len(operation.get("positions", []))


def operation_matches_expected(
    operation: dict,
    expected_operation: dict,
) -> bool:
    """Return whether one operation satisfies an expected operation pattern."""
    if operation.get("type") != expected_operation.get("type"):
        return False

    if operation.get("profile") != expected_operation.get("profile"):
        return False

    expected_position_count = expected_operation.get("position_count")
    if expected_position_count is not None:
        if count_positions(operation) != expected_position_count:
            return False

    return True


def evaluate_model_data(
    model_data: dict,
    eval_case: dict,
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

    expected_base_type = expected_base.get("type")
    if expected_base_type is not None:
        actual_base_type = base_operation.get("type")
        if actual_base_type != expected_base_type:
            failures.append(
                f"Expected base type {expected_base_type}, "
                f"but found {actual_base_type}."
            )

    expected_base_profile = expected_base.get("profile")
    if expected_base_profile is not None:
        actual_base_profile = base_operation.get("profile")
        if actual_base_profile != expected_base_profile:
            failures.append(
                f"Expected base profile {expected_base_profile}, "
                f"but found {actual_base_profile}."
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
                f"type={expected_operation.get('type')}, "
                f"profile={expected_operation.get('profile')}, "
                f"position_count={expected_operation.get('position_count')}."
            )

    return EvaluationResult(
        passed=len(failures) == 0,
        failures=failures,
    )
