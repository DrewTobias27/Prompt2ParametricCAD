"""Convert natural language CAD requests into structured model data."""

import json

from openai import OpenAI

from prompt2cad.schema import CAD_MODEL_SCHEMA


CAD_PROMPT_INSTRUCTIONS = """
You convert natural language CAD requests into JSON for a CadQuery-based
CAD interpreter. Return only valid model data. Use millimeters for all
dimensions.

The output must be an object with one key: operations.

The first operation should create the base solid:
- Use type "extrude".
- Use id "base".
- Use plane "XY".
- Choose one supported profile: "rectangle", "circle", "polygon", or "polyline".

Use these profile fields:
- rectangle: width and height
- circle: diameter
- polygon: sides and diameter
- polyline: points, as an ordered list of [x, y] points forming a closed
  straight-edged outline

After the base operation, use:
- type "add_extrude" to add material to an existing face
- type "cut" to remove material from an existing face

For add_extrude and cut operations:
- Use target "base.top" unless the user clearly requests a different face.
- Always use positions, even for one feature. Example: "positions": [[0, 0]]
- Use one operation with multiple positions for repeated identical features.
- Use distance for add_extrude operations.
- Use depth for cut operations. Use "through" for through-cuts.

If the user does not provide an exact dimension, choose a simple reasonable
dimension that keeps the part valid. Prefer simple valid geometry over fancy
geometry. Keep added extrusions connected to the base and keep cuts inside the
target face.
""".strip()


def create_openai_client() -> OpenAI:
    """Create an OpenAI API client using the OPENAI_API_KEY environment variable."""
    return OpenAI()


def prompt_to_model_data(user_prompt: str) -> dict:
    """Convert a natural language CAD request into structured model data."""
    client = create_openai_client()

    response = client.responses.create(
        model="gpt-5-mini",
        instructions=CAD_PROMPT_INSTRUCTIONS,
        input=user_prompt,
        text={
            "format": {
                "type": "json_schema",
                "name": "cad_model",
                "schema": CAD_MODEL_SCHEMA,
                "strict": True,
            }
        },
    )

    return json.loads(response.output_text)


def read_prompt_file(prompt_path: str) -> str:
    """Read and return the contents of a prompt file."""
    with open(prompt_path, "r", encoding="utf-8") as file:
        return file.read().strip()
