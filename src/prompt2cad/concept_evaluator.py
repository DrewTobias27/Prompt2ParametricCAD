"""Evaluate whether generated CAD model data matches prompt-level concepts.

The normal quality checker answers: "is this valid buildable CAD?"
This module answers the next question: "does the generated model contain the
important ideas the prompt asked for?"

The checks are intentionally concept-level instead of exact fixture-level. A
prompt like "a raised collar in the middle" should not fail just because the
collar is 8 mm wide instead of 10 mm wide, but it should fail if there is no
additive revolved collar operation at all.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class ConceptEvaluationResult:
    """Result of checking model data against expected CAD concepts."""

    passed: bool
    failures: list[str]


def evaluate_model_concepts(
    model_data: dict[str, Any],
    expected_concepts: dict[str, Any],
    geometry_summary: dict[str, Any] | None = None,
) -> ConceptEvaluationResult:
    """Return whether model data satisfies concept-level expectations."""
    if "any_of" in expected_concepts:
        return evaluate_any_concept_alternative(
            model_data,
            expected_concepts["any_of"],
            geometry_summary,
        )

    failures: list[str] = []
    operations = model_data.get("operations", [])
    relationships = model_data.get("relationships", [])

    if expected_base := expected_concepts.get("base"):
        failures.extend(expected_base_failures(operations, expected_base))

    failures.extend(
        operation_count_failures(
            operations,
            expected_concepts.get("operation_counts", {}),
            exact=True,
        )
    )
    failures.extend(
        operation_count_failures(
            operations,
            expected_concepts.get("min_operation_counts", {}),
            exact=False,
        )
    )
    failures.extend(
        expected_operation_failures(
            operations,
            expected_concepts.get("operations", []),
        )
    )
    failures.extend(
        expected_relationship_failures(
            relationships,
            expected_concepts.get("relationships", []),
        )
    )

    if geometry_summary is not None:
        failures.extend(
            expected_geometry_failures(
                geometry_summary,
                expected_concepts.get("geometry", {}),
            )
        )

    return ConceptEvaluationResult(passed=not failures, failures=failures)


def evaluate_any_concept_alternative(
    model_data: dict[str, Any],
    alternatives: list[dict[str, Any]],
    geometry_summary: dict[str, Any] | None,
) -> ConceptEvaluationResult:
    """Return pass when any alternative concept expectation passes."""
    alternative_failures = []
    for index, alternative in enumerate(alternatives, start=1):
        result = evaluate_model_concepts(
            model_data,
            alternative,
            geometry_summary=geometry_summary,
        )
        if result.passed:
            return ConceptEvaluationResult(passed=True, failures=[])
        alternative_failures.append(
            f"Alternative {index} failed: " + " | ".join(result.failures)
        )

    return ConceptEvaluationResult(passed=False, failures=alternative_failures)


def expected_base_failures(
    operations: list[dict[str, Any]],
    expected_base: dict[str, Any],
) -> list[str]:
    """Return failures for the first operation/base expectation."""
    if not operations:
        return ["Expected a base operation, but there are no operations."]

    failures = expected_object_failures(
        operations[0],
        expected_base,
        label="base operation",
    )
    return failures


def operation_count_failures(
    operations: list[dict[str, Any]],
    expected_counts: dict[str, int],
    *,
    exact: bool,
) -> list[str]:
    """Return failures for exact or minimum operation-type counts."""
    failures = []
    for operation_type, expected_count in expected_counts.items():
        actual_count = sum(
            1
            for operation in operations
            if operation.get("type") == operation_type
        )
        if exact and actual_count != expected_count:
            failures.append(
                f"Expected exactly {expected_count} {operation_type} operations, "
                f"but found {actual_count}."
            )
        if not exact and actual_count < expected_count:
            failures.append(
                f"Expected at least {expected_count} {operation_type} operations, "
                f"but found {actual_count}."
            )

    return failures


def expected_operation_failures(
    operations: list[dict[str, Any]],
    expected_operations: list[dict[str, Any]],
) -> list[str]:
    """Return failures for required operation patterns."""
    failures = []
    for expected_operation in expected_operations:
        if not any(
            object_matches_expected(operation, expected_operation)
            for operation in operations
        ):
            failures.append(
                "Missing operation matching "
                + json.dumps(expected_operation, sort_keys=True)
            )

    return failures


def expected_relationship_failures(
    relationships: list[dict[str, Any]],
    expected_relationships: list[dict[str, Any]],
) -> list[str]:
    """Return failures for required relationship patterns."""
    failures = []
    for expected_relationship in expected_relationships:
        if not any(
            object_matches_expected(relationship, expected_relationship)
            for relationship in relationships
        ):
            failures.append(
                "Missing relationship matching "
                + json.dumps(expected_relationship, sort_keys=True)
            )

    return failures


def expected_geometry_failures(
    geometry_summary: dict[str, Any],
    expected_geometry: dict[str, Any],
) -> list[str]:
    """Return failures for bounding-box and solid-count expectations."""
    failures = expected_object_failures(
        geometry_summary,
        {
            key: value
            for key, value in expected_geometry.items()
            if key != "bounding_box"
        },
        label="geometry summary",
    )
    failures.extend(
        expected_object_failures(
            geometry_summary.get("bounding_box", {}),
            expected_geometry.get("bounding_box", {}),
            label="bounding box",
        )
    )
    return failures


def object_matches_expected(
    actual: dict[str, Any],
    expected: dict[str, Any],
) -> bool:
    """Return whether a dict satisfies an expected pattern."""
    return not expected_object_failures(actual, expected, label="object")


def expected_object_failures(
    actual: dict[str, Any],
    expected: dict[str, Any],
    *,
    label: str,
) -> list[str]:
    """Return failures for one expected object pattern."""
    failures = []
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if not value_matches(actual_value, expected_value):
            failures.append(
                f"Expected {label} {key} {expected_value}, "
                f"but found {actual_value}."
            )

    return failures


def value_matches(actual_value: Any, expected_value: Any) -> bool:
    """Return whether an actual value satisfies an expected value or matcher."""
    if isinstance(expected_value, dict):
        if "one_of" in expected_value:
            return actual_value in expected_value["one_of"]
        if "contains" in expected_value:
            return str(expected_value["contains"]) in str(actual_value)
        if expected_value.get("exists") is True:
            return actual_value is not None
        if expected_value.get("exists") is False:
            return actual_value is None
        if "approx" in expected_value:
            if actual_value is None:
                return False
            tolerance = expected_value.get("tolerance", 0)
            return abs(float(actual_value) - float(expected_value["approx"])) <= float(
                tolerance
            )
        if "min" in expected_value and (
            actual_value is None or float(actual_value) < float(expected_value["min"])
        ):
            return False
        if "max" in expected_value and (
            actual_value is None or float(actual_value) > float(expected_value["max"])
        ):
            return False
        return all(
            value_matches((actual_value or {}).get(key), child_expected)
            for key, child_expected in expected_value.items()
        )

    return actual_value == expected_value
