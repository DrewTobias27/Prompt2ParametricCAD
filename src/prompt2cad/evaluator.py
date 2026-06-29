"""Evaluate generated CAD model data against geometry and graph expectations."""

from dataclasses import dataclass

from prompt2cad.interpreter import build_model_with_graph


SPECIAL_EXPECTED_KEYS = {"position_count", "count"}
DEFAULT_TOLERANCE = 1e-6


@dataclass
class EvaluationResult:
    """Result of checking generated model data against one eval case."""

    passed: bool
    failures: list[str]


def count_positions(operation: dict) -> int:
    """Return how many repeated feature positions an operation defines."""
    return len(operation.get("positions", []))


def values_match(
    actual_value: object,
    expected_value: object,
    tolerance: float = DEFAULT_TOLERANCE,
) -> bool:
    """Return whether an actual field value satisfies an expected field value."""
    if isinstance(actual_value, (int, float)) and isinstance(
        expected_value, (int, float)
    ):
        return abs(actual_value - expected_value) <= tolerance

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
    tolerance = expected_bounding_box.get("tolerance", DEFAULT_TOLERANCE)

    for axis, expected_value in expected_bounding_box.items():
        if axis == "tolerance":
            continue

        actual_value = actual_bounding_box[axis]
        if not values_match(actual_value, expected_value, tolerance):
            failures.append(
                f"Expected bounding box {axis} {expected_value}, "
                f"but found {actual_value}."
            )

    return failures


def solid_failures(part, expected_solid: dict) -> list[str]:
    """Return failures for solid-level validity checks."""
    failures = []
    if part is None:
        return ["Solid checks require a built CAD part."]

    solids = part.solids().vals()
    expected_single_solid = expected_solid.get("single_solid")
    if expected_single_solid is True and len(solids) != 1:
        failures.append(
            f"Expected one connected solid, but found {len(solids)}."
        )

    expected_valid = expected_solid.get("valid")
    if expected_valid is True:
        invalid_count = sum(1 for solid in solids if not solid.isValid())
        if invalid_count:
            failures.append(
                f"Expected all solids valid, but found {invalid_count} invalid."
            )

    minimum_volume = expected_solid.get("minimum_volume")
    if minimum_volume is not None:
        actual_volume = sum(solid.Volume() for solid in solids)
        if actual_volume <= minimum_volume:
            failures.append(
                f"Expected volume greater than {minimum_volume}, "
                f"but found {actual_volume}."
            )

    return failures


def volume_failures(part, expected_volume: dict) -> list[str]:
    """Return failures for exact or approximate volume checks."""
    if part is None:
        return ["Volume check requires a built CAD part."]

    expected_value = expected_volume["value"]
    tolerance = expected_volume.get("tolerance", DEFAULT_TOLERANCE)
    actual_value = sum(solid.Volume() for solid in part.solids().vals())

    if values_match(actual_value, expected_value, tolerance):
        return []

    return [
        f"Expected volume {expected_value}, but found {actual_value}."
    ]


def operation_count_failures(
    operations: list[dict],
    expected_counts: list[dict],
) -> list[str]:
    """Return failures for operation count patterns."""
    failures = []

    for expected_count in expected_counts:
        expected_pattern = {
            key: value
            for key, value in expected_count.items()
            if key != "count"
        }
        matching_count = 0
        for operation in operations:
            if operation_matches_expected(operation, expected_pattern):
                matching_count += 1

        expected_value = expected_count["count"]
        if matching_count != expected_value:
            description = describe_expected_operation(expected_pattern)
            failures.append(
                f"Expected {expected_value} operations matching "
                f"{description}, but found {matching_count}."
            )

    return failures


def graph_failures(model_data: dict, expected_graph: dict) -> list[str]:
    """Return failures for feature graph and reference expectations."""
    failures = []
    try:
        _, feature_graph = build_model_with_graph(model_data)
    except Exception as error:
        return [f"Feature graph check failed to build model: {error}"]

    if expected_graph.get("no_validation_warnings") is True:
        if feature_graph.validation_warnings:
            warning_messages = [
                warning.message
                for warning in feature_graph.validation_warnings
            ]
            failures.append(
                "Expected no graph validation warnings, but found: "
                + "; ".join(warning_messages)
            )

    expected_build_order = expected_graph.get("build_order")
    if expected_build_order is not None:
        if feature_graph.build_order != expected_build_order:
            failures.append(
                f"Expected graph build_order {expected_build_order}, "
                f"but found {feature_graph.build_order}."
            )

    for reference_name in expected_graph.get("required_references", []):
        if not feature_graph.registry.has_reference(reference_name):
            failures.append(
                f"Missing required graph reference: {reference_name}."
            )

    for alias, expected_canonical in expected_graph.get("required_aliases", {}).items():
        actual_canonical = feature_graph.registry.resolve_reference_name(alias)
        if actual_canonical != expected_canonical:
            failures.append(
                f"Expected alias {alias} to resolve to {expected_canonical}, "
                f"but found {actual_canonical}."
            )

    for expected_feature in expected_graph.get("features", []):
        feature_id = expected_feature["id"]
        feature_node = feature_graph.get_feature(feature_id)
        if feature_node is None:
            failures.append(f"Missing expected graph feature: {feature_id}.")
            continue

        expected_parent = expected_feature.get("parent_feature_id")
        if (
            expected_parent is not None
            and feature_node.parent_feature_id != expected_parent
        ):
            failures.append(
                f"Expected feature {feature_id} parent {expected_parent}, "
                f"but found {feature_node.parent_feature_id}."
            )

        expected_sketch_profile = expected_feature.get("sketch_profile")
        if expected_sketch_profile is not None:
            if feature_node.sketch is None:
                failures.append(
                    f"Expected feature {feature_id} to have a sketch."
                )
            elif feature_node.sketch.profile != expected_sketch_profile:
                failures.append(
                    f"Expected feature {feature_id} sketch profile "
                    f"{expected_sketch_profile}, but found "
                    f"{feature_node.sketch.profile}."
                )

        for reference_name in expected_feature.get("created_references", []):
            if reference_name not in feature_node.created_references:
                failures.append(
                    f"Expected feature {feature_id} to create reference "
                    f"{reference_name}."
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

    expected_solid = expected.get("solid")
    if expected_solid is not None:
        failures.extend(solid_failures(part, expected_solid))

    expected_volume = expected.get("volume")
    if expected_volume is not None:
        failures.extend(volume_failures(part, expected_volume))

    expected_operation_counts = expected.get("operation_counts", [])
    failures.extend(operation_count_failures(operations, expected_operation_counts))

    expected_graph = expected.get("graph")
    if expected_graph is not None:
        failures.extend(graph_failures(model_data, expected_graph))

    return EvaluationResult(
        passed=len(failures) == 0,
        failures=failures,
    )
