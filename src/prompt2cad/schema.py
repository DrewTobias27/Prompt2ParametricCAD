"""Shared JSON schemas for Prompt2ParametricCAD model data."""

from jsonschema import ValidationError
from jsonschema import validate


POSITIVE_NUMBER_SCHEMA = {
    "type": "number",
    "exclusiveMinimum": 0,
}

POINT_SCHEMA = {
    "type": "array",
    "items": {
        "type": "number",
    },
    "minItems": 2,
    "maxItems": 2,
}

POSITIONS_SCHEMA = {
    "type": "array",
    "items": POINT_SCHEMA,
    "minItems": 1,
}

NON_NEGATIVE_NUMBER_SCHEMA = {
    "type": "number",
    "minimum": 0,
}

POLYLINE_POINTS_SCHEMA = {
    "type": "array",
    "items": POINT_SCHEMA,
    "minItems": 3,
}

SKETCH_LINE_SEGMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "type": {
            "type": "string",
            "enum": ["line"],
        },
        "to": POINT_SCHEMA,
    },
    "required": ["type", "to"],
}

SKETCH_ARC_SEGMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "type": {
            "type": "string",
            "enum": ["arc"],
        },
        "through": POINT_SCHEMA,
        "to": POINT_SCHEMA,
    },
    "required": ["type", "through", "to"],
}

SKETCH_SEGMENTS_SCHEMA = {
    "type": "array",
    "items": {
        "anyOf": [
            SKETCH_LINE_SEGMENT_SCHEMA,
            SKETCH_ARC_SEGMENT_SCHEMA,
        ],
    },
    "minItems": 1,
}

CUT_DEPTH_SCHEMA = {
    "anyOf": [
        {
            "type": "string",
            "enum": ["through"],
        },
        POSITIVE_NUMBER_SCHEMA,
    ],
}

CENTERED_ON_RELATIONSHIP_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "type": {
            "type": "string",
            "enum": ["centered_on"],
        },
        "feature": {
            "type": "string",
        },
        "reference": {
            "type": "string",
        },
        "tolerance": NON_NEGATIVE_NUMBER_SCHEMA,
    },
    "required": [
        "type",
        "feature",
        "reference",
        "tolerance",
    ],
}

INSIDE_RELATIONSHIP_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "type": {
            "type": "string",
            "enum": ["inside"],
        },
        "feature": {
            "type": "string",
        },
        "container": {
            "type": "string",
        },
        "margin": NON_NEGATIVE_NUMBER_SCHEMA,
    },
    "required": [
        "type",
        "feature",
        "container",
        "margin",
    ],
}

SMALLER_THAN_RELATIONSHIP_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "type": {
            "type": "string",
            "enum": ["smaller_than"],
        },
        "feature": {
            "type": "string",
        },
        "reference": {
            "type": "string",
        },
        "max_width_fraction": {
            "type": "number",
            "exclusiveMinimum": 0,
        },
        "max_height_fraction": {
            "type": "number",
            "exclusiveMinimum": 0,
        },
    },
    "required": [
        "type",
        "feature",
        "reference",
        "max_width_fraction",
        "max_height_fraction",
    ],
}

MUST_CONNECT_RELATIONSHIP_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "type": {
            "type": "string",
            "enum": ["must_connect"],
        },
        "feature": {
            "type": "string",
        },
        "to": {
            "type": "string",
        },
    },
    "required": [
        "type",
        "feature",
        "to",
    ],
}

RELATIONSHIP_SCHEMAS = [
    CENTERED_ON_RELATIONSHIP_SCHEMA,
    INSIDE_RELATIONSHIP_SCHEMA,
    SMALLER_THAN_RELATIONSHIP_SCHEMA,
    MUST_CONNECT_RELATIONSHIP_SCHEMA,
]

RELATIONSHIPS_SCHEMA = {
    "type": "array",
    "items": {
        "anyOf": RELATIONSHIP_SCHEMAS,
    },
}

PROFILE_PROPERTIES = {
    "rectangle": {
        "width": POSITIVE_NUMBER_SCHEMA,
        "height": POSITIVE_NUMBER_SCHEMA,
    },
    "circle": {
        "diameter": POSITIVE_NUMBER_SCHEMA,
    },
    "polygon": {
        "sides": {
            "type": "integer",
            "minimum": 3,
        },
        "diameter": POSITIVE_NUMBER_SCHEMA,
    },
    "polyline": {
        "points": POLYLINE_POINTS_SCHEMA,
    },
    "sketch": {
        "start": POINT_SCHEMA,
        "segments": SKETCH_SEGMENTS_SCHEMA,
        "close": {
            "type": "boolean",
            "enum": [True],
        },
    },
}

PROFILE_REQUIRED_FIELDS = {
    "rectangle": ["width", "height"],
    "circle": ["diameter"],
    "polygon": ["sides", "diameter"],
    "polyline": ["points"],
    "sketch": ["start", "segments", "close"],
}


def build_base_extrude_schema(profile: str) -> dict:
    """Build a schema for a base extrusion operation."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "type": {
                "type": "string",
                "enum": ["extrude"],
            },
            "id": {
                "type": "string",
            },
            "plane": {
                "type": "string",
                "enum": ["XY"],
            },
            "profile": {
                "type": "string",
                "enum": [profile],
            },
            "distance": POSITIVE_NUMBER_SCHEMA,
            **PROFILE_PROPERTIES[profile],
        },
        "required": [
            "type",
            "id",
            "plane",
            "profile",
            "distance",
            *PROFILE_REQUIRED_FIELDS[profile],
        ],
    }


def build_revolve_feature_schema(
    operation_type: str,
    profile: str,
    include_id: bool = True,
    require_id: bool = False,
) -> dict:
    """Build a schema for an additive or subtractive revolve feature."""
    properties = {
        "type": {
            "type": "string",
            "enum": [operation_type],
        },
        "plane": {
            "type": "string",
            "enum": ["XY"],
        },
        "profile": {
            "type": "string",
            "enum": [profile],
        },
        "positions": POSITIONS_SCHEMA,
        "axis_start": POINT_SCHEMA,
        "axis_end": POINT_SCHEMA,
        "angle": {
            "type": "number",
            "exclusiveMinimum": 0,
            "maximum": 360,
        },
        **PROFILE_PROPERTIES[profile],
    }
    if include_id:
        properties["id"] = {
            "type": "string",
        }

    required = [
        "type",
        "plane",
        "profile",
        "positions",
        "axis_start",
        "axis_end",
        "angle",
        *PROFILE_REQUIRED_FIELDS[profile],
    ]
    if require_id:
        required.append("id")

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


def build_add_extrude_schema(
    profile: str,
    include_optional_fields: bool = True,
    require_id: bool = False,
    include_face_tags: bool = True,
) -> dict:
    """Build a schema for an additive extrusion operation."""
    properties = {
        "type": {
            "type": "string",
            "enum": ["add_extrude"],
        },
        "target": {
            "type": "string",
        },
        "profile": {
            "type": "string",
            "enum": [profile],
        },
        "positions": POSITIONS_SCHEMA,
        "distance": POSITIVE_NUMBER_SCHEMA,
        **PROFILE_PROPERTIES[profile],
    }
    if include_optional_fields:
        properties["id"] = {
            "type": "string",
        }
    if include_optional_fields and include_face_tags:
        properties["face_tags"] = {
            "type": "object",
            "additionalProperties": {
                "type": "string",
            },
        }

    required = [
        "type",
        "target",
        "profile",
        "positions",
        "distance",
        *PROFILE_REQUIRED_FIELDS[profile],
    ]
    if require_id:
        required.append("id")

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


def build_cut_schema(
    profile: str,
    include_id: bool = True,
    require_id: bool = False,
) -> dict:
    """Build a schema for a cut operation."""
    properties = {
        "type": {
            "type": "string",
            "enum": ["cut"],
        },
        "target": {
            "type": "string",
        },
        "profile": {
            "type": "string",
            "enum": [profile],
        },
        "positions": POSITIONS_SCHEMA,
        "depth": CUT_DEPTH_SCHEMA,
        **PROFILE_PROPERTIES[profile],
    }
    if include_id:
        properties["id"] = {
            "type": "string",
        }

    required = [
        "type",
        "target",
        "profile",
        "positions",
        "depth",
        *PROFILE_REQUIRED_FIELDS[profile],
    ]
    if require_id:
        required.append("id")

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


def build_revolve_schema(profile: str) -> dict:
    """Build a schema for a revolve operation."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "type": {
                "type": "string",
                "enum": ["revolve"],
            },
            "id": {
                "type": "string",
            },
            "plane": {
                "type": "string",
                "enum": ["XY"],
            },
            "profile": {
                "type": "string",
                "enum": [profile],
            },
            "positions": POSITIONS_SCHEMA,
            "axis_start": POINT_SCHEMA,
            "axis_end": POINT_SCHEMA,
            "angle": {
                "type": "number",
                "exclusiveMinimum": 0,
                "maximum": 360,
            },
            **PROFILE_PROPERTIES[profile],
        },
        "required": [
            "type",
            "id",
            "plane",
            "profile",
            "positions",
            "axis_start",
            "axis_end",
            "angle",
            *PROFILE_REQUIRED_FIELDS[profile],
        ],
    }


RECTANGLE_EXTRUDE_SCHEMA = build_base_extrude_schema("rectangle")
CIRCLE_EXTRUDE_SCHEMA = build_base_extrude_schema("circle")
POLYGON_EXTRUDE_SCHEMA = build_base_extrude_schema("polygon")
POLYLINE_EXTRUDE_SCHEMA = build_base_extrude_schema("polyline")
SKETCH_EXTRUDE_SCHEMA = build_base_extrude_schema("sketch")
RECTANGLE_REVOLVE_SCHEMA = build_revolve_schema("rectangle")
CIRCLE_REVOLVE_SCHEMA = build_revolve_schema("circle")
POLYGON_REVOLVE_SCHEMA = build_revolve_schema("polygon")
POLYLINE_REVOLVE_SCHEMA = build_revolve_schema("polyline")
SKETCH_REVOLVE_SCHEMA = build_revolve_schema("sketch")

RECTANGLE_ADD_EXTRUDE_SCHEMA = build_add_extrude_schema("rectangle")
CIRCLE_ADD_EXTRUDE_SCHEMA = build_add_extrude_schema("circle")
POLYGON_ADD_EXTRUDE_SCHEMA = build_add_extrude_schema("polygon")
POLYLINE_ADD_EXTRUDE_SCHEMA = build_add_extrude_schema("polyline")
SKETCH_ADD_EXTRUDE_SCHEMA = build_add_extrude_schema("sketch")

OPENAI_RECTANGLE_ADD_EXTRUDE_SCHEMA = build_add_extrude_schema(
    "rectangle",
    include_optional_fields=False,
)
OPENAI_CIRCLE_ADD_EXTRUDE_SCHEMA = build_add_extrude_schema(
    "circle",
    include_optional_fields=False,
)
OPENAI_POLYGON_ADD_EXTRUDE_SCHEMA = build_add_extrude_schema(
    "polygon",
    include_optional_fields=False,
)
OPENAI_POLYLINE_ADD_EXTRUDE_SCHEMA = build_add_extrude_schema(
    "polyline",
    include_optional_fields=False,
)
OPENAI_SKETCH_ADD_EXTRUDE_SCHEMA = build_add_extrude_schema(
    "sketch",
    include_optional_fields=False,
)

RELATIONAL_OPENAI_RECTANGLE_ADD_EXTRUDE_SCHEMA = build_add_extrude_schema(
    "rectangle",
    include_optional_fields=True,
    require_id=True,
    include_face_tags=False,
)
RELATIONAL_OPENAI_CIRCLE_ADD_EXTRUDE_SCHEMA = build_add_extrude_schema(
    "circle",
    include_optional_fields=True,
    require_id=True,
    include_face_tags=False,
)
RELATIONAL_OPENAI_POLYGON_ADD_EXTRUDE_SCHEMA = build_add_extrude_schema(
    "polygon",
    include_optional_fields=True,
    require_id=True,
    include_face_tags=False,
)
RELATIONAL_OPENAI_POLYLINE_ADD_EXTRUDE_SCHEMA = build_add_extrude_schema(
    "polyline",
    include_optional_fields=True,
    require_id=True,
    include_face_tags=False,
)
RELATIONAL_OPENAI_SKETCH_ADD_EXTRUDE_SCHEMA = build_add_extrude_schema(
    "sketch",
    include_optional_fields=True,
    require_id=True,
    include_face_tags=False,
)


RECTANGLE_ADD_REVOLVE_SCHEMA = build_revolve_feature_schema("add_revolve", "rectangle")
CIRCLE_ADD_REVOLVE_SCHEMA = build_revolve_feature_schema("add_revolve", "circle")
POLYGON_ADD_REVOLVE_SCHEMA = build_revolve_feature_schema("add_revolve", "polygon")
POLYLINE_ADD_REVOLVE_SCHEMA = build_revolve_feature_schema("add_revolve", "polyline")
SKETCH_ADD_REVOLVE_SCHEMA = build_revolve_feature_schema("add_revolve", "sketch")

RELATIONAL_OPENAI_RECTANGLE_ADD_REVOLVE_SCHEMA = build_revolve_feature_schema(
    "add_revolve",
    "rectangle",
    require_id=True,
)
RELATIONAL_OPENAI_CIRCLE_ADD_REVOLVE_SCHEMA = build_revolve_feature_schema(
    "add_revolve",
    "circle",
    require_id=True,
)
RELATIONAL_OPENAI_POLYGON_ADD_REVOLVE_SCHEMA = build_revolve_feature_schema(
    "add_revolve",
    "polygon",
    require_id=True,
)
RELATIONAL_OPENAI_POLYLINE_ADD_REVOLVE_SCHEMA = build_revolve_feature_schema(
    "add_revolve",
    "polyline",
    require_id=True,
)
RELATIONAL_OPENAI_SKETCH_ADD_REVOLVE_SCHEMA = build_revolve_feature_schema(
    "add_revolve",
    "sketch",
    require_id=True,
)

OPENAI_RECTANGLE_ADD_REVOLVE_SCHEMA = build_revolve_feature_schema(
    "add_revolve",
    "rectangle",
    include_id=False,
)
OPENAI_CIRCLE_ADD_REVOLVE_SCHEMA = build_revolve_feature_schema(
    "add_revolve",
    "circle",
    include_id=False,
)
OPENAI_POLYGON_ADD_REVOLVE_SCHEMA = build_revolve_feature_schema(
    "add_revolve",
    "polygon",
    include_id=False,
)
OPENAI_POLYLINE_ADD_REVOLVE_SCHEMA = build_revolve_feature_schema(
    "add_revolve",
    "polyline",
    include_id=False,
)
OPENAI_SKETCH_ADD_REVOLVE_SCHEMA = build_revolve_feature_schema(
    "add_revolve",
    "sketch",
    include_id=False,
)

RECTANGLE_CUT_SCHEMA = build_cut_schema("rectangle")
CIRCLE_CUT_SCHEMA = build_cut_schema("circle")
POLYGON_CUT_SCHEMA = build_cut_schema("polygon")
POLYLINE_CUT_SCHEMA = build_cut_schema("polyline")
SKETCH_CUT_SCHEMA = build_cut_schema("sketch")

RELATIONAL_OPENAI_RECTANGLE_CUT_SCHEMA = build_cut_schema(
    "rectangle",
    require_id=True,
)
RELATIONAL_OPENAI_CIRCLE_CUT_SCHEMA = build_cut_schema(
    "circle",
    require_id=True,
)
RELATIONAL_OPENAI_POLYGON_CUT_SCHEMA = build_cut_schema(
    "polygon",
    require_id=True,
)
RELATIONAL_OPENAI_POLYLINE_CUT_SCHEMA = build_cut_schema(
    "polyline",
    require_id=True,
)
RELATIONAL_OPENAI_SKETCH_CUT_SCHEMA = build_cut_schema(
    "sketch",
    require_id=True,
)

OPENAI_RECTANGLE_CUT_SCHEMA = build_cut_schema(
    "rectangle",
    include_id=False,
)
OPENAI_CIRCLE_CUT_SCHEMA = build_cut_schema(
    "circle",
    include_id=False,
)
OPENAI_POLYGON_CUT_SCHEMA = build_cut_schema(
    "polygon",
    include_id=False,
)
OPENAI_POLYLINE_CUT_SCHEMA = build_cut_schema(
    "polyline",
    include_id=False,
)
OPENAI_SKETCH_CUT_SCHEMA = build_cut_schema(
    "sketch",
    include_id=False,
)

RECTANGLE_CUT_REVOLVE_SCHEMA = build_revolve_feature_schema("cut_revolve", "rectangle")
CIRCLE_CUT_REVOLVE_SCHEMA = build_revolve_feature_schema("cut_revolve", "circle")
POLYGON_CUT_REVOLVE_SCHEMA = build_revolve_feature_schema("cut_revolve", "polygon")
POLYLINE_CUT_REVOLVE_SCHEMA = build_revolve_feature_schema("cut_revolve", "polyline")
SKETCH_CUT_REVOLVE_SCHEMA = build_revolve_feature_schema("cut_revolve", "sketch")

RELATIONAL_OPENAI_RECTANGLE_CUT_REVOLVE_SCHEMA = build_revolve_feature_schema(
    "cut_revolve",
    "rectangle",
    require_id=True,
)
RELATIONAL_OPENAI_CIRCLE_CUT_REVOLVE_SCHEMA = build_revolve_feature_schema(
    "cut_revolve",
    "circle",
    require_id=True,
)
RELATIONAL_OPENAI_POLYGON_CUT_REVOLVE_SCHEMA = build_revolve_feature_schema(
    "cut_revolve",
    "polygon",
    require_id=True,
)
RELATIONAL_OPENAI_POLYLINE_CUT_REVOLVE_SCHEMA = build_revolve_feature_schema(
    "cut_revolve",
    "polyline",
    require_id=True,
)
RELATIONAL_OPENAI_SKETCH_CUT_REVOLVE_SCHEMA = build_revolve_feature_schema(
    "cut_revolve",
    "sketch",
    require_id=True,
)

OPENAI_RECTANGLE_CUT_REVOLVE_SCHEMA = build_revolve_feature_schema(
    "cut_revolve",
    "rectangle",
    include_id=False,
)
OPENAI_CIRCLE_CUT_REVOLVE_SCHEMA = build_revolve_feature_schema(
    "cut_revolve",
    "circle",
    include_id=False,
)
OPENAI_POLYGON_CUT_REVOLVE_SCHEMA = build_revolve_feature_schema(
    "cut_revolve",
    "polygon",
    include_id=False,
)
OPENAI_POLYLINE_CUT_REVOLVE_SCHEMA = build_revolve_feature_schema(
    "cut_revolve",
    "polyline",
    include_id=False,
)
OPENAI_SKETCH_CUT_REVOLVE_SCHEMA = build_revolve_feature_schema(
    "cut_revolve",
    "sketch",
    include_id=False,
)

OPERATION_SCHEMAS = [
    RECTANGLE_EXTRUDE_SCHEMA,
    CIRCLE_EXTRUDE_SCHEMA,
    POLYGON_EXTRUDE_SCHEMA,
    POLYLINE_EXTRUDE_SCHEMA,
    SKETCH_EXTRUDE_SCHEMA,
    RECTANGLE_REVOLVE_SCHEMA,
    CIRCLE_REVOLVE_SCHEMA,
    POLYGON_REVOLVE_SCHEMA,
    POLYLINE_REVOLVE_SCHEMA,
    SKETCH_REVOLVE_SCHEMA,
    RECTANGLE_ADD_EXTRUDE_SCHEMA,
    CIRCLE_ADD_EXTRUDE_SCHEMA,
    POLYGON_ADD_EXTRUDE_SCHEMA,
    POLYLINE_ADD_EXTRUDE_SCHEMA,
    SKETCH_ADD_EXTRUDE_SCHEMA,
    RECTANGLE_CUT_SCHEMA,
    CIRCLE_CUT_SCHEMA,
    POLYGON_CUT_SCHEMA,
    POLYLINE_CUT_SCHEMA,
    SKETCH_CUT_SCHEMA,
    RECTANGLE_ADD_REVOLVE_SCHEMA,
    CIRCLE_ADD_REVOLVE_SCHEMA,
    POLYGON_ADD_REVOLVE_SCHEMA,
    POLYLINE_ADD_REVOLVE_SCHEMA,
    SKETCH_ADD_REVOLVE_SCHEMA,
    RECTANGLE_CUT_REVOLVE_SCHEMA,
    CIRCLE_CUT_REVOLVE_SCHEMA,
    POLYGON_CUT_REVOLVE_SCHEMA,
    POLYLINE_CUT_REVOLVE_SCHEMA,
    SKETCH_CUT_REVOLVE_SCHEMA,
]

OPENAI_OPERATION_SCHEMAS = [
    RECTANGLE_EXTRUDE_SCHEMA,
    CIRCLE_EXTRUDE_SCHEMA,
    POLYGON_EXTRUDE_SCHEMA,
    POLYLINE_EXTRUDE_SCHEMA,
    SKETCH_EXTRUDE_SCHEMA,
    RECTANGLE_REVOLVE_SCHEMA,
    CIRCLE_REVOLVE_SCHEMA,
    POLYGON_REVOLVE_SCHEMA,
    POLYLINE_REVOLVE_SCHEMA,
    SKETCH_REVOLVE_SCHEMA,
    OPENAI_RECTANGLE_ADD_EXTRUDE_SCHEMA,
    OPENAI_CIRCLE_ADD_EXTRUDE_SCHEMA,
    OPENAI_POLYGON_ADD_EXTRUDE_SCHEMA,
    OPENAI_POLYLINE_ADD_EXTRUDE_SCHEMA,
    OPENAI_SKETCH_ADD_EXTRUDE_SCHEMA,
    OPENAI_RECTANGLE_CUT_SCHEMA,
    OPENAI_CIRCLE_CUT_SCHEMA,
    OPENAI_POLYGON_CUT_SCHEMA,
    OPENAI_POLYLINE_CUT_SCHEMA,
    OPENAI_SKETCH_CUT_SCHEMA,
    OPENAI_RECTANGLE_ADD_REVOLVE_SCHEMA,
    OPENAI_CIRCLE_ADD_REVOLVE_SCHEMA,
    OPENAI_POLYGON_ADD_REVOLVE_SCHEMA,
    OPENAI_POLYLINE_ADD_REVOLVE_SCHEMA,
    OPENAI_SKETCH_ADD_REVOLVE_SCHEMA,
    OPENAI_RECTANGLE_CUT_REVOLVE_SCHEMA,
    OPENAI_CIRCLE_CUT_REVOLVE_SCHEMA,
    OPENAI_POLYGON_CUT_REVOLVE_SCHEMA,
    OPENAI_POLYLINE_CUT_REVOLVE_SCHEMA,
    OPENAI_SKETCH_CUT_REVOLVE_SCHEMA,
]

RELATIONAL_OPENAI_OPERATION_SCHEMAS = [
    RECTANGLE_EXTRUDE_SCHEMA,
    CIRCLE_EXTRUDE_SCHEMA,
    POLYGON_EXTRUDE_SCHEMA,
    POLYLINE_EXTRUDE_SCHEMA,
    SKETCH_EXTRUDE_SCHEMA,
    RECTANGLE_REVOLVE_SCHEMA,
    CIRCLE_REVOLVE_SCHEMA,
    POLYGON_REVOLVE_SCHEMA,
    POLYLINE_REVOLVE_SCHEMA,
    SKETCH_REVOLVE_SCHEMA,
    RELATIONAL_OPENAI_RECTANGLE_ADD_EXTRUDE_SCHEMA,
    RELATIONAL_OPENAI_CIRCLE_ADD_EXTRUDE_SCHEMA,
    RELATIONAL_OPENAI_POLYGON_ADD_EXTRUDE_SCHEMA,
    RELATIONAL_OPENAI_POLYLINE_ADD_EXTRUDE_SCHEMA,
    RELATIONAL_OPENAI_SKETCH_ADD_EXTRUDE_SCHEMA,
    RELATIONAL_OPENAI_RECTANGLE_CUT_SCHEMA,
    RELATIONAL_OPENAI_CIRCLE_CUT_SCHEMA,
    RELATIONAL_OPENAI_POLYGON_CUT_SCHEMA,
    RELATIONAL_OPENAI_POLYLINE_CUT_SCHEMA,
    RELATIONAL_OPENAI_SKETCH_CUT_SCHEMA,
    RELATIONAL_OPENAI_RECTANGLE_ADD_REVOLVE_SCHEMA,
    RELATIONAL_OPENAI_CIRCLE_ADD_REVOLVE_SCHEMA,
    RELATIONAL_OPENAI_POLYGON_ADD_REVOLVE_SCHEMA,
    RELATIONAL_OPENAI_POLYLINE_ADD_REVOLVE_SCHEMA,
    RELATIONAL_OPENAI_SKETCH_ADD_REVOLVE_SCHEMA,
    RELATIONAL_OPENAI_RECTANGLE_CUT_REVOLVE_SCHEMA,
    RELATIONAL_OPENAI_CIRCLE_CUT_REVOLVE_SCHEMA,
    RELATIONAL_OPENAI_POLYGON_CUT_REVOLVE_SCHEMA,
    RELATIONAL_OPENAI_POLYLINE_CUT_REVOLVE_SCHEMA,
    RELATIONAL_OPENAI_SKETCH_CUT_REVOLVE_SCHEMA,
]

CAD_MODEL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "operations": {
            "type": "array",
            "items": {
                "anyOf": OPERATION_SCHEMAS,
            },
            "minItems": 1,
        },
        "relationships": RELATIONSHIPS_SCHEMA,
    },
    "required": ["operations"],
}

OPENAI_CAD_MODEL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "operations": {
            "type": "array",
            "items": {
                "anyOf": OPENAI_OPERATION_SCHEMAS,
            },
            "minItems": 1,
        }
    },
    "required": ["operations"],
}

OPENAI_RELATIONAL_CAD_MODEL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "operations": {
            "type": "array",
            "items": {
                "anyOf": RELATIONAL_OPENAI_OPERATION_SCHEMAS,
            },
            "minItems": 1,
        },
        "relationships": RELATIONSHIPS_SCHEMA,
    },
    "required": ["operations", "relationships"],
}


def validate_model_data(model_data: dict) -> None:
    """Validate model data against the shared CAD model schema."""
    try:
        validate(instance=model_data, schema=CAD_MODEL_SCHEMA)
    except ValidationError as error:
        raise ValueError(
            f"Model data does not match schema: {error.message}"
        ) from error
