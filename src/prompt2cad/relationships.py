"""Relationship and constraint checks for CAD model data.

Operations describe how to build geometry. Relationships describe what the
features are supposed to mean relative to each other: centered, inside, smaller
than, connected to, and so on. This module is intentionally conservative. It
checks only relationships that can be inferred safely from the current JSON
representation, and returns explicit failures instead of guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from prompt2cad.feature_graph import FeatureGraph


GEOMETRY_TOLERANCE = 1e-6


@dataclass(frozen=True)
class RelationshipFailure:
    """One failed relationship constraint."""

    relationship_number: int
    relationship_type: str
    feature: str
    reason: str
    suggested_fixes: list[str]
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly failure dictionary."""
        return {
            "relationship_number": self.relationship_number,
            "relationship_type": self.relationship_type,
            "feature": self.feature,
            "reason": self.reason,
            "suggested_fixes": self.suggested_fixes,
            "details": self.details,
        }


def operation_feature_id(operation: dict, operation_number: int) -> str:
    """Return the explicit or generated feature id for an operation."""
    return FeatureGraph.get_operation_feature_id(operation, operation_number)


def operations_by_feature_id(model_data: dict) -> dict[str, dict]:
    """Return operations keyed by their feature ids."""
    return {
        operation_feature_id(operation, operation_number): operation
        for operation_number, operation in enumerate(
            model_data.get("operations", []),
            start=1,
        )
    }


def operation_numbers_by_feature_id(model_data: dict) -> dict[str, int]:
    """Return operation numbers keyed by feature id."""
    return {
        operation_feature_id(operation, operation_number): operation_number
        for operation_number, operation in enumerate(
            model_data.get("operations", []),
            start=1,
        )
    }


def profile_bounds(operation: dict) -> tuple[float, float, float, float] | None:
    """Return the local 2D bounds of a supported operation profile."""
    profile = operation.get("profile")

    if profile == "rectangle":
        return (
            -operation["width"] / 2,
            -operation["height"] / 2,
            operation["width"] / 2,
            operation["height"] / 2,
        )

    if profile == "circle":
        radius = operation["diameter"] / 2
        return (-radius, -radius, radius, radius)

    if profile == "polygon":
        radius = operation["diameter"] / 2
        return (-radius, -radius, radius, radius)

    if profile == "polyline":
        return points_bounds(operation["points"])

    if profile == "sketch":
        points = [operation["start"]]
        for segment in operation["segments"]:
            if segment["type"] == "line":
                points.append(segment["to"])
            elif segment["type"] == "arc":
                points.append(segment["through"])
                points.append(segment["to"])
        return points_bounds(points)

    return None


def points_bounds(points: list[list[float]]) -> tuple[float, float, float, float]:
    """Return a 2D bounding box around points."""
    x_values = [point[0] for point in points]
    y_values = [point[1] for point in points]
    return (
        min(x_values),
        min(y_values),
        max(x_values),
        max(y_values),
    )


def bounds_size(bounds: tuple[float, float, float, float]) -> tuple[float, float]:
    """Return width and height of 2D bounds."""
    min_x, min_y, max_x, max_y = bounds
    return (max_x - min_x, max_y - min_y)


def bounds_center(bounds: tuple[float, float, float, float]) -> tuple[float, float]:
    """Return center of 2D bounds."""
    min_x, min_y, max_x, max_y = bounds
    return ((min_x + max_x) / 2, (min_y + max_y) / 2)


def translate_bounds(
    bounds: tuple[float, float, float, float],
    position: list[float],
) -> tuple[float, float, float, float]:
    """Move local bounds to a positioned operation instance."""
    min_x, min_y, max_x, max_y = bounds
    return (
        min_x + position[0],
        min_y + position[1],
        max_x + position[0],
        max_y + position[1],
    )


def positioned_bounds(operation: dict) -> list[tuple[float, float, float, float]]:
    """Return one 2D bounds box per positioned operation instance."""
    bounds = profile_bounds(operation)
    if bounds is None:
        return []

    positions = operation.get("positions", [[0, 0]])
    return [translate_bounds(bounds, position) for position in positions]


def shrink_bounds(
    bounds: tuple[float, float, float, float],
    margin: float,
) -> tuple[float, float, float, float]:
    """Shrink 2D bounds inward by a margin."""
    min_x, min_y, max_x, max_y = bounds
    return (
        min_x + margin,
        min_y + margin,
        max_x - margin,
        max_y - margin,
    )


def bounds_inside(
    inner_bounds: tuple[float, float, float, float],
    outer_bounds: tuple[float, float, float, float],
) -> bool:
    """Return whether inner bounds are fully inside outer bounds."""
    inner_min_x, inner_min_y, inner_max_x, inner_max_y = inner_bounds
    outer_min_x, outer_min_y, outer_max_x, outer_max_y = outer_bounds
    return (
        inner_min_x >= outer_min_x - GEOMETRY_TOLERANCE
        and inner_min_y >= outer_min_y - GEOMETRY_TOLERANCE
        and inner_max_x <= outer_max_x + GEOMETRY_TOLERANCE
        and inner_max_y <= outer_max_y + GEOMETRY_TOLERANCE
    )


def find_prior_through_cut_containing_feature(
    model_data: dict,
    feature_id: str,
) -> dict[str, Any] | None:
    """Find whether a feature sits fully inside an earlier top through-cut."""
    feature_numbers = operation_numbers_by_feature_id(model_data)
    operations = model_data.get("operations", [])
    feature_number = feature_numbers.get(feature_id)
    if feature_number is None:
        return None

    feature_operation = operations[feature_number - 1]
    if feature_operation.get("type") != "add_extrude":
        return None

    feature_bounds_list = positioned_bounds(feature_operation)
    for cut_number, cut_operation in enumerate(
        operations[: feature_number - 1],
        start=1,
    ):
        if (
            cut_operation.get("type") != "cut"
            or cut_operation.get("target") != feature_operation.get("target")
            or cut_operation.get("depth") != "through"
        ):
            continue

        for cut_bounds in positioned_bounds(cut_operation):
            for feature_bounds in feature_bounds_list:
                if bounds_inside(feature_bounds, cut_bounds):
                    return {
                        "cut_operation_number": cut_number,
                        "cut_feature_id": operation_feature_id(
                            cut_operation,
                            cut_number,
                        ),
                        "cut_bounds": list(cut_bounds),
                        "feature_bounds": list(feature_bounds),
                    }

    return None


def reference_operation(
    relationship: dict,
    operations_by_id: dict[str, dict],
    reference_key: str,
) -> dict | None:
    """Look up a relationship reference operation."""
    reference = relationship.get(reference_key)
    if reference in operations_by_id:
        return operations_by_id[reference]

    if isinstance(reference, str) and "." in reference:
        parent_feature_id = reference.split(".", 1)[0]
        return operations_by_id.get(parent_feature_id)

    return None


def missing_reference_failure(
    relationship: dict,
    relationship_number: int,
    reference_key: str,
) -> RelationshipFailure:
    """Build a standard missing-reference failure."""
    return RelationshipFailure(
        relationship_number=relationship_number,
        relationship_type=relationship["type"],
        feature=relationship["feature"],
        reason=(
            f"Relationship references unknown {reference_key} "
            f"'{relationship.get(reference_key)}'."
        ),
        suggested_fixes=[
            "Use feature ids that exist earlier in the operations list.",
            "Create the referenced parent feature before depending on it.",
        ],
        details={"relationship": relationship},
    )


def validate_centered_on(
    relationship: dict,
    relationship_number: int,
    operations_by_id: dict[str, dict],
) -> RelationshipFailure | None:
    """Validate that a feature is centered on a reference."""
    feature_operation = operations_by_id.get(relationship["feature"])
    reference = reference_operation(relationship, operations_by_id, "reference")
    if feature_operation is None:
        return missing_reference_failure(
            relationship,
            relationship_number,
            "feature",
        )
    if reference is None:
        return missing_reference_failure(
            relationship,
            relationship_number,
            "reference",
        )

    feature_bounds_list = positioned_bounds(feature_operation)
    reference_bounds_list = positioned_bounds(reference)
    if len(feature_bounds_list) != 1 or len(reference_bounds_list) != 1:
        return RelationshipFailure(
            relationship_number=relationship_number,
            relationship_type=relationship["type"],
            feature=relationship["feature"],
            reason="Centered relationships currently require one feature instance and one reference instance.",
            suggested_fixes=[
                "Use one position for centered features.",
                "Use a separate relationship for repeated or patterned features.",
            ],
            details={
                "feature_instance_count": len(feature_bounds_list),
                "reference_instance_count": len(reference_bounds_list),
            },
        )

    feature_center = bounds_center(feature_bounds_list[0])
    reference_center = bounds_center(reference_bounds_list[0])
    tolerance = relationship["tolerance"]
    dx = abs(feature_center[0] - reference_center[0])
    dy = abs(feature_center[1] - reference_center[1])
    if dx <= tolerance and dy <= tolerance:
        return None

    return RelationshipFailure(
        relationship_number=relationship_number,
        relationship_type=relationship["type"],
        feature=relationship["feature"],
        reason=(
            "Feature is not centered on the requested reference in the current "
            "2D workplane bounds."
        ),
        suggested_fixes=[
            "Move the feature position to the reference center.",
            "If the feature is intentionally offset, remove or change the centered_on relationship.",
        ],
        details={
            "feature_center": list(feature_center),
            "reference_center": list(reference_center),
            "dx": dx,
            "dy": dy,
            "tolerance": tolerance,
        },
    )


def validate_inside(
    relationship: dict,
    relationship_number: int,
    operations_by_id: dict[str, dict],
) -> RelationshipFailure | None:
    """Validate that feature bounds are inside container bounds."""
    feature_operation = operations_by_id.get(relationship["feature"])
    container = reference_operation(relationship, operations_by_id, "container")
    if feature_operation is None:
        return missing_reference_failure(
            relationship,
            relationship_number,
            "feature",
        )
    if container is None:
        return missing_reference_failure(
            relationship,
            relationship_number,
            "container",
        )

    container_bounds_list = positioned_bounds(container)
    if not container_bounds_list:
        return RelationshipFailure(
            relationship_number=relationship_number,
            relationship_type=relationship["type"],
            feature=relationship["feature"],
            reason="Could not compute bounds for the requested container.",
            suggested_fixes=[
                "Use a supported profile with measurable 2D bounds.",
                "Use rectangle, circle, polygon, polyline, or sketch profiles.",
            ],
            details={},
        )

    margin = relationship["margin"]
    container_bounds_list = [
        shrink_bounds(container_bounds, margin)
        for container_bounds in container_bounds_list
    ]
    for feature_bounds in positioned_bounds(feature_operation):
        if not any(
            bounds_inside(feature_bounds, container_bounds)
            for container_bounds in container_bounds_list
        ):
            return RelationshipFailure(
                relationship_number=relationship_number,
                relationship_type=relationship["type"],
                feature=relationship["feature"],
                reason="Feature bounds are not fully inside the requested container.",
                suggested_fixes=[
                    "Move the feature toward one of the container instances.",
                    "Reduce the feature size.",
                    "Increase the container size or reduce the requested margin.",
                ],
                details={
                    "feature_bounds": list(feature_bounds),
                    "container_bounds": [
                        list(container_bounds)
                        for container_bounds in container_bounds_list
                    ],
                    "margin": margin,
                },
            )

    return None


def validate_smaller_than(
    relationship: dict,
    relationship_number: int,
    operations_by_id: dict[str, dict],
) -> RelationshipFailure | None:
    """Validate that a feature is proportionally smaller than a reference."""
    feature_operation = operations_by_id.get(relationship["feature"])
    reference = reference_operation(relationship, operations_by_id, "reference")
    if feature_operation is None:
        return missing_reference_failure(
            relationship,
            relationship_number,
            "feature",
        )
    if reference is None:
        return missing_reference_failure(
            relationship,
            relationship_number,
            "reference",
        )

    feature_bounds_list = positioned_bounds(feature_operation)
    reference_bounds_list = positioned_bounds(reference)
    if not feature_bounds_list or not reference_bounds_list:
        return RelationshipFailure(
            relationship_number=relationship_number,
            relationship_type=relationship["type"],
            feature=relationship["feature"],
            reason="Could not compute 2D bounds for smaller_than relationship.",
            suggested_fixes=[
                "Use supported profiles with clear 2D bounds.",
                "Use rectangle, circle, polygon, polyline, or sketch profiles.",
            ],
            details={},
        )

    reference_width, reference_height = bounds_size(reference_bounds_list[0])
    max_width = reference_width * relationship["max_width_fraction"]
    max_height = reference_height * relationship["max_height_fraction"]
    for feature_bounds in feature_bounds_list:
        feature_width, feature_height = bounds_size(feature_bounds)
        if feature_width > max_width or feature_height > max_height:
            return RelationshipFailure(
                relationship_number=relationship_number,
                relationship_type=relationship["type"],
                feature=relationship["feature"],
                reason="Feature is larger than the requested relative size.",
                suggested_fixes=[
                    "Reduce the feature width, height, diameter, or point spread.",
                    "Increase the parent/reference size if the larger feature is intended.",
                    "Relax the max_width_fraction or max_height_fraction relationship.",
                ],
                details={
                    "feature_size": [feature_width, feature_height],
                    "reference_size": [reference_width, reference_height],
                    "max_allowed_size": [max_width, max_height],
                },
            )

    return None


def validate_must_connect(
    relationship: dict,
    relationship_number: int,
    operations_by_id: dict[str, dict],
    model_data: dict,
) -> RelationshipFailure | None:
    """Validate static cases where a feature is known not to connect."""
    feature_operation = operations_by_id.get(relationship["feature"])
    target = reference_operation(relationship, operations_by_id, "to")
    if feature_operation is None:
        return missing_reference_failure(
            relationship,
            relationship_number,
            "feature",
        )
    if target is None:
        return missing_reference_failure(
            relationship,
            relationship_number,
            "to",
        )

    inside_cut = find_prior_through_cut_containing_feature(
        model_data,
        relationship["feature"],
    )
    if inside_cut is None:
        return None

    return RelationshipFailure(
        relationship_number=relationship_number,
        relationship_type=relationship["type"],
        feature=relationship["feature"],
        reason=(
            "Feature is fully inside an earlier through-cut opening, so it "
            "cannot connect to the requested solid without a bridge, rib, or overlap."
        ),
        suggested_fixes=[
            "Add bridge tabs or ribs connecting the feature to the surrounding solid.",
            "Use a blind pocket instead of a through-cut if the center feature should remain attached.",
            "Move or resize the feature so it overlaps existing solid material.",
        ],
        details=inside_cut,
    )


RELATIONSHIP_VALIDATORS = {
    "centered_on": validate_centered_on,
    "inside": validate_inside,
    "smaller_than": validate_smaller_than,
}


def check_relationships(model_data: dict) -> dict[str, Any]:
    """Return pass/fail information for relationship constraints."""
    relationships = model_data.get("relationships", [])
    operations_by_id = operations_by_feature_id(model_data)
    failures = []

    for relationship_number, relationship in enumerate(
        relationships,
        start=1,
    ):
        relationship_type = relationship["type"]
        if relationship_type == "must_connect":
            failure = validate_must_connect(
                relationship,
                relationship_number,
                operations_by_id,
                model_data,
            )
        else:
            failure = RELATIONSHIP_VALIDATORS[relationship_type](
                relationship,
                relationship_number,
                operations_by_id,
            )

        if failure is not None:
            failures.append(failure.to_dict())

    if failures:
        return {
            "passed": False,
            "failure_type": "relationship_constraint_failed",
            "reason": "One or more CAD relationship constraints were not satisfied.",
            "failures": failures,
            "suggested_fixes": [
                "Adjust feature positions, dimensions, or build order to satisfy the stated relationships.",
                "If the relationship does not match the intended part, remove or rewrite that relationship.",
            ],
        }

    return {
        "passed": True,
        "failure_type": None,
        "reason": "Relationship constraints passed.",
        "failures": [],
        "suggested_fixes": [],
    }


def validate_relationships(model_data: dict) -> None:
    """Raise ValueError when relationship constraints fail."""
    result = check_relationships(model_data)
    if result["passed"]:
        return

    first_failure = result["failures"][0]
    raise ValueError(
        "Relationship constraint failed: "
        f"{first_failure['reason']}"
    )
