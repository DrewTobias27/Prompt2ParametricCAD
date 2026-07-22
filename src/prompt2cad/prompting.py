"""Convert natural language CAD requests into structured model data."""

import json
import os

from openai import APIStatusError
from openai import OpenAI

from prompt2cad.design_intent import OPENAI_DESIGN_INTENT_SCHEMA
from prompt2cad.design_intent import intent_to_model_data
from prompt2cad.diagnostics import check_model_data
from prompt2cad.example_library import format_examples_for_prompt
from prompt2cad.example_library import select_relevant_examples
from prompt2cad.quality import check_model_quality
from prompt2cad.schema import OPENAI_CAD_MODEL_SCHEMA
from prompt2cad.schema import OPENAI_RELATIONAL_CAD_MODEL_SCHEMA


BASE_SUGGESTION_INSTRUCTIONS = """
You create exactly one base extrusion operation for a CadQuery-based CAD
interpreter. Return only valid model data with one key: operations.

The operations array must contain exactly one operation.
The operation must:
- use type "extrude"
- use id "base"
- use plane "XY"
- use the requested profile exactly
- use millimeters
- choose simple reasonable dimensions when exact dimensions are not provided

Supported profiles:
- rectangle: include width, height, and distance
- circle: include diameter and distance
- polygon: include sides, diameter, and distance
- polyline: include points and distance

For polyline:
- points must be an ordered list of [x, y] points
- points must form a simple closed outline when connected in order
- do not repeat the first point at the end
- prefer simple, buildable outlines such as L-shapes, trapezoids, brackets,
  tabs, and stepped plates

Prefer simple valid geometry over fancy geometry.
""".strip()


FEATURE_SUGGESTION_INSTRUCTIONS = """
You create exactly one feature operation for an existing CadQuery-based CAD
model. Return only valid model data with one key: operations.

The operations array must contain exactly one operation.
The operation must:
- use the requested operation_type exactly
- use the requested target exactly
- use the requested profile exactly
- use millimeters
- choose simple reasonable dimensions and positions when exact values are not
  provided

Supported operation types:
- add_extrude: add material to a target face
- cut: remove material from a target face

Supported profiles:
- rectangle: include width and height
- circle: include diameter
- polygon: include sides and diameter
- polyline: include points

For all feature operations:
- include positions as a list containing one [x, y] point
- if unsure, use [[0, 0]]
- for add_extrude, include distance
- for cut, include depth. Use a positive number unless a through cut is clearly
  requested.

For polyline:
- points must be an ordered list of [x, y] points
- points must form a simple closed outline when connected in order
- do not repeat the first point at the end
- keep the outline small enough to fit on a typical base face

Prefer simple valid geometry over fancy geometry.
""".strip()


CAD_PROMPT_INSTRUCTIONS = """
You convert natural language CAD requests into JSON for a CadQuery-based
CAD interpreter. Return only valid model data. Use millimeters for all
dimensions.

The output must be an object with two keys:
- operations
- relationships

relationships must be an array. Use [] only for very simple one-feature parts.
For multi-feature parts, include relationship constraints that explain the
important design intent between features.

You may receive input as JSON with:
- user_prompt: the CAD request to satisfy
- retrieved_examples: similar solved examples from this project

Use retrieved_examples as guidance for construction strategy, feature order,
target names, profiles, and repeated-position patterns. Do not blindly copy an
example if its dimensions or features do not match the user_prompt.

Supported relationship constraints:
- centered_on: feature is centered on a reference feature or face.
  Example: {"type": "centered_on", "feature": "boss", "reference": "base", "tolerance": 0.001}
- inside: feature stays inside a container's top-view bounds.
  Example: {"type": "inside", "feature": "hole_pattern", "container": "base", "margin": 5}
- smaller_than: feature is proportionally smaller than a reference.
  Example: {"type": "smaller_than", "feature": "boss", "reference": "base", "max_width_fraction": 0.6, "max_height_fraction": 0.6}
- must_connect: feature must connect to another feature or solid.
  Example: {"type": "must_connect", "feature": "center_block", "to": "base"}

Use stable feature ids when relationships need to refer to added features.

The first operation should create the base solid:
- Use id "base".
- Use plane "XY".
- Use type "extrude" for prismatic parts made by pulling a 2D profile straight.
- Use type "revolve" for turned/lathe-style parts such as cylinders, shafts,
  bushings, knobs, or round parts described as revolved.
- Choose one supported profile: "rectangle", "circle", "polygon", "polyline",
  or "sketch".

Use these profile fields:
- rectangle: width and height
- circle: diameter
- polygon: sides and diameter
- polyline: points, as an ordered list of [x, y] points forming a closed
  straight-edged outline
- Do not repeat the first point at the end of a polyline. The interpreter
  closes the outline automatically.
- sketch: start and segments. Use sketch for outlines that need both straight
  lines and true circular arcs.
- sketch line segment: {"type": "line", "to": [x, y]}
- sketch arc segment: {"type": "arc", "through": [x, y], "to": [x, y]}
- sketch close must be true. The sketch may explicitly end at the start point,
  or the interpreter will close it automatically.
- Prefer sketch arcs over polyline approximations for rounded caps, domes,
  hemispheres, curved sides, and other circular-arc geometry.
- For sketch profiles, do not encode the same offset twice. If positions is
  [[0, 0]], sketch start and segment points may use absolute workplane
  coordinates. If positions is not [[0, 0]], sketch start and segment points
  must use local coordinates relative to that position.

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
- A capsule or cylinder with hemispherical ends can be made by revolving a
  sketch profile with arc segments around a vertical axis. For example, a
  20 mm diameter capsule with a 40 mm straight section can start at [0, -30],
  arc through [5, -28.660254] to [10, -20], line to [10, 20], arc through
  [5, 28.660254] to [0, 30], line back to [0, -30], then revolve 360 degrees.

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
  "base.back", "base.left", and "base.right".
- If an exact side face tag does not exist, the interpreter can use a virtual
  bounding-box target on that side. This is useful for polygon, polyline,
  sketch, rounded, or rotated-looking bases.
- Always use positions, even for one feature. Example: "positions": [[0, 0]]
- Use one operation with multiple positions for repeated identical features.
- On top or bottom targets, positions are normal top-view [x, y] coordinates.
- On side targets such as "base.front", "base.back", "base.left", or
  "base.right", positions are coordinates on that side face. The second
  coordinate is vertical height relative to the center of the side face. For
  thin plates or blocks, keep this second coordinate near 0 so the added
  extrusion or cut stays on the side face instead of floating above or below
  the part.
- Example: for a 10 mm thick square plate, a small boss on "base.front" should
  usually use a position like [[15, 0]], not [[15, 10]].
- Use distance for add_extrude operations.
- Use depth for cut operations. Use "through" for through-cuts.

For add_revolve and cut_revolve operations:
- Do not use target. These operations are positioned by plane, positions,
  axis_start, axis_end, and angle.
- Use plane "XY".
- Use positions to place the revolved feature profile relative to the axis.
- Added revolved solids must overlap or intersect the existing part enough to
  form one connected solid. Do not place add_revolve features so they merely
  touch tangentially or float beside the base.
- For visible external add_revolve features, do not bury the feature inside
  the base. Place it so it partially overlaps the base for connection but
  protrudes outside the base enough to be visible.
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

CAD_INTENT_INSTRUCTIONS = """
You convert natural language CAD requests into high-level design intent for a
deterministic CAD lowering system. Return only valid design-intent JSON.

The output must contain:
- required_concepts: the major semantic concepts that must appear in the
  generated intent
- base: the main solid
- features: cuts and extrusions added after the base
- edge_treatments: chamfers and fillets applied to existing feature edges.
  Use [] when the part does not need chamfers or fillets.

This is not the final CadQuery operation JSON. Use intent concepts such as
placement and shape so the backend can compute exact coordinates.

First identify the major nouns and manufacturing/CAD ideas in the request,
then include them in required_concepts using the supported role vocabulary.
Every required concept should be covered by either the base role, a feature
role, an edge-treatment role, or a clear feature id. Do not list a required
concept unless you also represent it in the intent.

Supported semantic roles:
- base_body, plate, mounting_plate, support_plate, cradle, bracket
- wall, rib, boss, hub, post, pad, tab, rim, lip, tube, collar
- hole, bolt_hole, counterbore, countersink, slot, key_slot, groove,
  o_ring_groove, pocket, cutout, drain, spoke
- chamfer, fillet

Use role fields to preserve design intent:
- Base role should describe the main body, such as plate, cradle, bracket,
  or base_body.
- Feature roles should describe why the feature exists, such as
  mounting_plate, boss, hole, slot, groove, wall, rib, rim, or drain.
- Edge-treatment roles should usually be chamfer or fillet.

Important concept coverage examples:
- If the prompt says mounting plate, support plate, or flat bottom plate,
  include a separate feature with role "mounting_plate" or "support_plate".
  Do not treat a flat face of another body as the plate unless the prompt
  only asks for a flat face.
- If the prompt says hole, slot, groove, rib, wall, boss, rim, collar,
  chamfer, or fillet, include a matching role or clear id for that concept.
  The backend checks for missing required concepts.

Supported base profiles:
- rectangle: flat rectangular plates/blocks
- circle: flat circular plates/flanges
- polygon: flat polygon plates
- d_shape: flat D-shaped plates with one straight back edge and one rounded
  front edge
- cylinder: shaft-like round parts described by diameter and length
- half_cylinder: half-round bases described by diameter and length
- capsule: shaft-like bodies with hemispherical/rounded ends, described by
  diameter and total length

Important base-profile choices:
- Use base profile "circle" for a circular flange, circular plate, disk, or
  ring unless the prompt clearly describes a shaft-like part with length.
  Do not use "cylinder" for a flat flange.
- Use base profile "d_shape" for a D-shaped plate with a flat back and rounded
  front. Do not use "half_cylinder" for a flat D-shaped plate.
- Use "half_cylinder" only for a 3D half-round cradle/body, not a flat plate
  outline.

Supported feature operations:
- extrusion: add material from a face target
- cut: remove material from a face target
- revolved_extrusion: add an axial collar/ring/band around a shaft-like base
- revolved_cut: remove an axial groove/ring/channel around a shaft-like base

Supported feature shapes:
- rectangle
- circle
- polygon
- polyline: arbitrary closed straight-edge profiles such as triangular ribs,
  L-shaped pads, custom tabs, or gussets. Use points to describe the outline.
- slot
- rounded_rectangle

Supported placements:
- centered: for centered bosses, holes, and slots
- explicit: when exact positions are given
- near_corners: for holes/features near 1 to 4 corners
- circular_pattern: for bolt circles or evenly spaced radial features
- rectangular_pattern: for row/column hole patterns
- mirrored: for features mirrored across x and/or y axes
- offset_from_edge: for features placed a set distance from a named edge
  or described as offset upward/downward/inward from an edge. Prefer this over
  explicit coordinates when the prompt describes an edge-relative position.
- same_as_feature: for child features that must reuse every instance position
  of an earlier feature. Include source_feature with that earlier feature's id.
  Use this for requests such as "one hole in each boss", "a hole in every
  tab", or concentric counterbores. The child should normally target the
  source feature's appropriate face, such as "corner_bosses.top".

Supported edge treatments:
- chamfer: needs distance
- fillet: needs radius

Supported edge selectors:
- top_outer_edges
- bottom_outer_edges
- vertical_edges
- all_edges

Use edge_treatments for real chamfers/fillets. Do not fake chamfers by
drawing diagonal sketch geometry unless the user asks for an unusual custom
profile that is not a normal edge treatment.

Use stable ids such as "corner_holes", "center_boss", "bolt_holes", or
"side_slot". Use target "base.top" unless a side or feature face is clearly
requested.

Parent-child feature rules:
- If a feature is described as being in, on, through, or concentric with an
  earlier feature, target that earlier feature rather than the base.
- When there is one child for every repeated parent, use same_as_feature so
  the child inherits exact positions instead of independently recomputing a
  similar near-corner, mirrored, or circular pattern.
- For a raised rim made as an outer extrusion followed by an inner cut, make
  the inner cut target the rim extrusion's top face.
- A single through cut may pass through multiple aligned, parallel walls.
  When one straight bore creates the requested hole in every aligned wall,
  output one cut from the nearest wall rather than duplicate cuts at the same
  axis; later duplicate cuts would have no physical effect.

Wall dimension rules for extrusion from a base top face:
- distance is the vertical wall height.
- For a wall along the left or right edge, rectangle width is wall thickness
  and rectangle height is the wall span along the base height.
- For a wall along the front or back edge, rectangle height is wall thickness
  and rectangle width is the wall span along the base width.

For shaft-like parts:
- Use base profile "cylinder" for normal shafts/cylinders that have diameter
  and length.
- Use base profile "capsule" for cylindrical bodies with hemispherical or
  rounded ends.
- Use revolved_extrusion with rectangle shape for raised collars, rings, and
  bands around a shaft. The rectangle width is radial thickness; height is
  axial width.
- Use revolved_cut with rectangle shape for grooves around a shaft. The
  rectangle width is radial cut depth; height is axial groove width.
- For centered collars/grooves, use centered placement. For features near one
  end, use offset_from_edge with edge "front" or "back".
- Do not include counterbore or countersink in required_concepts unless the
  prompt explicitly asks for a counterbore, countersink, recessed screw seat,
  or chamfered/conical hole.

For compound holes:
- A counterbore should be represented as a normal circular through-hole plus a
  larger, shallow, concentric circular cut with role "counterbore".
- A countersink should be represented as a normal circular through-hole plus a
  conical/revolved cut with role "countersink".
- An O-ring groove on a flat circular flange should usually be a shallow
  revolved_cut with role "o_ring_groove" on a circle base, not a shaft-like
  cylinder base. Include radius to locate the groove ring from the center.

For strict schema compatibility, fill unrelated numeric/string fields with
null. Examples:
- A circle feature needs diameter, but width, height, length, sides,
  radius, orientation, and unrelated distance/depth fields may be null.
- A cut uses depth. An extrusion uses distance.
- A revolved_extrusion or revolved_cut uses rectangle width and height, not
  distance or depth.
- A polyline feature needs at least three outline points. These points describe
  the closed sketch shape; placement describes where that sketch instance is
  located.
- A rounded_rectangle feature needs width, height, and radius.
- A near_corners placement should include count and may use margin null when
  the backend should choose a default.
- A circular_pattern placement should include count and may use radius null
  when the backend should choose a reasonable radius.

Do not use null for dimensions required by the chosen base profile, feature
shape, or operation. If the user asks for a hole, boss, slot, flange, or other
feature without exact dimensions, choose simple reasonable numeric dimensions
proportional to the base. For example:
- A circular hole must include a numeric diameter.
- A rectangular boss must include numeric width, height, and distance.
- A slot must include numeric length and width.
- A triangular rib should usually use shape "polyline" with three outline
  points, not a polygon diameter.
- A cylinder, half_cylinder, or capsule base must include numeric diameter and
  length.
- A chamfer must include numeric distance; a fillet must include numeric radius.

Prefer clear relationships over exact coordinates. For example, for "four
holes near the corners", use one circle cut feature with near_corners
placement instead of manually calculating four positions.
""".strip()


CAD_REPAIR_INSTRUCTIONS = """
You repair JSON model data for a CadQuery-based CAD interpreter. Return only
valid model data with two keys: operations and relationships.

You will receive:
- the original user prompt
- failed CAD JSON
- local CAD failure analysis
- a structured quality report with issue codes, messages, and suggestions

Your job is to revise the JSON so it preserves the user's intent while fixing
the identified CAD problem.

Important repair rules:
- Do not return the same geometry with tiny numeric changes.
- Use the failure reason, quality issue codes, and suggested fixes directly.
- The final model must build as one connected, valid solid.
- Fix every quality-report error and any repairable target-kind warning.
- If an inner object sits inside a through-cut frame opening, either add bridge
  tabs/ribs connecting it to the frame or replace the through cut with a shallow
  pocket/recess.
- Keep added extrusions overlapping existing solid material.
- Keep cuts inside the target face.
- Preserve useful relationship constraints and update them when the repaired
  geometry changes.
- Prefer simple, robust geometry over clever fragile geometry.
""".strip()


REPAIRABLE_QUALITY_WARNING_CODES = {
    "edge_operation_targets_face",
    "face_operation_targets_edge",
}
DEFAULT_OPENAI_MODEL = "gpt-5-mini"


def parse_json_response_text(response_text: str) -> dict:
    """Parse JSON from an API response that may include Markdown fences."""
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])


def is_bad_request(error: Exception) -> bool:
    """Return whether an OpenAI SDK exception represents HTTP status 400."""
    return isinstance(error, APIStatusError) and error.status_code == 400


def create_json_response(
    client: OpenAI,
    *,
    model: str,
    instructions: str,
    input_text: str,
    schema: dict,
    schema_name: str,
) -> dict:
    """Create a structured JSON response, with a JSON-only fallback for demos.

    Structured Outputs are the preferred path because they constrain the model
    tightly. If the OpenAI API rejects the schema request with a 400, retry with
    plain JSON instructions so prompt mode can still run instead of failing
    completely.
    """
    try:
        response = client.responses.create(
            model=model,
            instructions=instructions,
            input=input_text,
            text={
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "schema": schema,
                    "strict": True,
                }
            },
        )
    except APIStatusError as error:
        if not is_bad_request(error):
            raise
        fallback_instructions = (
            instructions
            + "\n\nThe strict JSON schema request was rejected. Return only one "
            + "valid JSON object. Do not include Markdown, explanations, or code fences."
        )
        try:
            response = client.responses.create(
                model=model,
                instructions=fallback_instructions,
                input=input_text,
            )
        except APIStatusError as fallback_error:
            detail = fallback_error.body or str(fallback_error)
            raise RuntimeError(
                "OpenAI JSON fallback failed "
                f"(HTTP {fallback_error.status_code}): {detail}"
            ) from fallback_error

    return parse_json_response_text(response.output_text)


def create_openai_client() -> OpenAI:
    """Create an OpenAI API client using the OPENAI_API_KEY environment variable."""
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key is not None:
        return OpenAI(api_key=api_key.strip())

    return OpenAI()


def openai_model(task: str = "generation") -> str:
    """Return the configured OpenAI model for a prompt task."""
    task_specific_env = f"PROMPT2CAD_{task.upper()}_MODEL"
    return (
        os.getenv(task_specific_env)
        or os.getenv("PROMPT2CAD_OPENAI_MODEL")
        or DEFAULT_OPENAI_MODEL
    )


def build_generation_input(user_prompt: str, max_examples: int = 3) -> str:
    """Build the API input with locally retrieved CAD examples."""
    examples = select_relevant_examples(
        user_prompt,
        max_examples=max_examples,
    )
    if not examples:
        return user_prompt

    generation_input = {
        "user_prompt": user_prompt,
        "retrieved_examples": json.loads(format_examples_for_prompt(examples)),
    }
    return json.dumps(generation_input, indent=2)


def prompt_to_model_data(user_prompt: str) -> dict:
    """Convert a natural language CAD request into structured model data."""
    client = create_openai_client()

    return create_json_response(
        client,
        model=openai_model("generation"),
        instructions=CAD_PROMPT_INSTRUCTIONS,
        input_text=build_generation_input(user_prompt),
        schema=OPENAI_RELATIONAL_CAD_MODEL_SCHEMA,
        schema_name="cad_model",
    )


def prompt_to_design_intent(user_prompt: str) -> dict:
    """Convert a natural language CAD request into high-level design intent."""
    client = create_openai_client()

    return create_json_response(
        client,
        model=openai_model("intent"),
        instructions=CAD_INTENT_INSTRUCTIONS,
        input_text=build_generation_input(user_prompt),
        schema=OPENAI_DESIGN_INTENT_SCHEMA,
        schema_name="cad_design_intent",
    )


def prompt_to_model_data_via_intent(user_prompt: str) -> dict:
    """Generate design intent first, then lower it into CAD model data."""
    design_intent = prompt_to_design_intent(user_prompt)
    return intent_to_model_data(design_intent)


def repair_model_data(
    user_prompt: str,
    failed_model_data: dict,
    failure_analysis: dict,
) -> dict:
    """Ask the model to repair failed CAD JSON using local diagnostics."""
    client = create_openai_client()
    repair_request = {
        "user_prompt": user_prompt,
        "failed_model_data": failed_model_data,
        "failure_analysis": failure_analysis,
    }

    return create_json_response(
        client,
        model=openai_model("repair"),
        instructions=CAD_REPAIR_INSTRUCTIONS,
        input_text=json.dumps(repair_request),
        schema=OPENAI_RELATIONAL_CAD_MODEL_SCHEMA,
        schema_name="cad_repaired_model",
    )


def quality_report_needs_repair(quality_report: dict) -> bool:
    """Return whether quality issues should trigger an API repair attempt."""
    if not quality_report.get("passed", False):
        return True

    return any(
        issue.get("code") in REPAIRABLE_QUALITY_WARNING_CODES
        for issue in quality_report.get("issues", [])
    )


def quality_issue_suggestions(quality_report: dict) -> list[str]:
    """Return concise repair suggestions from quality issues."""
    suggestions = []
    for issue in quality_report.get("issues", []):
        suggestion = issue.get("suggestion")
        if suggestion and suggestion not in suggestions:
            suggestions.append(suggestion)

    return suggestions


def build_repair_failure_analysis(model_data: dict) -> dict:
    """Combine build diagnostics and quality-gate output for repair."""
    diagnostics = check_model_data(model_data)
    quality_report = check_model_quality(model_data)
    needs_repair = (
        not diagnostics.get("passed", False)
        or quality_report_needs_repair(quality_report)
    )

    if not needs_repair:
        return {
            "passed": True,
            "failure_type": None,
            "reason": "Model data passed diagnostics and quality checks.",
            "suggested_fixes": [],
            "diagnostics": diagnostics,
            "quality_report": quality_report,
        }

    suggested_fixes = list(diagnostics.get("suggested_fixes", []))
    for suggestion in quality_issue_suggestions(quality_report):
        if suggestion not in suggested_fixes:
            suggested_fixes.append(suggestion)

    repairable_quality_codes = [
        issue.get("code")
        for issue in quality_report.get("issues", [])
        if issue.get("severity") == "error"
        or issue.get("code") in REPAIRABLE_QUALITY_WARNING_CODES
    ]

    return {
        "passed": False,
        "failure_type": (
            diagnostics.get("failure_type")
            or "quality_gate_failed"
        ),
        "reason": diagnostics.get(
            "reason",
            "The model failed diagnostics or quality-gate checks.",
        ),
        "suggested_fixes": suggested_fixes,
        "repairable_quality_codes": repairable_quality_codes,
        "diagnostics": diagnostics,
        "quality_report": quality_report,
    }


def prompt_to_model_data_with_repair(
    user_prompt: str,
    max_repairs: int = 1,
) -> tuple[dict, list[dict]]:
    """Generate CAD JSON and use at most a small number of repair attempts."""
    model_data = prompt_to_model_data(user_prompt)
    repair_history = []

    for _ in range(max_repairs):
        failure_analysis = build_repair_failure_analysis(model_data)
        if failure_analysis["passed"]:
            return model_data, repair_history

        repaired_model_data = repair_model_data(
            user_prompt,
            model_data,
            failure_analysis,
        )
        repair_history.append(
            {
                "failure_analysis": failure_analysis,
                "failed_model_data": model_data,
                "repaired_model_data": repaired_model_data,
            }
        )
        model_data = repaired_model_data

    return model_data, repair_history


def suggest_base_model_data(
    profile: str,
    description: str = "",
    distance: float | None = None,
) -> dict:
    """Suggest one base extrusion model from a selected profile."""
    client = create_openai_client()
    request_data = {
        "profile": profile,
        "description": description,
        "distance": distance,
    }

    return create_json_response(
        client,
        model=openai_model("base_suggestion"),
        instructions=BASE_SUGGESTION_INSTRUCTIONS,
        input_text=json.dumps(request_data),
        schema=OPENAI_CAD_MODEL_SCHEMA,
        schema_name="cad_base_model",
    )


def suggest_feature_model_data(
    operation_type: str,
    target: str,
    profile: str,
    description: str = "",
) -> dict:
    """Suggest one feature operation from selected manual builder controls."""
    client = create_openai_client()
    request_data = {
        "operation_type": operation_type,
        "target": target,
        "profile": profile,
        "description": description,
    }

    return create_json_response(
        client,
        model=openai_model("feature_suggestion"),
        instructions=FEATURE_SUGGESTION_INSTRUCTIONS,
        input_text=json.dumps(request_data),
        schema=OPENAI_CAD_MODEL_SCHEMA,
        schema_name="cad_feature_model",
    )


def read_prompt_file(prompt_path: str) -> str:
    """Read and return the contents of a prompt file."""
    with open(prompt_path, "r", encoding="utf-8") as file:
        return file.read().strip()
