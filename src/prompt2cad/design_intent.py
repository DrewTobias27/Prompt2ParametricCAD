"""Convert higher-level CAD design intent into executable model data.

The normal interpreter wants concrete CAD operations: exact profiles,
positions, targets, depths, and distances. Natural language prompts usually
describe a level above that: "four holes near the corners", "a centered boss",
"a slot on the right side", or "six holes around the center".

This module is the bridge. It lets a model describe relationships and common
feature concepts, then deterministically lowers them into the existing
Prompt2ParametricCAD operation JSON.
"""

from __future__ import annotations

import math
from typing import Any

from jsonschema import ValidationError
from jsonschema import validate


POSITIVE_NUMBER_SCHEMA = {
    "type": "number",
    "exclusiveMinimum": 0,
}

POINT_SCHEMA = {
    "type": "array",
    "items": {"type": "number"},
    "minItems": 2,
    "maxItems": 2,
}

POINTS_SCHEMA = {
    "type": "array",
    "items": POINT_SCHEMA,
    "minItems": 3,
}

OPENAI_NULLABLE_NUMBER_SCHEMA = {
    "type": ["number", "null"],
}

OPENAI_NULLABLE_INTEGER_SCHEMA = {
    "type": ["integer", "null"],
}

OPENAI_NULLABLE_POINTS_SCHEMA = {
    "anyOf": [
        POINTS_SCHEMA,
        {"type": "null"},
    ],
}

OPENAI_ORIENTATION_SCHEMA = {
    "anyOf": [
        {"type": "string", "enum": ["horizontal", "vertical"]},
        {"type": "null"},
    ],
}

OPENAI_DEPTH_SCHEMA = {
    "anyOf": [
        {"type": "string", "enum": ["through"]},
        {"type": "number"},
        {"type": "null"},
    ],
}

PLACEMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": True,
    "properties": {
        "type": {
            "type": "string",
            "enum": [
                "centered",
                "explicit",
                "near_corners",
                "circular_pattern",
                "rectangular_pattern",
                "mirrored",
                "offset_from_edge",
            ],
        },
    },
    "required": ["type"],
}

BASE_INTENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "id": {"type": "string"},
        "profile": {
            "type": "string",
            "enum": [
                "rectangle",
                "circle",
                "polygon",
                "cylinder",
                "half_cylinder",
                "capsule",
            ],
        },
        "width": POSITIVE_NUMBER_SCHEMA,
        "height": POSITIVE_NUMBER_SCHEMA,
        "diameter": POSITIVE_NUMBER_SCHEMA,
        "sides": {"type": "integer", "minimum": 3},
        "thickness": POSITIVE_NUMBER_SCHEMA,
        "length": POSITIVE_NUMBER_SCHEMA,
    },
    "required": ["id", "profile"],
}

FEATURE_INTENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "id": {"type": "string"},
        "operation": {
            "type": "string",
            "enum": ["extrusion", "cut", "revolved_extrusion", "revolved_cut"],
        },
        "target": {"type": "string"},
        "shape": {
            "type": "string",
            "enum": [
                "rectangle",
                "circle",
                "polygon",
                "polyline",
                "slot",
                "rounded_rectangle",
            ],
        },
        "placement": PLACEMENT_SCHEMA,
        "width": POSITIVE_NUMBER_SCHEMA,
        "height": POSITIVE_NUMBER_SCHEMA,
        "diameter": POSITIVE_NUMBER_SCHEMA,
        "sides": {"type": "integer", "minimum": 3},
        "length": POSITIVE_NUMBER_SCHEMA,
        "radius": POSITIVE_NUMBER_SCHEMA,
        "points": POINTS_SCHEMA,
        "orientation": {
            "type": "string",
            "enum": ["horizontal", "vertical"],
        },
        "distance": POSITIVE_NUMBER_SCHEMA,
        "depth": {
            "anyOf": [
                {"type": "string", "enum": ["through"]},
                POSITIVE_NUMBER_SCHEMA,
            ],
        },
    },
    "required": ["id", "operation", "target", "shape", "placement"],
}

EDGE_TREATMENT_INTENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "id": {"type": "string"},
        "treatment": {
            "type": "string",
            "enum": ["chamfer", "fillet"],
        },
        "target_feature": {"type": "string"},
        "edge_selector": {
            "type": "string",
            "enum": [
                "top_outer_edges",
                "bottom_outer_edges",
                "vertical_edges",
                "all_edges",
            ],
        },
        "distance": POSITIVE_NUMBER_SCHEMA,
        "radius": POSITIVE_NUMBER_SCHEMA,
    },
    "required": [
        "id",
        "treatment",
        "target_feature",
        "edge_selector",
    ],
}

DESIGN_INTENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "base": BASE_INTENT_SCHEMA,
        "features": {
            "type": "array",
            "items": FEATURE_INTENT_SCHEMA,
        },
        "edge_treatments": {
            "type": "array",
            "items": EDGE_TREATMENT_INTENT_SCHEMA,
        },
    },
    "required": ["base", "features"],
}

OPENAI_CENTERED_PLACEMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "type": {"type": "string", "enum": ["centered"]},
    },
    "required": ["type"],
}

OPENAI_EXPLICIT_PLACEMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "type": {"type": "string", "enum": ["explicit"]},
        "positions": {
            "type": "array",
            "items": POINT_SCHEMA,
            "minItems": 1,
        },
    },
    "required": ["type", "positions"],
}

OPENAI_NEAR_CORNERS_PLACEMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "type": {"type": "string", "enum": ["near_corners"]},
        "count": {"type": "integer", "minimum": 1, "maximum": 4},
        "margin": OPENAI_NULLABLE_NUMBER_SCHEMA,
    },
    "required": ["type", "count", "margin"],
}

OPENAI_CIRCULAR_PATTERN_PLACEMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "type": {"type": "string", "enum": ["circular_pattern"]},
        "count": {"type": "integer", "minimum": 1},
        "radius": OPENAI_NULLABLE_NUMBER_SCHEMA,
        "margin": OPENAI_NULLABLE_NUMBER_SCHEMA,
        "start_angle_degrees": OPENAI_NULLABLE_NUMBER_SCHEMA,
    },
    "required": ["type", "count", "radius", "margin", "start_angle_degrees"],
}

OPENAI_RECTANGULAR_PATTERN_PLACEMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "type": {"type": "string", "enum": ["rectangular_pattern"]},
        "rows": {"type": "integer", "minimum": 1},
        "columns": {"type": "integer", "minimum": 1},
        "row_spacing": {"type": "number"},
        "column_spacing": {"type": "number"},
        "center": POINT_SCHEMA,
    },
    "required": [
        "type",
        "rows",
        "columns",
        "row_spacing",
        "column_spacing",
        "center",
    ],
}

OPENAI_MIRRORED_PLACEMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "type": {"type": "string", "enum": ["mirrored"]},
        "seed": POINT_SCHEMA,
        "axes": {
            "type": "array",
            "items": {"type": "string", "enum": ["x", "y"]},
            "minItems": 1,
        },
    },
    "required": ["type", "seed", "axes"],
}

OPENAI_OFFSET_FROM_EDGE_PLACEMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "type": {"type": "string", "enum": ["offset_from_edge"]},
        "edge": {
            "type": "string",
            "enum": ["front", "back", "left", "right"],
        },
        "offset": {"type": "number"},
        "along": {"type": "number"},
    },
    "required": ["type", "edge", "offset", "along"],
}

OPENAI_PLACEMENT_SCHEMA = {
    "anyOf": [
        OPENAI_CENTERED_PLACEMENT_SCHEMA,
        OPENAI_EXPLICIT_PLACEMENT_SCHEMA,
        OPENAI_NEAR_CORNERS_PLACEMENT_SCHEMA,
        OPENAI_CIRCULAR_PATTERN_PLACEMENT_SCHEMA,
        OPENAI_RECTANGULAR_PATTERN_PLACEMENT_SCHEMA,
        OPENAI_MIRRORED_PLACEMENT_SCHEMA,
        OPENAI_OFFSET_FROM_EDGE_PLACEMENT_SCHEMA,
    ],
}

OPENAI_BASE_INTENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "id": {"type": "string"},
        "profile": {
            "type": "string",
            "enum": [
                "rectangle",
                "circle",
                "polygon",
                "cylinder",
                "half_cylinder",
                "capsule",
            ],
        },
        "width": OPENAI_NULLABLE_NUMBER_SCHEMA,
        "height": OPENAI_NULLABLE_NUMBER_SCHEMA,
        "diameter": OPENAI_NULLABLE_NUMBER_SCHEMA,
        "sides": OPENAI_NULLABLE_INTEGER_SCHEMA,
        "thickness": OPENAI_NULLABLE_NUMBER_SCHEMA,
        "length": OPENAI_NULLABLE_NUMBER_SCHEMA,
    },
    "required": [
        "id",
        "profile",
        "width",
        "height",
        "diameter",
        "sides",
        "thickness",
        "length",
    ],
}

OPENAI_FEATURE_INTENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "id": {"type": "string"},
        "operation": {
            "type": "string",
            "enum": ["extrusion", "cut", "revolved_extrusion", "revolved_cut"],
        },
        "target": {"type": "string"},
        "shape": {
            "type": "string",
            "enum": [
                "rectangle",
                "circle",
                "polygon",
                "polyline",
                "slot",
                "rounded_rectangle",
            ],
        },
        "placement": OPENAI_PLACEMENT_SCHEMA,
        "width": OPENAI_NULLABLE_NUMBER_SCHEMA,
        "height": OPENAI_NULLABLE_NUMBER_SCHEMA,
        "diameter": OPENAI_NULLABLE_NUMBER_SCHEMA,
        "sides": OPENAI_NULLABLE_INTEGER_SCHEMA,
        "length": OPENAI_NULLABLE_NUMBER_SCHEMA,
        "radius": OPENAI_NULLABLE_NUMBER_SCHEMA,
        "points": OPENAI_NULLABLE_POINTS_SCHEMA,
        "orientation": OPENAI_ORIENTATION_SCHEMA,
        "distance": OPENAI_NULLABLE_NUMBER_SCHEMA,
        "depth": OPENAI_DEPTH_SCHEMA,
    },
    "required": [
        "id",
        "operation",
        "target",
        "shape",
        "placement",
        "width",
        "height",
        "diameter",
        "sides",
        "length",
        "radius",
        "points",
        "orientation",
        "distance",
        "depth",
    ],
}

OPENAI_EDGE_TREATMENT_INTENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "id": {"type": "string"},
        "treatment": {
            "type": "string",
            "enum": ["chamfer", "fillet"],
        },
        "target_feature": {"type": "string"},
        "edge_selector": {
            "type": "string",
            "enum": [
                "top_outer_edges",
                "bottom_outer_edges",
                "vertical_edges",
                "all_edges",
            ],
        },
        "distance": OPENAI_NULLABLE_NUMBER_SCHEMA,
        "radius": OPENAI_NULLABLE_NUMBER_SCHEMA,
    },
    "required": [
        "id",
        "treatment",
        "target_feature",
        "edge_selector",
        "distance",
        "radius",
    ],
}

OPENAI_DESIGN_INTENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "base": OPENAI_BASE_INTENT_SCHEMA,
        "features": {
            "type": "array",
            "items": OPENAI_FEATURE_INTENT_SCHEMA,
        },
        "edge_treatments": {
            "type": "array",
            "items": OPENAI_EDGE_TREATMENT_INTENT_SCHEMA,
        },
    },
    "required": ["base", "features", "edge_treatments"],
}


def validate_design_intent(intent: dict[str, Any]) -> None:
    """Validate high-level design intent before lowering it."""
    try:
        validate(instance=intent, schema=DESIGN_INTENT_SCHEMA)
    except ValidationError as error:
        raise ValueError(
            f"Design intent does not match schema: {error.message}"
        ) from error

    validate_base_dimensions(intent["base"])
    for feature in intent["features"]:
        validate_feature_dimensions(feature)
    for edge_treatment in intent.get("edge_treatments", []):
        validate_edge_treatment_dimensions(edge_treatment)


def intent_to_model_data(intent: dict[str, Any]) -> dict[str, Any]:
    """Lower design intent into executable Prompt2ParametricCAD model data."""
    intent = remove_null_values(intent)
    intent = normalize_intent_references(intent)
    intent = fill_reasonable_missing_dimensions(intent)
    validate_design_intent(intent)

    base = intent["base"]
    operations = [base_operation(base)]
    relationships = []

    for feature in intent["features"]:
        operation = feature_operation(base, feature)
        operations.append(operation)
        relationships.extend(feature_relationships(feature))

    for edge_treatment in intent.get("edge_treatments", []):
        operations.append(edge_treatment_operation(edge_treatment))

    return {
        "operations": operations,
        "relationships": relationships,
    }


def normalize_intent_references(intent: dict[str, Any]) -> dict[str, Any]:
    """Normalize model-friendly intent names into interpreter-friendly names.

    The language model may call the main body "plate", "shaft", or "flange".
    The interpreter expects the base operation id to be "base", so we keep the
    user's semantic description in the feature ids but normalize the structural
    parent id and any references to it.
    """
    base = dict(intent["base"])
    original_base_id = base.get("id", "base")
    base["id"] = "base"

    return {
        **intent,
        "base": base,
        "features": [
            normalize_feature_reference(feature, original_base_id)
            for feature in intent.get("features", [])
        ],
        "edge_treatments": [
            normalize_edge_treatment_reference(edge_treatment, original_base_id)
            for edge_treatment in intent.get("edge_treatments", [])
        ],
    }


def normalize_feature_reference(
    feature: dict[str, Any],
    original_base_id: str,
) -> dict[str, Any]:
    """Return a feature with canonical target names."""
    normalized = dict(feature)
    normalized["target"] = normalize_face_target(
        normalized.get("target", "base.top"),
        original_base_id,
    )
    return normalized


def normalize_edge_treatment_reference(
    edge_treatment: dict[str, Any],
    original_base_id: str,
) -> dict[str, Any]:
    """Return an edge treatment with canonical target feature names."""
    normalized = dict(edge_treatment)
    if normalized.get("target_feature") == original_base_id:
        normalized["target_feature"] = "base"
    return normalized


def normalize_face_target(target: str, original_base_id: str) -> str:
    """Normalize a face-operation target into feature.reference format."""
    if target == "":
        return "base.top"

    if target in {"base", original_base_id}:
        return "base.top"

    if target.startswith(f"{original_base_id}."):
        target = f"base.{target.split('.', 1)[1]}"

    target_aliases = {
        "base.flat": "base.front",
    }
    if target in target_aliases:
        return target_aliases[target]

    return target


def fill_reasonable_missing_dimensions(intent: dict[str, Any]) -> dict[str, Any]:
    """Fill omitted intent dimensions with deterministic base-relative defaults."""
    base = intent["base"]
    features = []
    for feature in intent["features"]:
        filled_feature = dict(feature)
        filled_feature.update(reasonable_feature_dimensions(base, filled_feature))
        features.append(filled_feature)

    return {
        **intent,
        "features": features,
    }


def reasonable_feature_dimensions(
    base: dict[str, Any],
    feature: dict[str, Any],
) -> dict[str, Any]:
    """Return missing feature dimensions inferred from base proportions."""
    base_width, base_height = base_plan_size(base)
    base_depth = base_default_feature_depth(base)
    smaller_base_side = min(base_width, base_height)
    updates = {}

    if feature["shape"] == "circle" and "diameter" not in feature:
        updates["diameter"] = round_to_practical_size(smaller_base_side * 0.13)

    if feature["shape"] == "polygon":
        if "diameter" not in feature:
            updates["diameter"] = round_to_practical_size(smaller_base_side * 0.25)
        if "sides" not in feature:
            updates["sides"] = 6

    if feature["shape"] == "rectangle":
        if "width" not in feature:
            updates["width"] = round_to_practical_size(base_width * 0.2)
        if "height" not in feature:
            updates["height"] = round_to_practical_size(base_height * 0.25)

    if feature["shape"] == "slot":
        if "length" not in feature:
            updates["length"] = round_to_practical_size(base_width * 0.35)
        if "width" not in feature:
            updates["width"] = round_to_practical_size(smaller_base_side * 0.12)
        if "orientation" not in feature:
            updates["orientation"] = "horizontal"

    if feature["shape"] == "rounded_rectangle":
        if "width" not in feature:
            updates["width"] = round_to_practical_size(base_width * 0.3)
        if "height" not in feature:
            updates["height"] = round_to_practical_size(base_height * 0.2)
        if "radius" not in feature:
            smaller_feature_side = min(
                number_value(updates.get("width", feature.get("width", base_width * 0.3))),
                number_value(updates.get("height", feature.get("height", base_height * 0.2))),
            )
            updates["radius"] = round_to_practical_size(smaller_feature_side * 0.2)

    if feature["operation"] == "extrusion" and "distance" not in feature:
        updates["distance"] = round_to_practical_size(base_depth * 1.25)

    if feature["operation"] == "cut" and "depth" not in feature:
        updates["depth"] = "through"

    return updates


def round_to_practical_size(value: float) -> float:
    """Round an inferred dimension to a simple millimeter value."""
    rounded = max(1, round(number_value(value)))
    return round_number(rounded)


def base_operation(base: dict[str, Any]) -> dict[str, Any]:
    """Return the concrete base operation for a base intent."""
    if base["profile"] in {"cylinder", "half_cylinder"}:
        return axial_cylinder_base_operation(base)

    if base["profile"] == "capsule":
        return capsule_base_operation(base)

    operation = {
        "type": "extrude",
        "id": base["id"],
        "plane": "XY",
        "profile": base["profile"],
        "distance": number_value(base["thickness"]),
    }

    if base["profile"] == "rectangle":
        operation["width"] = number_value(base["width"])
        operation["height"] = number_value(base["height"])
    elif base["profile"] == "circle":
        operation["diameter"] = number_value(base["diameter"])
    elif base["profile"] == "polygon":
        operation["diameter"] = number_value(base["diameter"])
        operation["sides"] = int(base["sides"])

    return operation


def axial_cylinder_base_operation(base: dict[str, Any]) -> dict[str, Any]:
    """Return a revolved cylinder or half-cylinder base operation."""
    radius = number_value(base["diameter"]) / 2
    angle = 180 if base["profile"] == "half_cylinder" else 360
    return {
        "type": "revolve",
        "id": base["id"],
        "plane": "XY",
        "profile": "rectangle",
        "positions": [[round_number(radius / 2), 0]],
        "axis_start": [0, -1],
        "axis_end": [0, 1],
        "angle": angle,
        "width": round_number(radius),
        "height": number_value(base["length"]),
    }


def capsule_base_operation(base: dict[str, Any]) -> dict[str, Any]:
    """Return a revolved capsule/rounded-shaft base operation."""
    radius = number_value(base["diameter"]) / 2
    length = number_value(base["length"])
    if length <= 2 * radius:
        raise ValueError("Capsule length must be greater than its diameter")

    half_length = length / 2
    straight_end = half_length - radius
    diagonal_offset = radius / math.sqrt(2)
    start = [0, -half_length]
    return {
        "type": "revolve",
        "id": base["id"],
        "plane": "XY",
        "profile": "sketch",
        "positions": [[0, 0]],
        "axis_start": [0, -1],
        "axis_end": [0, 1],
        "angle": 360,
        "start": rounded_points([start])[0],
        "segments": [
            {
                "type": "arc",
                "through": rounded_points(
                    [[diagonal_offset, -straight_end - diagonal_offset]]
                )[0],
                "to": rounded_points([[radius, -straight_end]])[0],
            },
            {"type": "line", "to": rounded_points([[radius, straight_end]])[0]},
            {
                "type": "arc",
                "through": rounded_points(
                    [[diagonal_offset, straight_end + diagonal_offset]]
                )[0],
                "to": rounded_points([[0, half_length]])[0],
            },
            {"type": "line", "to": rounded_points([start])[0]},
        ],
        "close": True,
    }


def feature_operation(base: dict[str, Any], feature: dict[str, Any]) -> dict[str, Any]:
    """Return one concrete add_extrude or cut operation."""
    if feature["operation"] in {"revolved_extrusion", "revolved_cut"}:
        return revolved_feature_operation(base, feature)

    operation_type = "add_extrude" if feature["operation"] == "extrusion" else "cut"
    operation = {
        "type": operation_type,
        "id": feature["id"],
        "target": feature["target"],
        "positions": resolve_positions(base, feature),
    }

    operation.update(profile_fields(feature))

    if operation_type == "add_extrude":
        operation["distance"] = number_value(feature.get("distance", 5))
    else:
        operation["depth"] = feature.get("depth", "through")

    return operation


def revolved_feature_operation(
    base: dict[str, Any],
    feature: dict[str, Any],
) -> dict[str, Any]:
    """Return an additive or subtractive revolved feature."""
    if feature["shape"] != "rectangle":
        return custom_revolved_feature_operation(feature)

    radial_size = number_value(feature["width"])
    axial_size = number_value(feature["height"])
    base_radius = number_value(base["diameter"]) / 2
    center_y = revolved_feature_center_y(base, feature)
    center_x = (
        base_radius + radial_size / 2
        if feature["operation"] == "revolved_extrusion"
        else base_radius - radial_size / 2
    )

    return {
        "type": (
            "add_revolve"
            if feature["operation"] == "revolved_extrusion"
            else "cut_revolve"
        ),
        "id": feature["id"],
        "plane": "XY",
        "profile": "rectangle",
        "positions": [[round_number(center_x), round_number(center_y)]],
        "axis_start": [0, -1],
        "axis_end": [0, 1],
        "angle": 360,
        "width": round_number(radial_size),
        "height": round_number(axial_size),
    }


def custom_revolved_feature_operation(feature: dict[str, Any]) -> dict[str, Any]:
    """Return a revolved feature using a custom 2D profile."""
    operation_type = (
        "add_revolve"
        if feature["operation"] == "revolved_extrusion"
        else "cut_revolve"
    )
    operation = {
        "type": operation_type,
        "id": feature["id"],
        "plane": "XY",
        "positions": resolve_custom_revolve_positions(feature),
        "axis_start": [0, -1],
        "axis_end": [0, 1],
        "angle": 360,
    }
    operation.update(profile_fields(feature))
    return operation


def resolve_custom_revolve_positions(feature: dict[str, Any]) -> list[list[float]]:
    """Return positions for custom-profile revolved features."""
    placement = feature["placement"]
    if placement["type"] == "centered":
        return [[0, 0]]
    if placement["type"] == "explicit":
        return rounded_points(placement["positions"])
    raise ValueError(
        "Custom revolved features support centered or explicit placement"
    )


def revolved_feature_center_y(base: dict[str, Any], feature: dict[str, Any]) -> float:
    """Resolve axial feature placement into a Y position for revolve sketches."""
    placement = feature["placement"]
    if placement["type"] == "centered":
        return 0
    if placement["type"] == "explicit":
        return number_value(placement["positions"][0][1])
    if placement["type"] == "offset_from_edge":
        length = number_value(base["length"])
        axial_size = number_value(feature["height"])
        offset = number_value(placement["offset"])
        if placement["edge"] == "front":
            return length / 2 - offset - axial_size / 2
        if placement["edge"] == "back":
            return -length / 2 + offset + axial_size / 2

    raise ValueError(
        "Revolved features support centered, explicit, or front/back offset placement"
    )


def edge_treatment_operation(edge_treatment: dict[str, Any]) -> dict[str, Any]:
    """Return one concrete chamfer or fillet operation."""
    treatment = edge_treatment["treatment"]
    operation = {
        "type": treatment,
        "id": edge_treatment["id"],
        "target": (
            f"{edge_treatment['target_feature']}."
            f"{edge_treatment['edge_selector']}"
        ),
    }

    if treatment == "chamfer":
        operation["distance"] = number_value(edge_treatment["distance"])
    elif treatment == "fillet":
        operation["radius"] = number_value(edge_treatment["radius"])
    else:
        raise ValueError(f"Unsupported edge treatment: {treatment}")

    return operation


def profile_fields(feature: dict[str, Any]) -> dict[str, Any]:
    """Return concrete profile fields for a high-level feature shape."""
    shape = feature["shape"]
    if shape == "rectangle":
        return {
            "profile": "rectangle",
            "width": number_value(feature["width"]),
            "height": number_value(feature["height"]),
        }

    if shape == "circle":
        return {
            "profile": "circle",
            "diameter": number_value(feature["diameter"]),
        }

    if shape == "polygon":
        return {
            "profile": "polygon",
            "sides": int(feature["sides"]),
            "diameter": number_value(feature["diameter"]),
        }

    if shape == "polyline":
        return {
            "profile": "polyline",
            "points": rounded_points(feature["points"]),
        }

    if shape == "slot":
        return slot_profile_fields(
            length=number_value(feature["length"]),
            width=number_value(feature["width"]),
            orientation=feature.get("orientation", "horizontal"),
        )

    if shape == "rounded_rectangle":
        return rounded_rectangle_profile_fields(
            width=number_value(feature["width"]),
            height=number_value(feature["height"]),
            radius=number_value(feature["radius"]),
        )

    raise ValueError(f"Unsupported intent shape: {shape}")


def rounded_rectangle_profile_fields(
    width: float,
    height: float,
    radius: float,
) -> dict[str, Any]:
    """Return an arc sketch for a rounded rectangle."""
    if radius <= 0:
        raise ValueError("Rounded rectangle radius must be positive")
    if radius * 2 >= min(width, height):
        raise ValueError(
            "Rounded rectangle radius must be less than half the smaller side"
        )

    half_width = width / 2
    half_height = height / 2
    diagonal_offset = radius / math.sqrt(2)
    start = [-half_width + radius, -half_height]
    segments = [
        {"type": "line", "to": [half_width - radius, -half_height]},
        {
            "type": "arc",
            "through": [
                half_width - radius + diagonal_offset,
                -half_height + radius - diagonal_offset,
            ],
            "to": [half_width, -half_height + radius],
        },
        {"type": "line", "to": [half_width, half_height - radius]},
        {
            "type": "arc",
            "through": [
                half_width - radius + diagonal_offset,
                half_height - radius + diagonal_offset,
            ],
            "to": [half_width - radius, half_height],
        },
        {"type": "line", "to": [-half_width + radius, half_height]},
        {
            "type": "arc",
            "through": [
                -half_width + radius - diagonal_offset,
                half_height - radius + diagonal_offset,
            ],
            "to": [-half_width, half_height - radius],
        },
        {"type": "line", "to": [-half_width, -half_height + radius]},
        {
            "type": "arc",
            "through": [
                -half_width + radius - diagonal_offset,
                -half_height + radius - diagonal_offset,
            ],
            "to": start,
        },
    ]

    return {
        "profile": "sketch",
        "start": start,
        "segments": segments,
        "close": True,
    }


def slot_profile_fields(length: float, width: float, orientation: str) -> dict[str, Any]:
    """Return a true arc sketch for a rounded slot."""
    if length <= width:
        raise ValueError("Slot length must be greater than slot width")

    radius = width / 2
    straight_half_length = (length - width) / 2

    if orientation == "horizontal":
        start = [-straight_half_length, -radius]
        segments = [
            {"type": "line", "to": [straight_half_length, -radius]},
            {
                "type": "arc",
                "through": [straight_half_length + radius, 0],
                "to": [straight_half_length, radius],
            },
            {"type": "line", "to": [-straight_half_length, radius]},
            {
                "type": "arc",
                "through": [-straight_half_length - radius, 0],
                "to": start,
            },
        ]
    else:
        start = [-radius, -straight_half_length]
        segments = [
            {"type": "line", "to": [-radius, straight_half_length]},
            {
                "type": "arc",
                "through": [0, straight_half_length + radius],
                "to": [radius, straight_half_length],
            },
            {"type": "line", "to": [radius, -straight_half_length]},
            {
                "type": "arc",
                "through": [0, -straight_half_length - radius],
                "to": start,
            },
        ]

    return {
        "profile": "sketch",
        "start": start,
        "segments": segments,
        "close": True,
    }


def resolve_positions(base: dict[str, Any], feature: dict[str, Any]) -> list[list[float]]:
    """Resolve high-level placement into exact operation positions."""
    placement = feature["placement"]
    placement_type = placement["type"]

    if placement_type == "centered":
        return [[0, 0]]

    if placement_type == "explicit":
        return rounded_points(placement["positions"])

    if placement_type == "near_corners":
        return near_corner_positions(base, feature, placement)

    if placement_type == "circular_pattern":
        return circular_pattern_positions(base, feature, placement)

    if placement_type == "rectangular_pattern":
        return rectangular_pattern_positions(placement)

    if placement_type == "mirrored":
        return mirrored_positions(placement)

    if placement_type == "offset_from_edge":
        return offset_from_edge_position(base, feature, placement)

    raise ValueError(f"Unsupported placement type: {placement_type}")


def near_corner_positions(
    base: dict[str, Any],
    feature: dict[str, Any],
    placement: dict[str, Any],
) -> list[list[float]]:
    """Place repeated feature instances near the base corner regions."""
    count = int(placement.get("count", 4))
    if count < 1 or count > 4:
        raise ValueError("near_corners placement supports between 1 and 4 corners")

    base_width, base_height = base_plan_size(base)
    feature_width, feature_height = feature_plan_size(feature)
    margin = number_value(placement.get("margin", 5))
    x = base_width / 2 - margin - feature_width / 2
    y = base_height / 2 - margin - feature_height / 2
    if x <= 0 or y <= 0:
        raise ValueError("Feature is too large to place near the requested corners")

    corners = [
        [-x, y],
        [x, y],
        [-x, -y],
        [x, -y],
    ]
    return rounded_points(corners[:count])


def circular_pattern_positions(
    base: dict[str, Any],
    feature: dict[str, Any],
    placement: dict[str, Any],
) -> list[list[float]]:
    """Place feature instances evenly around the origin."""
    count = int(placement["count"])
    if count < 1:
        raise ValueError("circular_pattern placement requires at least one copy")

    radius = placement.get("radius")
    if radius is None:
        base_width, base_height = base_plan_size(base)
        feature_width, feature_height = feature_plan_size(feature)
        margin = number_value(placement.get("margin", 5))
        radius = min(base_width, base_height) / 2 - margin - max(
            feature_width,
            feature_height,
        ) / 2

    radius = number_value(radius)
    if radius <= 0:
        raise ValueError("circular_pattern radius must be positive")

    start_angle = math.radians(number_value(placement.get("start_angle_degrees", 0)))
    positions = []
    for index in range(count):
        angle = start_angle + (2 * math.pi * index) / count
        positions.append([radius * math.cos(angle), radius * math.sin(angle)])

    return rounded_points(positions)


def rectangular_pattern_positions(placement: dict[str, Any]) -> list[list[float]]:
    """Place feature instances in a centered row/column grid."""
    rows = int(placement["rows"])
    columns = int(placement["columns"])
    if rows < 1 or columns < 1:
        raise ValueError("rectangular_pattern requires at least one row and column")

    row_spacing = number_value(placement["row_spacing"])
    column_spacing = number_value(placement["column_spacing"])
    center = placement.get("center", [0, 0])
    center_x = number_value(center[0])
    center_y = number_value(center[1])
    positions = []

    for row in range(rows):
        y = center_y + (row - (rows - 1) / 2) * row_spacing
        for column in range(columns):
            x = center_x + (column - (columns - 1) / 2) * column_spacing
            positions.append([x, y])

    return rounded_points(positions)


def mirrored_positions(placement: dict[str, Any]) -> list[list[float]]:
    """Mirror a seed position across the requested axes."""
    seed = placement.get("seed", [0, 0])
    axes = set(placement.get("axes", []))
    x_values = [number_value(seed[0])]
    y_values = [number_value(seed[1])]

    if "y" in axes:
        x_values.append(-x_values[0])
    if "x" in axes:
        y_values.append(-y_values[0])

    positions = []
    for x in x_values:
        for y in y_values:
            point = [x, y]
            if point not in positions:
                positions.append(point)

    return rounded_points(positions)


def offset_from_edge_position(
    base: dict[str, Any],
    feature: dict[str, Any],
    placement: dict[str, Any],
) -> list[list[float]]:
    """Place one feature by offsetting inward from a named base edge."""
    base_width, base_height = base_plan_size(base)
    feature_width, feature_height = feature_plan_size(feature)
    edge = placement["edge"]
    offset = number_value(placement["offset"])
    along = number_value(placement["along"])

    if edge == "front":
        return rounded_points(
            [[along, base_height / 2 - offset - feature_height / 2]]
        )
    if edge == "back":
        return rounded_points(
            [[along, -base_height / 2 + offset + feature_height / 2]]
        )
    if edge == "right":
        return rounded_points(
            [[base_width / 2 - offset - feature_width / 2, along]]
        )
    if edge == "left":
        return rounded_points(
            [[-base_width / 2 + offset + feature_width / 2, along]]
        )

    raise ValueError(f"Unsupported edge: {edge}")


def feature_relationships(feature: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate basic relationship constraints from feature intent."""
    relationships = []
    placement_type = feature["placement"]["type"]

    if placement_type == "centered" and feature["operation"] not in {
        "revolved_extrusion",
        "revolved_cut",
    }:
        relationships.append(
            {
                "type": "centered_on",
                "feature": feature["id"],
                "reference": "base",
                "tolerance": 0.001,
            }
        )

    if (
        feature["target"].startswith("base.")
        and feature["operation"] not in {"revolved_extrusion", "revolved_cut"}
    ):
        relationships.append(
            {
                "type": "inside",
                "feature": feature["id"],
                "container": "base",
                "margin": 0,
            }
        )

    if feature["operation"] in {"extrusion", "revolved_extrusion"}:
        relationships.append(
            {
                "type": "must_connect",
                "feature": feature["id"],
                "to": feature.get("target", "base").split(".", 1)[0],
            }
        )

    return relationships


def base_plan_size(base: dict[str, Any]) -> tuple[float, float]:
    """Return approximate top-view size for base placement math."""
    if base["profile"] == "rectangle":
        return number_value(base["width"]), number_value(base["height"])

    if base["profile"] in {"cylinder", "half_cylinder", "capsule"}:
        return number_value(base["diameter"]), number_value(base["length"])

    diameter = number_value(base["diameter"])
    return diameter, diameter


def base_default_feature_depth(base: dict[str, Any]) -> float:
    """Return a practical depth scale for inferred feature dimensions."""
    if "thickness" in base:
        return number_value(base["thickness"])
    if "diameter" in base:
        return number_value(base["diameter"])
    base_width, base_height = base_plan_size(base)
    return min(base_width, base_height) * 0.1


def feature_plan_size(feature: dict[str, Any]) -> tuple[float, float]:
    """Return approximate top-view size for feature placement math."""
    shape = feature["shape"]
    if shape == "rectangle":
        return number_value(feature["width"]), number_value(feature["height"])

    if shape in {"circle", "polygon"}:
        diameter = number_value(feature["diameter"])
        return diameter, diameter

    if shape == "polyline":
        return point_bounds_size(feature["points"])

    if shape == "slot":
        length = number_value(feature["length"])
        width = number_value(feature["width"])
        if feature.get("orientation", "horizontal") == "vertical":
            return width, length
        return length, width

    if shape == "rounded_rectangle":
        return number_value(feature["width"]), number_value(feature["height"])

    raise ValueError(f"Unsupported feature shape: {shape}")


def point_bounds_size(points: list[list[float]]) -> tuple[float, float]:
    """Return the width and height of a point list's bounding box."""
    xs = [number_value(point[0]) for point in points]
    ys = [number_value(point[1]) for point in points]
    return max(xs) - min(xs), max(ys) - min(ys)


def validate_base_dimensions(base: dict[str, Any]) -> None:
    """Check profile-specific base dimensions."""
    if base["profile"] == "rectangle":
        require_keys(base, ["width", "height", "thickness"])
    elif base["profile"] == "circle":
        require_keys(base, ["diameter", "thickness"])
    elif base["profile"] == "polygon":
        require_keys(base, ["diameter", "sides", "thickness"])
    elif base["profile"] in {"cylinder", "half_cylinder", "capsule"}:
        require_keys(base, ["diameter", "length"])


def validate_feature_dimensions(feature: dict[str, Any]) -> None:
    """Check shape-specific feature dimensions."""
    if feature["shape"] == "rectangle":
        require_keys(feature, ["width", "height"])
    elif feature["shape"] == "circle":
        require_keys(feature, ["diameter"])
    elif feature["shape"] == "polygon":
        require_keys(feature, ["diameter", "sides"])
    elif feature["shape"] == "polyline":
        require_keys(feature, ["points"])
    elif feature["shape"] == "slot":
        require_keys(feature, ["length", "width"])
    elif feature["shape"] == "rounded_rectangle":
        require_keys(feature, ["width", "height", "radius"])

    if feature["operation"] == "extrusion":
        require_keys(feature, ["distance"])
    elif feature["operation"] == "cut":
        require_keys(feature, ["depth"])
    elif feature["operation"] in {"revolved_extrusion", "revolved_cut"}:
        if feature["shape"] == "rectangle":
            require_keys(feature, ["width", "height"])
    else:
        raise ValueError(f"Unsupported feature operation: {feature['operation']}")


def validate_edge_treatment_dimensions(edge_treatment: dict[str, Any]) -> None:
    """Check treatment-specific edge treatment dimensions."""
    if edge_treatment["treatment"] == "chamfer":
        require_keys(edge_treatment, ["distance"])
    elif edge_treatment["treatment"] == "fillet":
        require_keys(edge_treatment, ["radius"])


def require_keys(data: dict[str, Any], keys: list[str]) -> None:
    """Raise a helpful error when required shape-specific keys are missing."""
    missing_keys = [key for key in keys if key not in data]
    if missing_keys:
        raise ValueError(f"Missing required intent fields: {', '.join(missing_keys)}")


def missing_required_intent_dimensions(intent: dict[str, Any]) -> list[dict[str, Any]]:
    """Return required dimensions omitted by raw design intent."""
    intent = remove_null_values(intent)
    missing = []
    base_missing = missing_base_dimension_fields(intent["base"])
    if base_missing:
        missing.append({
            "kind": "base",
            "id": intent["base"].get("id", "base"),
            "fields": base_missing,
        })

    for feature in intent["features"]:
        feature_missing = missing_feature_dimension_fields(feature)
        if feature_missing:
            missing.append({
                "kind": "feature",
                "id": feature.get("id", "unknown_feature"),
                "fields": feature_missing,
            })

    for edge_treatment in intent.get("edge_treatments", []):
        edge_missing = missing_edge_treatment_dimension_fields(edge_treatment)
        if edge_missing:
            missing.append({
                "kind": "edge_treatment",
                "id": edge_treatment.get("id", "unknown_edge_treatment"),
                "fields": edge_missing,
            })

    return missing


def missing_base_dimension_fields(base: dict[str, Any]) -> list[str]:
    """Return missing base dimensions required by its profile."""
    if base["profile"] == "rectangle":
        return missing_keys(base, ["width", "height", "thickness"])
    if base["profile"] == "circle":
        return missing_keys(base, ["diameter", "thickness"])
    if base["profile"] == "polygon":
        return missing_keys(base, ["diameter", "sides", "thickness"])
    if base["profile"] in {"cylinder", "half_cylinder", "capsule"}:
        return missing_keys(base, ["diameter", "length"])
    return []


def missing_feature_dimension_fields(feature: dict[str, Any]) -> list[str]:
    """Return missing feature dimensions required by its shape and operation."""
    required_fields = []
    if feature["shape"] == "rectangle":
        required_fields.extend(["width", "height"])
    elif feature["shape"] == "circle":
        required_fields.append("diameter")
    elif feature["shape"] == "polygon":
        required_fields.extend(["diameter", "sides"])
    elif feature["shape"] == "polyline":
        required_fields.append("points")
    elif feature["shape"] == "slot":
        required_fields.extend(["length", "width"])
    elif feature["shape"] == "rounded_rectangle":
        required_fields.extend(["width", "height", "radius"])

    if feature["operation"] == "extrusion":
        required_fields.append("distance")
    elif feature["operation"] == "cut":
        required_fields.append("depth")

    return missing_keys(feature, required_fields)


def missing_edge_treatment_dimension_fields(edge_treatment: dict[str, Any]) -> list[str]:
    """Return missing dimensions required by an edge treatment."""
    if edge_treatment["treatment"] == "chamfer":
        return missing_keys(edge_treatment, ["distance"])
    if edge_treatment["treatment"] == "fillet":
        return missing_keys(edge_treatment, ["radius"])
    return []


def missing_keys(data: dict[str, Any], keys: list[str]) -> list[str]:
    """Return keys absent after null cleanup."""
    return [key for key in keys if key not in data]


def rounded_points(points: list[list[float]]) -> list[list[float]]:
    """Round points for stable, readable JSON output."""
    return [[round_number(x), round_number(y)] for x, y in points]


def round_number(value: float) -> float:
    """Round a number while preserving normal int-looking values."""
    rounded = round(number_value(value), 6)
    if rounded == int(rounded):
        return int(rounded)
    return rounded


def number_value(value: Any) -> float:
    """Convert a JSON number-like value to float."""
    if isinstance(value, bool):
        raise ValueError("Boolean values are not valid CAD numbers")
    return float(value)


def remove_null_values(value: Any) -> Any:
    """Remove null fields emitted by strict API schemas."""
    if isinstance(value, dict):
        return {
            key: remove_null_values(child_value)
            for key, child_value in value.items()
            if child_value is not None
        }

    if isinstance(value, list):
        return [remove_null_values(item) for item in value]

    return value
