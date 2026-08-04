"""Check that design intent survives deterministic lowering into CAD operations."""

from __future__ import annotations

import math
from typing import Any

from prompt2cad.design_intent import collapse_aligned_wall_through_cuts


INTENT_OPERATION_TYPES = {
    "extrusion": "add_extrude",
    "cut": "cut",
    "revolved_extrusion": "add_revolve",
    "revolved_cut": "cut_revolve",
}

INTENT_PROFILE_TYPES = {
    "rectangle": "rectangle",
    "circle": "circle",
    "polygon": "polygon",
    "polyline": "polyline",
    "slot": "sketch",
    "rounded_rectangle": "sketch",
}


def evaluate_intent_alignment(
    design_intent: dict[str, Any],
    model_data: dict[str, Any],
) -> dict[str, Any]:
    """Return failures when intent features disappear or change while lowering."""
    design_intent = collapse_aligned_wall_through_cuts(design_intent)
    operations = model_data.get("operations", [])
    operations_by_id = {
        operation.get("id"): operation
        for operation in operations
        if operation.get("id")
    }
    failures: list[str] = []

    base_operation = operations_by_id.get("base")
    if base_operation is None:
        failures.append("The design-intent base did not lower to operation id 'base'.")

    for feature in design_intent.get("features", []):
        feature_id = feature.get("id")
        operation = operations_by_id.get(feature_id)
        if operation is None:
            failures.append(
                f"Intent feature '{feature_id}' did not produce a CAD operation."
            )
            continue

        expected_type = (
            "countersink"
            if feature.get("role") == "countersink"
            else INTENT_OPERATION_TYPES.get(feature.get("operation"))
        )
        if operation.get("type") != expected_type:
            failures.append(
                f"Intent feature '{feature_id}' expected operation type "
                f"'{expected_type}', but lowered to '{operation.get('type')}'."
            )

        expected_profile = (
            None
            if feature.get("role") == "countersink"
            else INTENT_PROFILE_TYPES.get(feature.get("shape"))
        )
        if expected_profile and operation.get("profile") != expected_profile:
            failures.append(
                f"Intent feature '{feature_id}' expected profile "
                f"'{expected_profile}', but lowered to '{operation.get('profile')}'."
            )

        failures.extend(feature_instance_failures(feature, operation))
        placement = feature.get("placement", {})
        if placement.get("type") == "same_as_feature":
            source_feature = placement.get("source_feature")
            source_operation = operations_by_id.get(source_feature)
            if source_operation is None:
                failures.append(
                    f"Intent feature '{feature_id}' inherits positions from "
                    f"missing feature '{source_feature}'."
                )
            elif (
                normalized_positions(operation)
                != normalized_positions(source_operation)
                and not same_feature_local_origin_is_valid(
                    feature,
                    operation,
                    source_operation,
                )
            ):
                failures.append(
                    f"Intent feature '{feature_id}' did not preserve positions "
                    f"from source feature '{source_feature}'."
                )

    for treatment in design_intent.get("edge_treatments", []):
        treatment_id = treatment.get("id")
        operation = operations_by_id.get(treatment_id)
        if operation is None:
            failures.append(
                f"Intent edge treatment '{treatment_id}' did not produce a CAD operation."
            )
            continue
        if operation.get("type") != treatment.get("treatment"):
            failures.append(
                f"Intent edge treatment '{treatment_id}' expected "
                f"'{treatment.get('treatment')}', but lowered to "
                f"'{operation.get('type')}'."
            )

    return {
        "passed": not failures,
        "failures": failures,
    }


def same_feature_local_origin_is_valid(
    feature: dict[str, Any],
    operation: dict[str, Any],
    source_operation: dict[str, Any],
) -> bool:
    """Accept local [0, 0] when a child sketches on its one-instance parent."""
    source_feature = feature.get("placement", {}).get("source_feature")
    target_owner = str(feature.get("target", "")).partition(".")[0]
    return (
        target_owner == source_feature
        and len(normalized_positions(source_operation)) == 1
        and normalized_positions(operation) == [(0.0, 0.0)]
    )


def feature_instance_failures(
    feature: dict[str, Any],
    operation: dict[str, Any],
) -> list[str]:
    """Check placement count and geometry after intent lowering."""
    if operation.get("type") in {"add_revolve", "cut_revolve"}:
        return []

    placement = feature.get("placement", {})
    placement_type = placement.get("type")
    positions = operation.get("positions", [])
    expected_count = expected_instance_count(placement)
    failures: list[str] = []

    if expected_count is not None and len(positions) != expected_count:
        failures.append(
            f"Intent feature '{feature.get('id')}' placement '{placement_type}' "
            f"expected {expected_count} instance(s), but lowering produced "
            f"{len(positions)}."
        )

    normalized = [tuple(round(float(value), 6) for value in point) for point in positions]
    if len(set(normalized)) != len(normalized):
        failures.append(
            f"Intent feature '{feature.get('id')}' lowered to duplicate positions."
        )

    if placement_type == "circular_pattern" and len(positions) > 1:
        failures.extend(circular_pattern_failures(feature, placement, positions))

    if placement_type == "rectangular_pattern" and positions:
        rows = int(placement.get("rows", 0))
        columns = int(placement.get("columns", 0))
        unique_x = {round(float(point[0]), 6) for point in positions}
        unique_y = {round(float(point[1]), 6) for point in positions}
        if len(unique_x) != columns or len(unique_y) != rows:
            failures.append(
                f"Intent feature '{feature.get('id')}' rectangular pattern "
                f"expected a {rows} by {columns} grid, but produced "
                f"{len(unique_y)} by {len(unique_x)} unique coordinates."
            )

    return failures


def expected_instance_count(placement: dict[str, Any]) -> int | None:
    """Return the instance count implied by a placement object."""
    placement_type = placement.get("type")
    if placement_type in {"centered", "offset_from_edge"}:
        return 1
    if placement_type == "explicit":
        return len(placement.get("positions", []))
    if placement_type in {"near_corners", "circular_pattern"}:
        return int(placement.get("count", 4))
    if placement_type == "rectangular_pattern":
        return int(placement.get("rows", 0)) * int(placement.get("columns", 0))
    if placement_type == "mirrored":
        axes = set(placement.get("axes", []))
        # A mirror is meaningful only when each requested axis creates a new
        # instance. Seeds lying on a mirror axis collapse copies; comparing
        # against the requested 2**N count lets feedback repair that intent.
        return 2 ** len(axes)
    if placement_type == "same_as_feature":
        return None
    return None


def normalized_positions(operation: dict[str, Any]) -> list[tuple[float, float]]:
    """Return stable unordered positions for cross-operation comparison."""
    return sorted(
        (round(float(point[0]), 6), round(float(point[1]), 6))
        for point in operation.get("positions", [])
    )


def circular_pattern_failures(
    feature: dict[str, Any],
    placement: dict[str, Any],
    positions: list[list[float]],
) -> list[str]:
    """Check equal radius and angular spacing for a circular pattern."""
    failures: list[str] = []
    radii = [math.hypot(float(point[0]), float(point[1])) for point in positions]
    radial_tolerance = max(1e-4, max(radii) * 1e-5)
    if max(radii) - min(radii) > radial_tolerance:
        failures.append(
            f"Intent feature '{feature.get('id')}' circular pattern positions "
            "are not on one common radius."
        )

    angles = sorted(math.atan2(float(point[1]), float(point[0])) for point in positions)
    gaps = [
        (angles[(index + 1) % len(angles)] - angle) % (2 * math.pi)
        for index, angle in enumerate(angles)
    ]
    expected_gap = 2 * math.pi / len(positions)
    if any(abs(gap - expected_gap) > 1e-4 for gap in gaps):
        failures.append(
            f"Intent feature '{feature.get('id')}' circular pattern is not "
            "evenly spaced around the origin."
        )

    requested_radius = placement.get("radius")
    if requested_radius is not None and any(
        abs(radius - float(requested_radius)) > radial_tolerance
        for radius in radii
    ):
        failures.append(
            f"Intent feature '{feature.get('id')}' circular pattern did not "
            f"preserve the requested radius {requested_radius}."
        )

    return failures
