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
import math
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
        expected_operation_group_failures(
            operations,
            expected_concepts.get("operation_groups", []),
        )
    )
    failures.extend(
        expected_relationship_failures(
            relationships,
            expected_concepts.get("relationships", []),
        )
    )
    failures.extend(
        expected_operation_relationship_failures(
            operations,
            expected_concepts.get("operation_relationships", []),
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


def expected_operation_group_failures(
    operations: list[dict[str, Any]],
    expected_groups: list[dict[str, Any]],
) -> list[str]:
    """Return failures for aggregate facts about matching operations.

    A generated design may represent repeated geometry as one patterned
    operation or as several single-instance operations. Group checks validate
    the requested semantic result without requiring one particular encoding.
    """
    failures = []
    for group in expected_groups:
        selector = group.get("selector", {})
        matches = [
            operation
            for operation in operations
            if object_matches_expected(operation, selector)
        ]
        label = json.dumps(selector, sort_keys=True)

        if "operation_count" in group and not value_matches(
            len(matches),
            group["operation_count"],
        ):
            failures.append(
                f"Expected operation group {label} to contain "
                f"{group['operation_count']} operations, but found "
                f"{len(matches)}."
            )

        instance_count = sum(operation_instance_count(match) for match in matches)
        if "instance_count" in group and not value_matches(
            instance_count,
            group["instance_count"],
        ):
            failures.append(
                f"Expected operation group {label} to contain "
                f"{group['instance_count']} feature instances, but found "
                f"{instance_count}."
            )

        positions = [
            point
            for match in matches
            for point in match.get("positions", [])
            if isinstance(point, list)
        ]
        if "positions" in group and not value_matches(
            positions,
            group["positions"],
        ):
            failures.append(
                f"Expected operation group {label} positions to match "
                f"{group['positions']}, but found {positions}."
            )

        target_count = len({
            str(match["target"])
            for match in matches
            if match.get("target") is not None
        })
        if "unique_target_count" in group and not value_matches(
            target_count,
            group["unique_target_count"],
        ):
            failures.append(
                f"Expected operation group {label} to use "
                f"{group['unique_target_count']} unique targets, but found "
                f"{target_count}."
            )

        target_parent_count = len({
            str(match["target"]).split(".", 1)[0]
            for match in matches
            if match.get("target") is not None
        })
        if "unique_target_parent_count" in group and not value_matches(
            target_parent_count,
            group["unique_target_parent_count"],
        ):
            failures.append(
                f"Expected operation group {label} to use "
                f"{group['unique_target_parent_count']} unique target parents, "
                f"but found {target_parent_count}."
            )

    return failures


def operation_instance_count(operation: dict[str, Any]) -> int:
    """Return the number of concrete instances represented by an operation."""
    positions = operation.get("positions")
    if isinstance(positions, list) and positions:
        return len(positions)
    return 1


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


def expected_operation_relationship_failures(
    operations: list[dict[str, Any]],
    expected_relationships: list[dict[str, Any]],
) -> list[str]:
    """Return failures for relationships between concrete operations."""
    operations_by_id = {
        operation.get("id"): operation
        for operation in operations
        if operation.get("id")
    }
    failures = []
    for relationship in expected_relationships:
        relationship_type = relationship.get("type")
        feature_refs = relationship.get("features", [])
        referenced = [
            resolve_operation_reference(operations, operations_by_id, feature_ref)
            for feature_ref in feature_refs
        ]
        missing_refs = [
            feature_ref
            for feature_ref, operation in zip(feature_refs, referenced)
            if operation is None
        ]
        if missing_refs:
            failures.append(
                f"Operation relationship '{relationship_type}' references "
                f"missing feature selectors {missing_refs}."
            )
            continue

        if relationship_type == "same_positions":
            tolerance = float(relationship.get("tolerance", 1e-6))
            if not all_positions_match(referenced, tolerance):
                failures.append(
                    f"Expected features {feature_refs} to use the same positions, "
                    "but their instance coordinates differ."
                )
        elif relationship_type == "same_instance_count":
            counts = [len(operation.get("positions", [])) for operation in referenced]
            if len(set(counts)) != 1:
                failures.append(
                    f"Expected features {feature_refs} to have the same instance "
                    f"count, but found {counts}."
                )
        elif relationship_type == "targets_parent":
            feature_ref = relationship.get("feature")
            parent_ref = relationship.get("parent")
            operation = resolve_operation_reference(
                operations,
                operations_by_id,
                feature_ref,
            )
            parent_operation = resolve_operation_reference(
                operations,
                operations_by_id,
                parent_ref,
            )
            expected_parent = (
                parent_operation.get("id") if parent_operation else parent_ref
            )
            actual_target = operation.get("target") if operation else None
            actual_parent = (
                str(actual_target).split(".", 1)[0] if actual_target else None
            )
            if actual_parent != expected_parent:
                failures.append(
                    f"Expected feature '{feature_ref}' to target parent "
                    f"'{expected_parent}', but it targets '{actual_target}'."
                )
        elif relationship_type == "dimension_order":
            smaller_ref = relationship.get("smaller")
            larger_ref = relationship.get("larger")
            field = relationship.get("field")
            smaller = resolve_operation_reference(
                operations,
                operations_by_id,
                smaller_ref,
            )
            larger = resolve_operation_reference(
                operations,
                operations_by_id,
                larger_ref,
            )
            if smaller is None or larger is None:
                failures.append(
                    "Dimension-order relationship could not uniquely resolve "
                    f"'{smaller_ref}' and '{larger_ref}'."
                )
                continue
            smaller_value = smaller.get(field)
            larger_value = larger.get(field)
            if (
                not isinstance(smaller_value, (int, float))
                or not isinstance(larger_value, (int, float))
                or smaller_value >= larger_value
            ):
                failures.append(
                    f"Expected {smaller_ref} {field} to be smaller than "
                    f"{larger_ref} {field}, but found {smaller_value} and "
                    f"{larger_value}."
                )
        elif relationship_type == "circular_pattern_angular_offset":
            if len(referenced) != 2:
                failures.append(
                    "Circular-pattern angular-offset relationships require "
                    "exactly two feature selectors."
                )
                continue
            first_positions = referenced[0].get("positions", [])
            second_positions = referenced[1].get("positions", [])
            expected_offset = float(relationship.get("offset_degrees", 0))
            tolerance = float(relationship.get("tolerance_degrees", 1e-4))
            if not circular_patterns_have_angular_offset(
                first_positions,
                second_positions,
                expected_offset,
                tolerance,
            ):
                failures.append(
                    f"Expected circular patterns {feature_refs} to have a "
                    f"{expected_offset} degree angular offset, but their "
                    "pattern phases differ."
                )
        else:
            failures.append(
                f"Unsupported expected operation relationship '{relationship_type}'."
            )

    return failures


def resolve_operation_reference(
    operations: list[dict[str, Any]],
    operations_by_id: dict[str, dict[str, Any]],
    reference: Any,
) -> dict[str, Any] | None:
    """Resolve an operation by exact id or by a concept-evaluator pattern."""
    if isinstance(reference, str):
        return operations_by_id.get(reference)
    if isinstance(reference, dict):
        matches = [
            operation
            for operation in operations
            if object_matches_expected(operation, reference)
        ]
        return matches[0] if len(matches) == 1 else None
    return None


def all_positions_match(
    operations: list[dict[str, Any]],
    tolerance: float,
) -> bool:
    """Return whether all operations use the same unordered 2D positions."""
    if not operations:
        return True

    def normalized_positions(operation: dict[str, Any]) -> list[tuple[int, int]]:
        scale = 1 / tolerance if tolerance > 0 else 1e6
        return sorted(
            (round(float(point[0]) * scale), round(float(point[1]) * scale))
            for point in operation.get("positions", [])
        )

    first_positions = normalized_positions(operations[0])
    return all(
        normalized_positions(operation) == first_positions
        for operation in operations[1:]
    )


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
            return any(
                value_matches(actual_value, alternative)
                for alternative in expected_value["one_of"]
            )
        if "contains" in expected_value:
            return str(expected_value["contains"]) in str(actual_value)
        if expected_value.get("exists") is True:
            return actual_value is not None
        if expected_value.get("exists") is False:
            return actual_value is None
        if "length" in expected_value:
            if not isinstance(actual_value, (list, tuple, dict, str)):
                return False
            if len(actual_value) != int(expected_value["length"]):
                return False
        if "unique_length" in expected_value:
            if not isinstance(actual_value, (list, tuple)):
                return False
            normalized = [
                tuple(item) if isinstance(item, list) else item
                for item in actual_value
            ]
            if len(set(normalized)) != int(expected_value["unique_length"]):
                return False
        if "circular_pattern" in expected_value:
            if not circular_positions_match(
                actual_value,
                expected_value["circular_pattern"],
            ):
                return False
        if "point_set" in expected_value:
            if not unordered_points_match(
                actual_value,
                expected_value["point_set"],
                float(expected_value.get("tolerance", 1e-6)),
            ):
                return False
        if "approx" in expected_value:
            if actual_value is None:
                return False
            tolerance = expected_value.get("tolerance", 0)
            try:
                return abs(
                    float(actual_value) - float(expected_value["approx"])
                ) <= float(tolerance)
            except (TypeError, ValueError):
                return False
        if "min" in expected_value:
            try:
                if actual_value is None or float(actual_value) < float(
                    expected_value["min"]
                ):
                    return False
            except (TypeError, ValueError):
                return False
        if "max" in expected_value:
            try:
                if actual_value is None or float(actual_value) > float(
                    expected_value["max"]
                ):
                    return False
            except (TypeError, ValueError):
                return False
        matcher_keys = {
            "one_of",
            "contains",
            "exists",
            "approx",
            "tolerance",
            "min",
            "max",
            "length",
            "unique_length",
            "circular_pattern",
            "point_set",
        }
        nested_expectations = {
            key: child_expected
            for key, child_expected in expected_value.items()
            if key not in matcher_keys
        }
        if not nested_expectations:
            return True
        if not isinstance(actual_value, dict):
            return False
        return all(
            value_matches(actual_value.get(key), child_expected)
            for key, child_expected in nested_expectations.items()
        )

    return actual_value == expected_value


def circular_positions_match(
    actual_value: Any,
    expected_pattern: dict[str, Any],
) -> bool:
    """Return whether 2D positions form an evenly spaced circular pattern."""
    if not isinstance(actual_value, list) or not actual_value:
        return False
    if not all(
        isinstance(point, list)
        and len(point) == 2
        and all(isinstance(value, (int, float)) for value in point)
        for point in actual_value
    ):
        return False

    expected_count = expected_pattern.get("count")
    if expected_count is not None and len(actual_value) != int(expected_count):
        return False

    radii = [math.hypot(point[0], point[1]) for point in actual_value]
    tolerance = float(expected_pattern.get("tolerance", 1e-4))
    if max(radii) - min(radii) > tolerance:
        return False

    expected_radius = expected_pattern.get("radius")
    if expected_radius is not None and any(
        abs(radius - float(expected_radius)) > tolerance for radius in radii
    ):
        return False

    if len(actual_value) > 1:
        angles = sorted(math.atan2(point[1], point[0]) for point in actual_value)
        gaps = [
            (angles[(index + 1) % len(angles)] - angle) % (2 * math.pi)
            for index, angle in enumerate(angles)
        ]
        expected_gap = 2 * math.pi / len(actual_value)
        if any(abs(gap - expected_gap) > tolerance for gap in gaps):
            return False

    expected_start_angle = expected_pattern.get("start_angle_degrees")
    if expected_start_angle is not None:
        angle_tolerance = float(
            expected_pattern.get("angle_tolerance_degrees", 1e-4)
        )
        if not any(
            angular_distance_degrees(
                math.degrees(math.atan2(point[1], point[0])),
                float(expected_start_angle),
            )
            <= angle_tolerance
            for point in actual_value
        ):
            return False

    return True


def unordered_points_match(
    actual_value: Any,
    expected_points: Any,
    tolerance: float,
) -> bool:
    """Return whether two 2D point lists match regardless of ordering."""
    if not isinstance(actual_value, list) or not isinstance(expected_points, list):
        return False
    if len(actual_value) != len(expected_points):
        return False
    if not all(is_2d_numeric_point(point) for point in actual_value):
        return False
    if not all(is_2d_numeric_point(point) for point in expected_points):
        return False

    unmatched = list(actual_value)
    for expected_point in expected_points:
        match_index = next(
            (
                index
                for index, actual_point in enumerate(unmatched)
                if math.dist(actual_point, expected_point) <= tolerance
            ),
            None,
        )
        if match_index is None:
            return False
        unmatched.pop(match_index)
    return True


def is_2d_numeric_point(value: Any) -> bool:
    """Return whether a value is a numeric two-dimensional point."""
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(isinstance(coordinate, (int, float)) for coordinate in value)
    )


def circular_patterns_have_angular_offset(
    first_positions: Any,
    second_positions: Any,
    expected_offset_degrees: float,
    tolerance_degrees: float,
) -> bool:
    """Return whether equal-count circular patterns have the expected phase."""
    if not isinstance(first_positions, list) or not isinstance(second_positions, list):
        return False
    if (
        not first_positions
        or len(first_positions) != len(second_positions)
        or not all(is_2d_numeric_point(point) for point in first_positions)
        or not all(is_2d_numeric_point(point) for point in second_positions)
    ):
        return False

    count = len(first_positions)
    period = 360.0 / count
    first_phase = circular_pattern_phase_degrees(first_positions, period)
    second_phase = circular_pattern_phase_degrees(second_positions, period)
    actual_offset = abs(second_phase - first_phase) % period
    actual_offset = min(actual_offset, period - actual_offset)
    expected_offset = abs(expected_offset_degrees) % period
    expected_offset = min(expected_offset, period - expected_offset)
    return abs(actual_offset - expected_offset) <= tolerance_degrees


def circular_pattern_phase_degrees(
    positions: list[list[float]],
    period_degrees: float,
) -> float:
    """Return the repeated angular phase of one evenly spaced pattern."""
    angle = math.degrees(math.atan2(positions[0][1], positions[0][0]))
    return angle % period_degrees


def angular_distance_degrees(first: float, second: float) -> float:
    """Return the smallest unsigned angle between two degree values."""
    difference = abs((first - second) % 360.0)
    return min(difference, 360.0 - difference)
