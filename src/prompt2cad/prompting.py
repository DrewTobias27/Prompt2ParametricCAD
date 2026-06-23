"""Convert natural language CAD requests into structured model data."""

import json

from openai import OpenAI

from prompt2cad.schema import CAD_MODEL_SCHEMA


def create_openai_client() -> OpenAI:
    """Create an OpenAI API client using the OPENAI_API_KEY environment variable."""
    return OpenAI()


def prompt_to_model_data(user_prompt: str) -> dict:
    """Convert a natural language CAD request into structured model data."""
    client = create_openai_client()

    response = client.responses.create(
        model="gpt-5-mini",
        instructions=(
            "You convert natural language CAD requests into JSON for a "
            "CadQuery-based CAD interpreter. Return only valid model data. "
            "Use millimeters for all dimensions. For now, only create one "
            "rectangular base extrusion using type extrude, profile rectangle, "
            "plane XY, and id base."
        ),
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
