"""Shared JSON schemas for Prompt2ParametricCAD model data."""

from jsonschema import ValidationError
from jsonschema import validate


CAD_MODEL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "operations": {
            "type": "array",
            "items": {
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
                        "enum": ["rectangle"],
                    },
                    "width": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                    },
                    "height": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                    },
                    "distance": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                    },
                },
                "required": [
                    "type",
                    "id",
                    "plane",
                    "profile",
                    "width",
                    "height",
                    "distance",
                ],
            },
        }
    },
    "required": ["operations"],
}


def validate_model_data(model_data: dict) -> None:
    """Validate model data against the shared CAD model schema."""
    try:
        validate(instance=model_data, schema=CAD_MODEL_SCHEMA)
    except ValidationError as error:
        raise ValueError(
            f"Model data does not match schema: {error.message}"
        ) from error
