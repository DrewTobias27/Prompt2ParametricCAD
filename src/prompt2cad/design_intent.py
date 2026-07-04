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
                "mirrored",
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
            "enum": ["rectangle", "circle", "polygon"],
        },
        "width": POSITIVE_NUMBER_SCHEMA,
        "height": POSITIVE_NUMBER_SCHEMA,
        "diameter": POSITIVE_NUMBER_SCHEMA,
        "sides": {"type": "integer", "minimum": 3},
        "thickness": POSITIVE_NUMBER_SCHEMA,
    },
    "required": ["id", "profile", "thickness"],
}

FEATURE_INTENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "id": {"type": "string"},
        "operation": {
            "type": "string",
            "enum": ["extrusion", "cut"],
        },
        "target": {"type": "string"},
        "shape": {
            "type": "string",
            "enum": ["rectangle", "circle", "polygon", "slot"],
        },
        "placement": PLACEMENT_SCHEMA,
        "width": POSITIVE_NUMBER_SCHEMA,
        "height": POSITIVE_NUMBER_SCHEMA,
        "diameter": POSITIVE_NUMBER_SCHEMA,
        "sides": {"type": "integer", "minimum": 3},
        "length": POSITIVE_NUMBER_SCHEMA,
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

DESIGN_INTENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "base": BASE_INTENT_SCHEMA,
        "features": {
            "type": "array",
            "items": FEATURE_INTENT_SCHEMA,
        },
    },
    "required": ["base", "features"],
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


def intent_to_model_data(intent: dict[str, Any]) -> dict[str, Any]:
    """Lower design intent into executable Prompt2ParametricCAD model data."""
    validate_design_intent(intent)

    base = intent["base"]
    operations = [base_operation(base)]
    relationships = []

    for feature in intent["features"]:
        operation = feature_operation(base, feature)
        operations.append(operation)
        relationships.extend(feature_relationships(feature))

    return {
        "operations": operations,
        "relationships": relationships,
    }


def base_operation(base: dict[str, Any]) -> dict[str, Any]:
    """Return the concrete base operation for a base intent."""
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


def feature_operation(base: dict[str, Any], feature: dict[str, Any]) -> dict[str, Any]:
    """Return one concrete add_extrude or cut operation."""
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

    if shape == "slot":
        return slot_profile_fields(
            length=number_value(feature["length"]),
            width=number_value(feature["width"]),
            orientation=feature.get("orientation", "horizontal"),
        )

    raise ValueError(f"Unsupported intent shape: {shape}")


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

    if placement_type == "mirrored":
        return mirrored_positions(placement)

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


def feature_relationships(feature: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate basic relationship constraints from feature intent."""
    relationships = []
    placement_type = feature["placement"]["type"]

    if placement_type == "centered":
        relationships.append(
            {
                "type": "centered_on",
                "feature": feature["id"],
                "reference": "base",
                "tolerance": 0.001,
            }
        )

    if feature["target"].startswith("base."):
        relationships.append(
            {
                "type": "inside",
                "feature": feature["id"],
                "container": "base",
                "margin": 0,
            }
        )

    if feature["operation"] == "extrusion":
        relationships.append(
            {
                "type": "must_connect",
                "feature": feature["id"],
                "to": feature["target"].split(".", 1)[0],
            }
        )

    return relationships


def base_plan_size(base: dict[str, Any]) -> tuple[float, float]:
    """Return approximate top-view size for base placement math."""
    if base["profile"] == "rectangle":
        return number_value(base["width"]), number_value(base["height"])

    diameter = number_value(base["diameter"])
    return diameter, diameter


def feature_plan_size(feature: dict[str, Any]) -> tuple[float, float]:
    """Return approximate top-view size for feature placement math."""
    shape = feature["shape"]
    if shape == "rectangle":
        return number_value(feature["width"]), number_value(feature["height"])

    if shape in {"circle", "polygon"}:
        diameter = number_value(feature["diameter"])
        return diameter, diameter

    if shape == "slot":
        length = number_value(feature["length"])
        width = number_value(feature["width"])
        if feature.get("orientation", "horizontal") == "vertical":
            return width, length
        return length, width

    raise ValueError(f"Unsupported feature shape: {shape}")


def validate_base_dimensions(base: dict[str, Any]) -> None:
    """Check profile-specific base dimensions."""
    if base["profile"] == "rectangle":
        require_keys(base, ["width", "height"])
    elif base["profile"] == "circle":
        require_keys(base, ["diameter"])
    elif base["profile"] == "polygon":
        require_keys(base, ["diameter", "sides"])


def validate_feature_dimensions(feature: dict[str, Any]) -> None:
    """Check shape-specific feature dimensions."""
    if feature["shape"] == "rectangle":
        require_keys(feature, ["width", "height"])
    elif feature["shape"] == "circle":
        require_keys(feature, ["diameter"])
    elif feature["shape"] == "polygon":
        require_keys(feature, ["diameter", "sides"])
    elif feature["shape"] == "slot":
        require_keys(feature, ["length", "width"])

    if feature["operation"] == "extrusion":
        require_keys(feature, ["distance"])
    else:
        require_keys(feature, ["depth"])


def require_keys(data: dict[str, Any], keys: list[str]) -> None:
    """Raise a helpful error when required shape-specific keys are missing."""
    missing_keys = [key for key in keys if key not in data]
    if missing_keys:
        raise ValueError(f"Missing required intent fields: {', '.join(missing_keys)}")


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

