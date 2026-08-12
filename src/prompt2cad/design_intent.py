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
from copy import deepcopy
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

SEMANTIC_ROLE_VALUES = [
    "base_body",
    "plate",
    "mounting_plate",
    "support_plate",
    "cradle",
    "bracket",
    "wall",
    "rib",
    "boss",
    "hub",
    "post",
    "pad",
    "tab",
    "rim",
    "lip",
    "tube",
    "collar",
    "hole",
    "bolt_hole",
    "counterbore",
    "countersink",
    "slot",
    "key_slot",
    "groove",
    "o_ring_groove",
    "pocket",
    "cutout",
    "drain",
    "spoke",
    "chamfer",
    "fillet",
]

ROLE_SCHEMA = {
    "type": "string",
    "enum": SEMANTIC_ROLE_VALUES,
}

OPENAI_ROLE_SCHEMA = {
    "anyOf": [
        ROLE_SCHEMA,
        {"type": "null"},
    ],
}

REQUIRED_CONCEPTS_SCHEMA = {
    "type": "array",
    "items": ROLE_SCHEMA,
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
                "same_as_feature",
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
        "role": ROLE_SCHEMA,
        "profile": {
            "type": "string",
            "enum": [
                "rectangle",
                "circle",
                "polygon",
                "d_shape",
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
        "role": ROLE_SCHEMA,
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
        "role": ROLE_SCHEMA,
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
        "required_concepts": REQUIRED_CONCEPTS_SCHEMA,
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
            "description": (
                "Feature-center coordinates on the target sketch plane. For "
                "revolved shaft features, use [0, axial_center], so two "
                "features at opposite axial locations use [0, -a] and [0, a]."
            ),
        },
    },
    "required": ["type", "positions"],
}

OPENAI_NEAR_CORNERS_PLACEMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "type": {"type": "string", "enum": ["near_corners"]},
        "count": {"type": "integer", "minimum": 1, "maximum": 24},
        "margin": {
            **OPENAI_NULLABLE_NUMBER_SCHEMA,
            "description": (
                "Clearance from the feature's outside edge to the parent "
                "outline. A larger margin moves the feature inward toward "
                "the center."
            ),
        },
    },
    "required": ["type", "count", "margin"],
}

OPENAI_CIRCULAR_PATTERN_PLACEMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "type": {"type": "string", "enum": ["circular_pattern"]},
        "count": {"type": "integer", "minimum": 1},
        "radius": {
            **OPENAI_NULLABLE_NUMBER_SCHEMA,
            "description": (
                "Distance from the parent center to each feature center. A "
                "smaller radius moves the pattern inward."
            ),
        },
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
        "offset": {
            "type": "number",
            "description": (
                "Inward distance from the named parent edge. Increasing the "
                "offset moves the feature farther inward."
            ),
        },
        "along": {"type": "number"},
    },
    "required": ["type", "edge", "offset", "along"],
}

OPENAI_SAME_AS_FEATURE_PLACEMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "type": {"type": "string", "enum": ["same_as_feature"]},
        "source_feature": {"type": "string"},
    },
    "required": ["type", "source_feature"],
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
        OPENAI_SAME_AS_FEATURE_PLACEMENT_SCHEMA,
    ],
}

OPENAI_POSITIVE_NUMBER_REF = {"$ref": "#/$defs/positive_number"}
OPENAI_POINTS_REF = {"$ref": "#/$defs/points"}
OPENAI_ROLE_REF = {"$ref": "#/$defs/nullable_role"}
OPENAI_PLACEMENT_REF = {"$ref": "#/$defs/placement"}

def strict_openai_object(properties: dict[str, Any]) -> dict[str, Any]:
    """Return an object schema compatible with strict Structured Outputs."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties),
    }


def fixed_string_schema(value: str) -> dict[str, Any]:
    """Return a single-value string discriminator schema."""
    return {"type": "string", "enum": [value]}


OPENAI_BASE_COMMON_PROPERTIES = {
    "id": {"type": "string"},
    "role": OPENAI_ROLE_REF,
}


def openai_base_variant(
    profile: str,
    dimensions: dict[str, Any],
) -> dict[str, Any]:
    """Return one base-profile schema with only applicable dimensions."""
    return strict_openai_object({
        **OPENAI_BASE_COMMON_PROPERTIES,
        "profile": fixed_string_schema(profile),
        **dimensions,
    })


OPENAI_BASE_INTENT_SCHEMA = {
    "anyOf": [
        openai_base_variant("rectangle", {
            "width": OPENAI_POSITIVE_NUMBER_REF,
            "height": OPENAI_POSITIVE_NUMBER_REF,
            "thickness": OPENAI_POSITIVE_NUMBER_REF,
        }),
        openai_base_variant("circle", {
            "diameter": OPENAI_POSITIVE_NUMBER_REF,
            "thickness": OPENAI_POSITIVE_NUMBER_REF,
        }),
        openai_base_variant("polygon", {
            "diameter": OPENAI_POSITIVE_NUMBER_REF,
            "sides": {"type": "integer", "minimum": 3},
            "thickness": OPENAI_POSITIVE_NUMBER_REF,
        }),
        openai_base_variant("d_shape", {
            "width": OPENAI_POSITIVE_NUMBER_REF,
            "height": OPENAI_POSITIVE_NUMBER_REF,
            "thickness": OPENAI_POSITIVE_NUMBER_REF,
        }),
        openai_base_variant("cylinder", {
            "diameter": OPENAI_POSITIVE_NUMBER_REF,
            "length": OPENAI_POSITIVE_NUMBER_REF,
        }),
        openai_base_variant("half_cylinder", {
            "diameter": OPENAI_POSITIVE_NUMBER_REF,
            "length": OPENAI_POSITIVE_NUMBER_REF,
        }),
        openai_base_variant("capsule", {
            "diameter": OPENAI_POSITIVE_NUMBER_REF,
            "length": OPENAI_POSITIVE_NUMBER_REF,
        }),
        openai_base_variant("capsule", {
            "diameter": OPENAI_POSITIVE_NUMBER_REF,
            "length": OPENAI_POSITIVE_NUMBER_REF,
            "thickness": OPENAI_POSITIVE_NUMBER_REF,
        }),
    ],
}


OPENAI_FEATURE_COMMON_PROPERTIES = {
    "id": {"type": "string"},
    "role": OPENAI_ROLE_REF,
    "target": {"type": "string"},
    "placement": OPENAI_PLACEMENT_REF,
}

OPENAI_FEATURE_SHAPE_DIMENSIONS = {
    "rectangle": {
        "width": {
            **OPENAI_POSITIVE_NUMBER_REF,
            "description": (
                "Planar sketch width. For a revolved collar or groove, this "
                "is radial thickness/depth, not axial width."
            ),
        },
        "height": {
            **OPENAI_POSITIVE_NUMBER_REF,
            "description": (
                "Planar sketch height. For a revolved collar or groove, this "
                "is axial width along the shaft."
            ),
        },
    },
    "circle": {"diameter": OPENAI_POSITIVE_NUMBER_REF},
    "polygon": {
        "diameter": OPENAI_POSITIVE_NUMBER_REF,
        "sides": {"type": "integer", "minimum": 3},
    },
    "polyline": {"points": OPENAI_POINTS_REF},
    "slot": {
        "length": OPENAI_POSITIVE_NUMBER_REF,
        "width": OPENAI_POSITIVE_NUMBER_REF,
        "orientation": {
            "type": "string",
            "enum": ["horizontal", "vertical"],
        },
    },
    "rounded_rectangle": {
        "width": OPENAI_POSITIVE_NUMBER_REF,
        "height": OPENAI_POSITIVE_NUMBER_REF,
        "radius": OPENAI_POSITIVE_NUMBER_REF,
    },
}


OPENAI_FEATURE_SHAPE_SCHEMA = {
    "anyOf": [
        strict_openai_object({
            "type": fixed_string_schema(shape),
            **dimensions,
        })
        for shape, dimensions in OPENAI_FEATURE_SHAPE_DIMENSIONS.items()
    ],
}

OPENAI_FEATURE_OPERATION_SCHEMA = {
    "anyOf": [
        strict_openai_object({
            "type": fixed_string_schema("extrusion"),
            "distance": OPENAI_POSITIVE_NUMBER_REF,
        }),
        strict_openai_object({
            "type": fixed_string_schema("cut"),
            "depth": {
                "anyOf": [
                    {"type": "string", "enum": ["through"]},
                    OPENAI_POSITIVE_NUMBER_REF,
                ],
            },
        }),
        strict_openai_object({
            "type": fixed_string_schema("revolved_extrusion"),
        }),
        strict_openai_object({
            "type": fixed_string_schema("revolved_extrusion"),
            "radius": {
                **OPENAI_POSITIVE_NUMBER_REF,
                "description": (
                    "Radial center of the revolved profile. Omit this field "
                    "for a normal collar so the backend infers it from the "
                    "shaft radius and radial profile width."
                ),
            },
        }),
        strict_openai_object({
            "type": fixed_string_schema("revolved_cut"),
        }),
        strict_openai_object({
            "type": fixed_string_schema("revolved_cut"),
            "radius": {
                **OPENAI_POSITIVE_NUMBER_REF,
                "description": (
                    "Radial center of the revolved cut profile. Omit this "
                    "field for a normal shaft groove so the backend infers it."
                ),
            },
        }),
    ],
}

OPENAI_FEATURE_INTENT_SCHEMA = strict_openai_object({
    **OPENAI_FEATURE_COMMON_PROPERTIES,
    "operation": OPENAI_FEATURE_OPERATION_SCHEMA,
    "shape": OPENAI_FEATURE_SHAPE_SCHEMA,
})


OPENAI_EDGE_COMMON_PROPERTIES = {
    "id": {"type": "string"},
    "role": OPENAI_ROLE_REF,
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
}

OPENAI_EDGE_TREATMENT_INTENT_SCHEMA = {
    "anyOf": [
        strict_openai_object({
            **OPENAI_EDGE_COMMON_PROPERTIES,
            "treatment": fixed_string_schema("chamfer"),
            "distance": OPENAI_POSITIVE_NUMBER_REF,
        }),
        strict_openai_object({
            **OPENAI_EDGE_COMMON_PROPERTIES,
            "treatment": fixed_string_schema("fillet"),
            "radius": OPENAI_POSITIVE_NUMBER_REF,
        }),
    ],
}

OPENAI_DESIGN_INTENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "$defs": {
        "positive_number": POSITIVE_NUMBER_SCHEMA,
        "points": POINTS_SCHEMA,
        "nullable_role": OPENAI_ROLE_SCHEMA,
        "placement": OPENAI_PLACEMENT_SCHEMA,
    },
    "properties": {
        "required_concepts": REQUIRED_CONCEPTS_SCHEMA,
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
    "required": ["required_concepts", "base", "features", "edge_treatments"],
}


def design_intent_from_openai(intent: dict[str, Any]) -> dict[str, Any]:
    """Flatten composed API feature objects into the internal intent format."""
    normalized = {
        **intent,
        "features": [
            feature_intent_from_openai(feature)
            for feature in intent.get("features", [])
        ],
    }
    return normalize_intent_placement_fields(normalized)


CIRCULAR_PATTERN_START_ANGLE_ALIASES = (
    "angle_offset",
    "angle_offset_degrees",
    "start_angle",
)


def normalize_intent_placement_fields(
    intent: dict[str, Any],
) -> dict[str, Any]:
    """Canonicalize equivalent placement fields at the intent boundary.

    Structured output normally restricts the model to the canonical schema,
    but repaired or previously saved intent can still contain an intuitive
    alias.  Normalize that vocabulary before validation so a requested
    circular-pattern phase cannot be silently discarded.
    """
    features = []
    for feature in intent.get("features", []):
        placement = feature.get("placement")
        if not isinstance(placement, dict):
            features.append(feature)
            continue

        normalized_placement = dict(placement)
        if placement.get("type") == "circular_pattern":
            if "start_angle_degrees" not in normalized_placement:
                for alias in CIRCULAR_PATTERN_START_ANGLE_ALIASES:
                    if alias in normalized_placement:
                        normalized_placement["start_angle_degrees"] = (
                            normalized_placement[alias]
                        )
                        break
            for alias in CIRCULAR_PATTERN_START_ANGLE_ALIASES:
                normalized_placement.pop(alias, None)

        features.append({**feature, "placement": normalized_placement})

    return {**intent, "features": features}


def feature_intent_from_openai(feature: dict[str, Any]) -> dict[str, Any]:
    """Flatten one API operation/shape pair without mutating the response."""
    if not isinstance(feature.get("operation"), dict):
        return feature

    operation = dict(feature["operation"])
    shape = dict(feature["shape"])
    return {
        **{
            key: value
            for key, value in feature.items()
            if key not in {"operation", "shape"}
        },
        "operation": operation.pop("type"),
        "shape": shape.pop("type"),
        **shape,
        **operation,
    }


def design_intent_to_openai(intent: dict[str, Any]) -> dict[str, Any]:
    """Compose internal intent into the sparse API/example representation."""
    return {
        "required_concepts": intent.get("required_concepts", []),
        "base": {
            **intent["base"],
            "role": intent["base"].get("role"),
        },
        "features": [
            feature_intent_to_openai(feature)
            for feature in intent.get("features", [])
        ],
        "edge_treatments": [
            {**treatment, "role": treatment.get("role")}
            for treatment in intent.get("edge_treatments", [])
        ],
    }


def feature_intent_to_openai(feature: dict[str, Any]) -> dict[str, Any]:
    """Compose one internal feature into focused operation and shape objects."""
    shape_fields = {
        key: feature[key]
        for key in OPENAI_FEATURE_SHAPE_DIMENSIONS[feature["shape"]]
        if key in feature
    }
    operation_fields = {}
    if feature["operation"] == "extrusion" and "distance" in feature:
        operation_fields["distance"] = feature["distance"]
    elif feature["operation"] == "cut" and "depth" in feature:
        operation_fields["depth"] = feature["depth"]
    elif (
        feature["operation"] in {"revolved_extrusion", "revolved_cut"}
        and "radius" in feature
    ):
        operation_fields["radius"] = feature["radius"]

    return {
        "id": feature["id"],
        "role": feature.get("role"),
        "target": feature["target"],
        "placement": feature["placement"],
        "operation": {
            "type": feature["operation"],
            **operation_fields,
        },
        "shape": {
            "type": feature["shape"],
            **shape_fields,
        },
    }


def validate_design_intent(intent: dict[str, Any]) -> None:
    """Validate high-level design intent before lowering it."""
    validate_design_intent_structure(intent)

    validate_base_dimensions(intent["base"])
    for feature in intent["features"]:
        validate_feature_dimensions(feature)
    for edge_treatment in intent.get("edge_treatments", []):
        validate_edge_treatment_dimensions(edge_treatment)


def validate_design_intent_structure(intent: dict[str, Any]) -> None:
    """Validate intent vocabulary and structure before inferring dimensions."""
    try:
        validate(instance=intent, schema=DESIGN_INTENT_SCHEMA)
    except ValidationError as error:
        raise ValueError(
            f"Design intent does not match schema: {error.message}"
        ) from error


def intent_to_model_data(intent: dict[str, Any]) -> dict[str, Any]:
    """Lower design intent into executable Prompt2ParametricCAD model data."""
    intent = prepare_design_intent_for_lowering(intent)

    base = intent["base"]
    features_by_id = {
        feature["id"]: feature
        for feature in intent["features"]
    }
    edge_treatments_by_target: dict[str, list[dict[str, Any]]] = {}
    for edge_treatment in intent.get("edge_treatments", []):
        edge_treatments_by_target.setdefault(
            edge_treatment["target_feature"],
            [],
        ).append(edge_treatment)

    operations = [base_operation(base)]
    operations_by_id = {"base": operations[0]}
    relationships = []

    append_edge_treatment_operations(
        operations,
        edge_treatments_by_target.pop("base", []),
        base,
        features_by_id,
    )

    for feature in intent["features"]:
        operation = feature_operation(base, feature, operations_by_id)
        operations.append(operation)
        operations_by_id[operation["id"]] = operation
        relationships.extend(feature_relationships(base, feature))
        append_edge_treatment_operations(
            operations,
            edge_treatments_by_target.pop(feature["id"], []),
            base,
            features_by_id,
        )

    for unmatched_treatments in edge_treatments_by_target.values():
        append_edge_treatment_operations(
            operations,
            unmatched_treatments,
            base,
            features_by_id,
        )

    return {
        "operations": operations,
        "relationships": relationships,
    }


def append_edge_treatment_operations(
    operations: list[dict[str, Any]],
    edge_treatments: list[dict[str, Any]],
    base: dict[str, Any],
    features_by_id: dict[str, dict[str, Any]],
) -> None:
    """Place edge treatments directly after the feature whose edges they own.

    Saved topological references are most stable at that point in the feature
    tree. Later cuts and unions can split or replace those edges.
    """
    for edge_treatment in edge_treatments:
        operations.append(
            edge_treatment_operation(
                edge_treatment,
                base=base,
                features_by_id=features_by_id,
            )
        )


def prepare_design_intent_for_lowering(
    intent: dict[str, Any],
) -> dict[str, Any]:
    """Return the canonical intent representation consumed by the lowerer."""
    intent = remove_null_values(intent)
    intent = normalize_intent_placement_fields(intent)
    # Validate enums and structural fields before dimension inference. This
    # turns model-invented profile or placement names into actionable schema
    # feedback instead of downstream KeyError messages.
    validate_design_intent_structure(intent)
    intent = normalize_intent_references(intent)
    intent = fill_reasonable_missing_dimensions(intent)
    intent = collapse_aligned_wall_through_cuts(intent)
    validate_design_intent(intent)
    return intent


OPPOSITE_EDGES = {
    "front": "back",
    "back": "front",
    "left": "right",
    "right": "left",
}


def collapse_aligned_wall_through_cuts(
    intent: dict[str, Any],
) -> dict[str, Any]:
    """Represent one aligned through-bore as one physical cut feature.

    A centered through cut starting on one of two opposing parallel walls
    already crosses the second wall. Keeping a second identical cut creates a
    no-op feature without changing the requested geometry or design intent.
    """
    features = intent.get("features", [])
    features_by_id = {
        feature["id"]: feature
        for feature in features
        if feature.get("id")
    }
    retained_features = []
    seen_edges_by_key: dict[tuple[Any, ...], list[str]] = {}

    for feature in features:
        candidate = aligned_wall_through_cut_key(feature, features_by_id)
        if candidate is None:
            retained_features.append(feature)
            continue

        key, parent_edge = candidate
        prior_edges = seen_edges_by_key.setdefault(key, [])
        if OPPOSITE_EDGES[parent_edge] in prior_edges:
            continue

        prior_edges.append(parent_edge)
        retained_features.append(feature)

    return {
        **intent,
        "features": retained_features,
    }


def aligned_wall_through_cut_key(
    feature: dict[str, Any],
    features_by_id: dict[str, dict[str, Any]],
) -> tuple[tuple[Any, ...], str] | None:
    """Return an alignment key for a simple centered cut through a wall."""
    if (
        feature.get("operation") != "cut"
        or feature.get("depth") != "through"
        or feature.get("shape")
        not in {"circle", "rectangle", "slot", "rounded_rectangle", "polygon"}
        or feature.get("placement", {}).get("type") != "centered"
    ):
        return None

    parent_id, separator, _ = feature.get("target", "").partition(".")
    if not separator:
        return None
    parent = features_by_id.get(parent_id)
    parent_placement = parent.get("placement", {}) if parent else {}
    parent_edge = parent_placement.get("edge")
    if (
        parent is None
        or parent.get("role") != "wall"
        or parent.get("operation") != "extrusion"
        or parent_placement.get("type") != "offset_from_edge"
        or parent_edge not in OPPOSITE_EDGES
    ):
        return None

    edge_axis = (
        "front_back"
        if parent_edge in {"front", "back"}
        else "left_right"
    )
    profile_signature = tuple(
        feature.get(field)
        for field in (
            "shape",
            "width",
            "height",
            "diameter",
            "length",
            "radius",
            "sides",
        )
    )
    key = (
        edge_axis,
        parent_placement.get("along", 0),
        parent.get("distance"),
        profile_signature,
    )
    return key, parent_edge


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
            normalize_feature_reference(
                feature,
                original_base_id,
                intent.get("features", []),
                base,
            )
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
    all_features: list[dict[str, Any]] | None = None,
    base: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a feature with canonical target names."""
    normalized = dict(feature)
    normalized["target"] = material_support_target(
        normalized.get("target", "base.top"),
        original_base_id,
        normalized,
        all_features or [],
        base,
    )
    placement = normalized.get("placement", {})
    if placement.get("type") == "same_as_feature":
        source_feature_id = placement.get("source_feature")
        source_feature = next(
            (
                candidate
                for candidate in (all_features or [])
                if candidate.get("id") == source_feature_id
            ),
            None,
        )
        target_owner = normalized["target"].split(".", 1)[0]
        if (
            source_feature is not None
            and source_feature.get("operation")
            in {"extrusion", "revolved_extrusion"}
            and target_owner == "base"
        ):
            normalized["target"] = f"{source_feature_id}.top"
    return normalized


def material_support_target(
    target: str,
    original_base_id: str,
    feature: dict[str, Any],
    all_features: list[dict[str, Any]],
    base: dict[str, Any] | None,
    visited_feature_ids: set[str] | None = None,
) -> str:
    """Resolve references through subtractive features to their material face."""
    normalized_target = normalize_face_target(
        target,
        original_base_id,
        feature,
        all_features,
        base,
    )
    target_owner, _, _ = normalized_target.partition(".")
    visited_feature_ids = set(visited_feature_ids or ())
    if target_owner in visited_feature_ids:
        raise ValueError(
            f"Cyclic subtractive target reference involving '{target_owner}'"
        )

    target_feature = next(
        (
            candidate
            for candidate in all_features
            if candidate.get("id") == target_owner
        ),
        None,
    )
    if target_feature and target_feature.get("operation") in {
        "cut",
        "revolved_cut",
    }:
        visited_feature_ids.add(target_owner)
        return material_support_target(
            target_feature.get("target", "base.top"),
            original_base_id,
            feature,
            all_features,
            base,
            visited_feature_ids,
        )

    return normalized_target


def normalize_edge_treatment_reference(
    edge_treatment: dict[str, Any],
    original_base_id: str,
) -> dict[str, Any]:
    """Return an edge treatment with canonical target feature names."""
    normalized = dict(edge_treatment)
    if normalized.get("target_feature") == original_base_id:
        normalized["target_feature"] = "base"
    return normalized


def normalize_face_target(
    target: str,
    original_base_id: str,
    feature: dict[str, Any] | None = None,
    all_features: list[dict[str, Any]] | None = None,
    base: dict[str, Any] | None = None,
) -> str:
    """Normalize a face-operation target into feature.reference format."""
    if target == "":
        return "base.top"

    if target in {"base", original_base_id}:
        return "base.top"

    if target.startswith(f"{original_base_id}."):
        target = f"base.{target.split('.', 1)[1]}"

    feature_ids = {
        candidate.get("id")
        for candidate in (all_features or [])
        if candidate.get("id")
    }

    target_aliases = {
        "base.flat": "base.top",
        "base.flat_face": "base.top",
        "base.curved": "base.outer_surface",
        "base.curved_surface": "base.outer_surface",
        "base.side": "base.top",
        "base.outer_surface": "base.outer_surface",
    }
    if base and base.get("profile") == "half_cylinder":
        # The canonical half-cylinder revolve places its actual flat material
        # face at +Z. "Bottom" describes its design role, not the generated
        # coordinate direction.
        target_aliases["base.bottom"] = "base.top"
    if target in target_aliases:
        return target_aliases[target]

    if "." in target:
        target_feature_id, face_name = target.split(".", 1)
        vague_side_names = {"side", "outer_surface", "side_surface"}
        if target_feature_id in feature_ids and face_name in vague_side_names:
            return f"{target_feature_id}.front"

    if target in feature_ids:
        return f"{target}.{default_face_for_bare_feature_target(target, feature)}"

    return target


def fill_reasonable_missing_dimensions(intent: dict[str, Any]) -> dict[str, Any]:
    """Fill omitted intent dimensions with deterministic base-relative defaults."""
    base = {
        **intent["base"],
        **reasonable_base_dimensions(intent["base"]),
    }
    features = []
    for feature in intent["features"]:
        filled_feature = dict(feature)
        filled_feature.update(reasonable_feature_dimensions(base, filled_feature))
        features.append(filled_feature)

    return {
        **intent,
        "base": base,
        "features": features,
    }


def default_face_for_bare_feature_target(
    target_feature_id: str,
    feature: dict[str, Any] | None,
) -> str:
    """Return a safe face when intent names a feature but not a feature face."""
    if feature and feature.get("operation") == "cut":
        target_text = target_feature_id.lower()
        if any(word in target_text for word in ["wall", "rib", "tab"]):
            return "front"

    return "top"


def reasonable_base_dimensions(base: dict[str, Any]) -> dict[str, Any]:
    """Return missing base dimensions inferred from equivalent fields."""
    updates = {}
    if base["profile"] == "polygon":
        if "diameter" not in base:
            if "width" in base:
                updates["diameter"] = base["width"]
            elif "height" in base:
                updates["diameter"] = base["height"]
        if "sides" not in base:
            updates["sides"] = 6

    return updates


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
        if "thickness" in base:
            return flat_capsule_base_operation(base)
        return capsule_base_operation(base)

    if base["profile"] == "d_shape":
        return d_shape_base_operation(base)

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


def d_shape_base_operation(base: dict[str, Any]) -> dict[str, Any]:
    """Return a flat D-shaped plate using a straight back and arc front."""
    width = number_value(base["width"])
    height = number_value(base["height"])
    radius = height / 2
    flat_back_x = -width / 2
    arc_center_x = width / 2 - radius
    rounded_front_x = width / 2

    return {
        "type": "extrude",
        "id": base["id"],
        "plane": "XY",
        "profile": "sketch",
        "distance": number_value(base["thickness"]),
        "start": rounded_points([[flat_back_x, -radius]])[0],
        "segments": [
            {
                "type": "line",
                "to": rounded_points([[arc_center_x, -radius]])[0],
            },
            {
                "type": "arc",
                "through": rounded_points([[rounded_front_x, 0]])[0],
                "to": rounded_points([[arc_center_x, radius]])[0],
            },
            {
                "type": "line",
                "to": rounded_points([[flat_back_x, radius]])[0],
            },
        ],
        "close": True,
    }


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


def flat_capsule_base_operation(base: dict[str, Any]) -> dict[str, Any]:
    """Return a flat obround/capsule plate operation using true sketch arcs."""
    operation = {
        "type": "extrude",
        "id": base["id"],
        "plane": "XY",
        "distance": number_value(base["thickness"]),
    }
    operation.update(
        slot_profile_fields(
            length=number_value(base["length"]),
            width=number_value(base["diameter"]),
            orientation="horizontal",
        )
    )
    return operation


def feature_operation(
    base: dict[str, Any],
    feature: dict[str, Any],
    operations_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return one concrete add_extrude or cut operation."""
    if feature.get("role") == "countersink":
        return countersink_feature_operation(
            base,
            feature,
            operations_by_id or {},
        )

    if feature["operation"] in {"revolved_extrusion", "revolved_cut"}:
        return revolved_feature_operation(base, feature)

    operation_type = "add_extrude" if feature["operation"] == "extrusion" else "cut"
    positions = resolve_positions(base, feature, operations_by_id)
    operation = {
        "type": operation_type,
        "id": feature["id"],
        "target": feature["target"],
        "positions": positions,
    }

    pattern = feature_pattern_metadata(
        feature,
        positions,
        operations_by_id or {},
    )
    if pattern is not None:
        operation["pattern"] = pattern

    operation.update(profile_fields(feature))

    if operation_type == "add_extrude":
        operation["distance"] = number_value(feature.get("distance", 5))
    else:
        operation["depth"] = feature.get("depth", "through")

    return operation


def countersink_feature_operation(
    base: dict[str, Any],
    feature: dict[str, Any],
    operations_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Lower a countersink intent into a target-face tapered-hole feature."""
    placement = feature.get("placement", {})
    source_feature_id = placement.get("source_feature")
    source_operation = operations_by_id.get(source_feature_id)

    hole_diameter = feature.get("diameter")
    if hole_diameter is None and source_operation is not None:
        hole_diameter = source_operation.get("diameter")
    if hole_diameter is None:
        raise ValueError(
            f"Countersink feature '{feature.get('id')}' requires a hole "
            "diameter or a same_as_feature source with a diameter"
        )

    hole_diameter = number_value(hole_diameter)
    radial_width = number_value(feature.get("width", hole_diameter / 2))
    countersink_diameter = max(
        hole_diameter * 1.5,
        hole_diameter + 2 * radial_width,
    )

    axial_depth = number_value(feature.get("height", radial_width))
    half_angle = math.degrees(math.atan2(radial_width, axial_depth))
    angle = max(30.0, min(150.0, 2 * half_angle))

    positions = resolve_positions(base, feature, operations_by_id)
    operation = {
        "type": "countersink",
        "id": feature["id"],
        "target": feature["target"],
        "positions": positions,
        "diameter": round_number(hole_diameter),
        "countersink_diameter": round_number(countersink_diameter),
        "angle": round_number(angle),
        "depth": (
            source_operation.get("depth", "through")
            if source_operation is not None
            else "through"
        ),
    }
    pattern = feature_pattern_metadata(feature, positions, operations_by_id)
    if pattern is not None:
        operation["pattern"] = pattern
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
    center_ys = revolved_feature_center_ys(base, feature)
    if "radius" in feature:
        center_x = number_value(feature["radius"])
    else:
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
        "positions": [
            [round_number(center_x), round_number(center_y)]
            for center_y in center_ys
        ],
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


def revolved_feature_center_ys(
    base: dict[str, Any],
    feature: dict[str, Any],
) -> list[float]:
    """Resolve every axial feature placement for a revolved rectangle."""
    placement = feature["placement"]
    if placement["type"] == "centered":
        return [0]
    if placement["type"] == "explicit":
        return [
            revolved_explicit_position_y(position)
            for position in placement["positions"]
        ]
    if placement["type"] == "offset_from_edge":
        length = number_value(base["length"])
        axial_size = number_value(feature["height"])
        offset = number_value(placement["offset"])
        if placement["edge"] == "front":
            return [length / 2 - offset - axial_size / 2]
        if placement["edge"] == "back":
            return [-length / 2 + offset + axial_size / 2]

    raise ValueError(
        "Revolved features support centered, explicit, or front/back offset placement"
    )


def revolved_explicit_position_y(position: list[float]) -> float:
    """Return an axial coordinate from either supported explicit convention."""
    position_x = number_value(position[0])
    position_y = number_value(position[1])
    # Design-intent placement is a generic 2D vocabulary. Older examples and
    # direct operation JSON put axial position in Y, while language models
    # commonly express a one-dimensional shaft offset as [axial, 0].
    if position_y == 0 and position_x != 0:
        return position_x
    return position_y


def edge_treatment_operation(
    edge_treatment: dict[str, Any],
    base: dict[str, Any],
    features_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return one concrete chamfer or fillet operation."""
    treatment = edge_treatment["treatment"]
    target_feature = edge_treatment["target_feature"]
    edge_selector = normalize_edge_selector(
        edge_treatment["edge_selector"],
        target_feature,
        base,
        features_by_id.get(target_feature) if features_by_id else None,
    )
    operation = {
        "type": treatment,
        "id": edge_treatment["id"],
        "target": f"{target_feature}.{edge_selector}",
    }

    if treatment == "chamfer":
        operation["distance"] = number_value(edge_treatment["distance"])
    elif treatment == "fillet":
        operation["radius"] = number_value(edge_treatment["radius"])
    else:
        raise ValueError(f"Unsupported edge treatment: {treatment}")

    return operation


def normalize_edge_selector(
    edge_selector: str,
    target_feature_id: str,
    base: dict[str, Any],
    target_feature: dict[str, Any] | None,
) -> str:
    """Normalize edge selectors that are invalid for curved feature geometry."""
    if (
        target_feature_id == "base"
        and edge_selector == "all_edges"
        and base.get("profile") in {"rectangle", "polygon"}
    ):
        return "vertical_edges"

    if target_feature_id == "base" and base.get("profile") in {
        "cylinder",
        "half_cylinder",
        "capsule",
    }:
        selector_aliases = {
            "top_outer_edges": "front_outer_edges",
            "bottom_outer_edges": "back_outer_edges",
            "vertical_edges": "end_edges",
        }
        if edge_selector in selector_aliases:
            return selector_aliases[edge_selector]

    if (
        edge_selector == "vertical_edges"
        and target_feature is not None
        and target_feature.get("shape") == "circle"
    ):
        return "top_outer_edges"

    return edge_selector


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
    smaller_side = min(width, height)
    if math.isclose(radius * 2, smaller_side, rel_tol=0, abs_tol=1e-9):
        return slot_profile_fields(
            length=max(width, height),
            width=smaller_side,
            orientation="horizontal" if width >= height else "vertical",
        )
    if radius * 2 > smaller_side:
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


def resolve_positions(
    base: dict[str, Any],
    feature: dict[str, Any],
    operations_by_id: dict[str, dict[str, Any]] | None = None,
) -> list[list[float]]:
    """Resolve high-level placement into exact operation positions."""
    placement = feature["placement"]
    placement_type = placement["type"]
    placement_reference = placement_reference_geometry(
        base,
        feature,
        operations_by_id or {},
    )

    if placement_type == "centered":
        return [[0, 0]]

    if placement_type == "explicit":
        return rounded_points(placement["positions"])

    if placement_type == "near_corners":
        return near_corner_positions(placement_reference, feature, placement)

    if placement_type == "circular_pattern":
        return circular_pattern_positions(placement_reference, feature, placement)

    if placement_type == "rectangular_pattern":
        return rectangular_pattern_positions(placement)

    if placement_type == "mirrored":
        return mirrored_positions(placement)

    if placement_type == "offset_from_edge":
        return offset_from_edge_position(placement_reference, feature, placement)

    if placement_type == "same_as_feature":
        source_feature = placement["source_feature"]
        source_operation = (operations_by_id or {}).get(source_feature)
        if source_operation is None:
            raise ValueError(
                f"same_as_feature placement references unknown or future "
                f"feature '{source_feature}'"
            )
        source_positions = source_operation.get("positions")
        if not isinstance(source_positions, list) or not source_positions:
            raise ValueError(
                f"Feature '{source_feature}' does not provide reusable positions"
            )
        target_owner, _, _ = str(feature.get("target", "")).partition(".")
        if target_owner == source_feature and len(source_positions) == 1:
            # A sketch on the source feature's own face uses that face's local
            # origin. Reusing its parent-plane offset would apply the offset a
            # second time and move the dependent feature off the solid.
            return [[0, 0]]
        return rounded_points(source_positions)

    raise ValueError(f"Unsupported placement type: {placement_type}")


def feature_pattern_metadata(
    feature: dict[str, Any],
    positions: list[list[float]],
    operations_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """Preserve the design rule behind repeated concrete positions.

    CadQuery still consumes ``positions`` exactly as before.  Native CAD
    exporters can additionally use this metadata to create one seed feature
    followed by an editable pattern instead of baking every instance into a
    single sketch.
    """
    if len(positions) < 2:
        return None

    placement = feature["placement"]
    placement_type = placement["type"]
    seed_position = rounded_points([positions[0]])[0]

    if placement_type == "circular_pattern":
        return {
            "type": "circular",
            "seed_position": seed_position,
            "center": [0, 0],
            "count": int(placement["count"]),
            "total_angle_degrees": 360,
        }

    if placement_type == "rectangular_pattern":
        return {
            "type": "linear",
            "seed_position": seed_position,
            "direction_1": [1, 0],
            "count_1": int(placement["columns"]),
            "spacing_1": round_number(number_value(placement["column_spacing"])),
            "direction_2": [0, 1],
            "count_2": int(placement["rows"]),
            "spacing_2": round_number(number_value(placement["row_spacing"])),
        }

    if placement_type == "mirrored":
        return {
            "type": "mirror",
            "seed_position": seed_position,
            "axes": list(dict.fromkeys(placement["axes"])),
        }

    if placement_type == "same_as_feature":
        source_operation = operations_by_id.get(placement["source_feature"])
        source_pattern = (
            source_operation.get("pattern")
            if source_operation is not None
            else None
        )
        if isinstance(source_pattern, dict):
            return deepcopy(source_pattern)

    return None


def placement_reference_geometry(
    base: dict[str, Any],
    feature: dict[str, Any],
    operations_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Return plan dimensions for the actual face targeted by a feature."""
    target = str(feature.get("target", "base.top"))
    target_owner, _, face_name = target.partition(".")
    if target_owner not in operations_by_id:
        return base
    if target_owner == "base" and face_name in {"top", "bottom"}:
        return base

    operation = operations_by_id[target_owner]
    visited_targets = set()
    while operation.get("type") in {"cut", "cut_revolve"}:
        parent_target = operation.get("target")
        if not isinstance(parent_target, str) or parent_target in visited_targets:
            return base
        visited_targets.add(parent_target)
        parent_owner, _, parent_face = parent_target.partition(".")
        parent_operation = operations_by_id.get(parent_owner)
        if parent_operation is None:
            return base
        operation = parent_operation
        face_name = parent_face

    profile_width, profile_height = operation_profile_size(operation)
    distance = number_value(operation.get("distance", 1))

    if face_name in {"front", "back"}:
        return {
            "profile": "rectangle",
            "width": profile_width,
            "height": distance,
        }
    if face_name in {"left", "right"}:
        return {
            "profile": "rectangle",
            "width": profile_height,
            "height": distance,
        }
    return {
        "profile": "rectangle",
        "width": profile_width,
        "height": profile_height,
    }


def operation_profile_size(operation: dict[str, Any]) -> tuple[float, float]:
    """Return approximate local width and height for an operation profile."""
    profile = operation.get("profile")
    if profile == "rectangle":
        return number_value(operation["width"]), number_value(operation["height"])
    if profile in {"circle", "polygon"}:
        diameter = number_value(operation["diameter"])
        return diameter, diameter
    if profile == "polyline":
        return points_size(operation["points"])
    if profile == "sketch":
        points = [operation["start"]]
        for segment in operation["segments"]:
            if segment["type"] == "line":
                points.append(segment["to"])
            else:
                points.extend([segment["through"], segment["to"]])
        return points_size(points)
    raise ValueError(
        f"Cannot determine placement dimensions for profile '{profile}'"
    )


def points_size(points: list[list[float]]) -> tuple[float, float]:
    """Return the axis-aligned width and height of 2D profile points."""
    if not points:
        raise ValueError("Cannot determine dimensions from an empty point list")

    x_values = [number_value(point[0]) for point in points]
    y_values = [number_value(point[1]) for point in points]
    return max(x_values) - min(x_values), max(y_values) - min(y_values)


def near_corner_positions(
    base: dict[str, Any],
    feature: dict[str, Any],
    placement: dict[str, Any],
) -> list[list[float]]:
    """Place repeated feature instances near the base corner regions."""
    count = int(placement.get("count", 4))
    if count < 1:
        raise ValueError("near_corners placement requires at least one position")

    if base.get("profile") == "polygon":
        sides = int(base["sides"])
        if count > sides:
            raise ValueError(
                "near_corners placement cannot request more positions than "
                "the target polygon has vertices"
            )

        circumradius = number_value(base["diameter"]) / 2
        feature_width, feature_height = feature_plan_size(feature)
        margin = number_value(placement.get("margin", 5))
        clearance = max(feature_width, feature_height) / 2 + margin
        radial_inset = clearance / math.cos(math.pi / sides)
        placement_radius = circumradius - radial_inset
        if placement_radius <= 0:
            raise ValueError(
                "Feature is too large to place near the polygon vertices"
            )

        return rounded_points(
            [
                [
                    placement_radius * math.cos(2 * math.pi * index / sides),
                    placement_radius * math.sin(2 * math.pi * index / sides),
                ]
                for index in range(count)
            ]
        )

    if count > 4:
        raise ValueError(
            "near_corners placement supports at most four positions on "
            "rectangular targets"
        )

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
        along_limit = max(0.0, (base_width - feature_width) / 2)
        along = max(-along_limit, min(along, along_limit))
        offset = max(0.0, min(offset, max(0.0, base_height - feature_height)))
        return rounded_points(
            [[along, base_height / 2 - offset - feature_height / 2]]
        )
    if edge == "back":
        along_limit = max(0.0, (base_width - feature_width) / 2)
        along = max(-along_limit, min(along, along_limit))
        offset = max(0.0, min(offset, max(0.0, base_height - feature_height)))
        return rounded_points(
            [[along, -base_height / 2 + offset + feature_height / 2]]
        )
    if edge == "right":
        along_limit = max(0.0, (base_height - feature_height) / 2)
        along = max(-along_limit, min(along, along_limit))
        offset = max(0.0, min(offset, max(0.0, base_width - feature_width)))
        return rounded_points(
            [[base_width / 2 - offset - feature_width / 2, along]]
        )
    if edge == "left":
        along_limit = max(0.0, (base_height - feature_height) / 2)
        along = max(-along_limit, min(along, along_limit))
        offset = max(0.0, min(offset, max(0.0, base_width - feature_width)))
        return rounded_points(
            [[-base_width / 2 + offset + feature_width / 2, along]]
        )

    raise ValueError(f"Unsupported edge: {edge}")


EXTERNAL_SUPPORT_ROLES = {
    "mounting_plate",
    "support_plate",
    "tab",
    "lip",
    "rim",
}


def feature_relationships(base: dict[str, Any], feature: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate basic relationship constraints from feature intent."""
    relationships = []
    placement_type = feature["placement"]["type"]
    target_parent, _, target_reference = feature["target"].partition(".")
    global_planar_target = target_reference in {"top", "bottom"}
    simple_base_target = target_parent == "base" and base["profile"] not in {
        "half_cylinder",
        "capsule",
    }

    if (
        placement_type == "centered"
        # The relationship evaluator compares operation positions in the
        # parent feature's global 2D workplane. A centered sketch on a front,
        # back, left, or right face is centered in that face's local frame,
        # so emitting a global centered_on constraint would be misleading.
        and global_planar_target
        and (target_parent != "base" or simple_base_target)
        and feature["operation"] not in {
            "revolved_extrusion",
            "revolved_cut",
        }
    ):
        relationships.append(
            {
                "type": "centered_on",
                "feature": feature["id"],
                "reference": target_parent,
                "tolerance": 0.001,
            }
        )

    if (
        target_reference == "top"
        and (target_parent != "base" or simple_base_target)
        and feature.get("role") not in EXTERNAL_SUPPORT_ROLES
        and feature["operation"] not in {"revolved_extrusion", "revolved_cut"}
    ):
        relationships.append(
            {
                "type": "inside",
                "feature": feature["id"],
                "container": target_parent,
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
    if base["profile"] in {"rectangle", "d_shape"}:
        return number_value(base["width"]), number_value(base["height"])

    if base["profile"] == "capsule" and "thickness" in base:
        return number_value(base["length"]), number_value(base["diameter"])

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
    if base["profile"] in {"rectangle", "d_shape"}:
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
    if base["profile"] in {"rectangle", "d_shape"}:
        return missing_keys(base, ["width", "height", "thickness"])
    if base["profile"] == "circle":
        return missing_keys(base, ["diameter", "thickness"])
    if base["profile"] == "polygon":
        required_fields = ["sides", "thickness"]
        if not any(key in base for key in ["diameter", "width", "height"]):
            required_fields.append("diameter")
        return missing_keys(base, required_fields)
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
