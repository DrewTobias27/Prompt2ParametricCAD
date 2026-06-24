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
- Use id "base".
- Use plane "XY".
- Use type "extrude" for prismatic parts made by pulling a 2D profile straight.
- Use type "revolve" for turned/lathe-style parts such as cylinders, shafts,
  bushings, knobs, or round parts described as revolved.
- Choose one supported profile: "rectangle", "circle", "polygon", or "polyline".

Use these profile fields:
- rectangle: width and height
- circle: diameter
- polygon: sides and diameter
- polyline: points, as an ordered list of [x, y] points forming a closed
  straight-edged outline
- Do not repeat the first point at the end of a polyline. The interpreter
  closes the outline automatically.

For revolve base operations:
- Use angle 360 for complete round parts.
- Use a smaller positive angle only when the user asks for a partial revolve,
  half cylinder, quarter cylinder, sector, or other incomplete rotation.
- Use positions to place the profile away from the revolve axis.
- Use axis_start and axis_end to define the revolve axis.
- axis_start and axis_end must be different points.
- For a vertical revolve axis in the XY plane, use axis_start [0, -1] and
  axis_end [0, 1].
- A common cylinder can be made by revolving a rectangle around a vertical
  axis in the XY plane. For example, a 20 mm diameter by 40 mm long cylinder
  can use a rectangle with width 10, height 40, positions [[5, 0]],
  axis_start [0, -1], axis_end [0, 1], and angle 360.

After the base operation, use:
- type "add_extrude" to add material to an existing face
- type "cut" to remove material from an existing face
- type "add_revolve" to add axisymmetric revolved material such as collars,
  raised rings, lips, or round bosses
- type "cut_revolve" to remove axisymmetric revolved material such as grooves,
  turned recesses, ring cuts, or lathe-style relief cuts

For add_extrude and cut operations:
- Use target "base.top" unless the user clearly requests a different face.
- Supported target names include "base.top", "base.bottom", "base.front",
  "base.back", "base.left", and "base.right" when those faces exist.
- Always use positions, even for one feature. Example: "positions": [[0, 0]]
- Use one operation with multiple positions for repeated identical features.
- Use distance for add_extrude operations.
- Use depth for cut operations. Use "through" for through-cuts.

For add_revolve and cut_revolve operations:
- Do not use target. These operations are positioned by plane, positions,
  axis_start, axis_end, and angle.
- Use plane "XY".
- Use positions to place the revolved feature profile relative to the axis.
- Use angle 360 for complete revolved features unless the user asks for a
  partial revolved feature.
- For features around the same axis as a revolved base cylinder, usually reuse
  axis_start [0, -1] and axis_end [0, 1].
- A collar on a 20 mm diameter shaft can be made with add_revolve using a
  rectangle centered at positions [[11, 0]], width 2, and the desired collar
  length as height.
- A groove in a 20 mm diameter shaft can be made with cut_revolve using a
  rectangle centered at positions [[9, 0]], width 2, and the desired groove
  length as height.

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
