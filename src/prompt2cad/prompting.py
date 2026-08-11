"""Convert natural language CAD requests into structured model data."""

import json
import os
import re
from time import perf_counter

from openai import APIStatusError
from openai import OpenAI

from prompt2cad.candidate_evaluation import evaluate_design_intent_candidate
from prompt2cad.candidate_evaluation import evaluate_model_candidate
from prompt2cad.candidate_evaluation import quality_report_needs_repair
from prompt2cad.candidate_evaluation import REPAIRABLE_QUALITY_WARNING_CODES
from prompt2cad.design_intent import OPENAI_DESIGN_INTENT_SCHEMA
from prompt2cad.design_intent import design_intent_from_openai
from prompt2cad.design_intent import design_intent_to_openai
from prompt2cad.design_intent import intent_to_model_data
from prompt2cad.diagnostics import check_model_data
from prompt2cad.example_library import format_examples_for_prompt
from prompt2cad.example_library import format_intent_examples_for_prompt
from prompt2cad.example_library import select_relevant_examples
from prompt2cad.example_library import select_relevant_intent_examples
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
  Mirror-axis geometry follows standard sketch coordinates:
  - x axis maps [x, y] to [x, -y]; the seed y must be nonzero.
  - y axis maps [x, y] to [-x, y]; the seed x must be nonzero.
  - both axes normally create four distinct positions, so both seed
    coordinates must be nonzero.
  Never request an axis that leaves the seed unchanged. For two features at
  positive and negative X, use axes ["y"], not ["x"].
- offset_from_edge: for features placed a set distance from a named edge
  or described as offset upward/downward/inward from an edge. Prefer this over
  explicit coordinates when the prompt describes an edge-relative position.
  offset is the inward distance perpendicular to the edge. along is the
  feature-center coordinate parallel to the edge, measured from the target
  center; use along 0 for a centered wall or feature. Never put the feature's
  width, height, span, or length in along.
  For near-corner circles, margin is clearance from the circle's outside edge
  to the parent outline, not the center-to-edge distance. If the user gives a
  center-to-edge distance, subtract the circle radius to obtain margin, or use
  explicit positions when exact centers are clearer.
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

Target-reference rules:
- Face targets must use "parent_id.face_name".
- The supported semantic face names are top, bottom, front, back, left, and
  right. Choose the face whose normal matches the requested feature direction.
- Never invent generic names such as side, outer_face, inner_face, flat, or
  curved. If the prompt is ambiguous, choose the most suitable supported face.
- Only target a feature declared earlier in build order.
- Every item in required_concepts must be visibly represented by a base role,
  feature role, edge-treatment role, or a clear id. For example, if bracket is
  required, use role "bracket" or include bracket in the base id.

Parent-child feature rules:
- If a feature is described as being in, on, through, or concentric with an
  earlier feature, target that earlier feature rather than the base.
- When there is one child for every repeated parent, use same_as_feature so
  the child inherits exact positions instead of independently recomputing a
  similar near-corner, mirrored, or circular pattern.
- A hole through a vertical wall must target the appropriate vertical side
  face of that wall. Do not target the wall's top face, which is its horizontal
  cap and produces a cut in the wrong direction.
- Coordinates on a vertical side face are local face coordinates: the first
  coordinate runs horizontally along the face and the second runs vertically
  from the face center. If a wall is H tall and a hole center is h above the
  wall base, use explicit position [[0, h - H/2]] when it is horizontally
  centered. Do not encode the requested height as offset_from_edge along.
- For a raised rim made as an outer extrusion followed by an inner cut, make
  the inner cut target the rim extrusion's top face. Give that inner cut a
  numeric depth equal to the rim extrusion distance so it removes only the
  raised material. Do not use "through" unless the request explicitly asks
  for the opening to continue through the body below the rim.
- When a tray is built from a thin bottom plus separate wall extrusions, start
  the rim on a wall top face and extrude only the rim height. Do not add wall
  height to rim distance. The centered inner rim cut must equal that same rim
  distance.
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

Coplanar side-extension rules:
- A tab, ear, or flange that extends the base outline while keeping the same
  thickness is not a raised top-face extrusion. Target base.left, base.right,
  base.front, or base.back and use distance for the outward extension.
- On that vertical side face, size the sketch to the requested in-plane tab
  span and the existing base thickness. Do not extrude a second base thickness
  upward from base.top.

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
- For an exact axial center, explicit placement stores the axial coordinate in
  the second value: use [[0, axial_center]], such as [[0, -25]] and [[0, 25]].
- For a collar with requested outside diameter D on a shaft diameter d, radial
  width is (D - d) / 2, axial height is the requested collar width, and the
  inferred radius should normally be omitted. Example: a 36 mm collar on a
  24 mm shaft that is 8 mm wide uses width 6 and height 8.
- For a circumferential groove 2 mm deep and 3 mm wide, use radial width 2 and
  axial height 3. Omit radius unless the request gives a nonstandard radial
  centerline.
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

Each base, feature shape, operation, and edge treatment has its own strict
schema. Return only fields that apply to that variant. Examples:
- A circle feature uses diameter; do not add width, height, length, or sides.
- A cut uses depth. An extrusion uses distance.
- A revolved_extrusion or revolved_cut uses its profile dimensions, not
  distance or depth. A rectangle revolved feature includes radius only when
  an explicit radial location is needed; otherwise omit it for inference.
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

CAD_INTENT_REPAIR_INSTRUCTIONS = """
You repair high-level CAD design intent after deterministic lowering and
CadQuery geometry evaluation. Return one complete replacement design-intent
object that follows the supplied strict schema.

The input contains:
- user_prompt: the original request, which remains authoritative
- failed_design_intent: the previous candidate
- evaluation_feedback: deterministic failures from intent coverage, lowering,
  solid construction, geometry checks, and per-operation effect checks

Fix the causes identified by evaluation_feedback while preserving every
requested concept that was already represented correctly. Do not merely rename
features to satisfy concept coverage. Correct dimensions, placements, targets,
parent-child relationships, feature order, and feature count as needed.

When missing_required_dimensions is non-empty, keep the valid design structure
and fill every listed field. Reuse dimensions stated by the user; otherwise
choose simple, proportional millimeter values that fit the parent geometry.

Every additive feature must intersect existing material. Every cut must remove
measurable material. Every repeated instance must affect the intended target.
For revolved rectangle features, width is radial depth/thickness, height is
axial width, and explicit axial placement uses [0, axial_center]. A repeated
collar or groove must use a different axial center for every requested copy.
For a same_as_feature child of an additive boss/tab, target that parent
feature's material face rather than the base. For side-face features, use
local coordinates [horizontal_from_center, vertical_from_center]. A hollow
rim's inner cut depth must equal the rim extrusion distance. A coplanar tab
extending the base outline must start on a side face, not the base top. When a
prompt gives a circular feature's center-to-edge distance, convert it to exact
positions or subtract the feature radius before using near_corners.margin.
Prefer the smallest change that satisfies the original request and all reported
failures. Return JSON only.
""".strip()


CAD_INTENT_REFINEMENT_INSTRUCTIONS = """
You revise an existing high-level CAD design intent in response to a user's
correction. Return one complete replacement design-intent object that follows
the supplied strict schema.

The input contains:
- original_user_prompt: the original CAD request
- user_correction: what the user wants changed in the most recent result
- previous_design_intent: the complete current design intent

Treat the correction as the requested change to the current model, not as a
new request from scratch. Preserve the base, feature ids, feature order,
relationships, dimensions, and edge treatments that the correction does not
affect. Keep existing ids whenever a feature remains; assign a new unique id
only for a genuinely new feature. Remove a feature only when the correction
explicitly requests its removal.

Return a complete, buildable design intent. Every additive feature must
intersect existing material, every cut must remove measurable material, and
all target/parent-child references must remain valid after the revision. Use
the original prompt to retain design requirements that the correction does not
mention. If the correction asks for an imprecise change, choose reasonable
proportional dimensions rather than omitting required fields.

Placement distance semantics are directional and relative to the previous
intent:
- near_corners.margin is clearance between the feature's outside edge and the
  parent outline. Increasing it moves the feature inward; decreasing it moves
  the feature toward the edge.
- offset_from_edge.offset is inward distance from the named edge. Increasing
  it moves the feature inward.
- circular_pattern.radius is center-to-center radius. Decreasing it moves the
  pattern inward toward the parent center.
- When a correction says to move a feature inward or outward by a distance,
  apply that distance as a delta to the existing placement value. Do not
  replace the existing value with the requested movement distance.
""".strip()


DEFAULT_OPENAI_MODEL = "gpt-5.5"
DEFAULT_OPENAI_REASONING_EFFORT = "low"
DEFAULT_MAX_REPAIRS = 3
MAX_CONFIGURED_REPAIRS = 3
SUPPORTED_REASONING_EFFORTS = {
    "none",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
}


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
    telemetry: dict | None = None,
    reasoning_effort: str | None = None,
) -> dict:
    """Create a structured JSON response, with a JSON-only fallback for demos.

    Structured Outputs are the preferred path because they constrain the model
    tightly. If the OpenAI API rejects the schema request with a 400, retry with
    plain JSON instructions so prompt mode can still run instead of failing
    completely.
    """
    request_options = {
        "model": model,
        "input": input_text,
    }
    if reasoning_effort is not None:
        request_options["reasoning"] = {"effort": reasoning_effort}

    api_started_at = perf_counter()
    api_attempts = 1
    used_structured_outputs = True
    try:
        response = client.responses.create(
            **request_options,
            instructions=instructions,
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
        api_attempts = 2
        used_structured_outputs = False
        fallback_instructions = (
            instructions
            + "\n\nThe strict JSON schema request was rejected. Return only one "
            + "valid JSON object. Do not include Markdown, explanations, or code fences."
        )
        try:
            response = client.responses.create(
                **request_options,
                instructions=fallback_instructions,
            )
        except APIStatusError as fallback_error:
            detail = fallback_error.body or str(fallback_error)
            raise RuntimeError(
                "OpenAI JSON fallback failed "
                f"(HTTP {fallback_error.status_code}): {detail}"
            ) from fallback_error

    if telemetry is not None:
        telemetry.update(
            response_usage_telemetry(
                response,
                requested_model=model,
                api_attempts=api_attempts,
                used_structured_outputs=used_structured_outputs,
                requested_reasoning_effort=reasoning_effort,
            )
        )
        telemetry["api_seconds"] = round(perf_counter() - api_started_at, 3)

    return parse_json_response_text(response.output_text)


def response_usage_telemetry(
    response,
    *,
    requested_model: str,
    api_attempts: int,
    used_structured_outputs: bool,
    requested_reasoning_effort: str | None,
) -> dict:
    """Return non-secret model and token metadata from an API response."""
    usage = getattr(response, "usage", None)
    input_details = getattr(usage, "input_tokens_details", None)
    output_details = getattr(usage, "output_tokens_details", None)

    telemetry = {
        "requested_model": requested_model,
        "response_model": getattr(response, "model", None),
        "api_attempts": api_attempts,
        "structured_outputs": used_structured_outputs,
        "requested_reasoning_effort": requested_reasoning_effort,
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
        "cached_input_tokens": getattr(input_details, "cached_tokens", None),
        "reasoning_tokens": getattr(output_details, "reasoning_tokens", None),
    }
    return {
        key: value
        for key, value in telemetry.items()
        if value is not None
    }


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


def openai_reasoning_effort(task: str = "generation") -> str | None:
    """Return an optional configured reasoning effort for one API task."""
    task_specific_env = f"PROMPT2CAD_{task.upper()}_REASONING_EFFORT"
    value = (
        os.getenv(task_specific_env)
        or os.getenv("PROMPT2CAD_REASONING_EFFORT")
        or DEFAULT_OPENAI_REASONING_EFFORT
    )
    if not value.strip():
        return None

    effort = value.strip().lower()
    if effort not in SUPPORTED_REASONING_EFFORTS:
        supported = ", ".join(sorted(SUPPORTED_REASONING_EFFORTS))
        raise ValueError(
            f"Unsupported reasoning effort '{effort}'. Supported values: {supported}."
        )
    return effort


def max_repair_attempts(task: str = "generation") -> int:
    """Return a bounded repair count, configurable without code changes."""
    task_specific_env = f"PROMPT2CAD_{task.upper()}_MAX_REPAIRS"
    raw_value = (
        os.getenv(task_specific_env)
        or os.getenv("PROMPT2CAD_MAX_REPAIRS")
    )
    if raw_value is None or not raw_value.strip():
        return DEFAULT_MAX_REPAIRS

    try:
        attempts = int(raw_value)
    except ValueError as error:
        raise ValueError(f"{task_specific_env} must be an integer") from error
    if not 0 <= attempts <= MAX_CONFIGURED_REPAIRS:
        raise ValueError(
            f"{task_specific_env} must be between 0 and {MAX_CONFIGURED_REPAIRS}"
        )
    return attempts


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


def build_intent_generation_input(
    user_prompt: str,
    max_examples: int = 2,
) -> str:
    """Build intent API input from matching prompt-to-intent examples."""
    examples = select_relevant_intent_examples(
        user_prompt,
        max_examples=max_examples,
    )
    if not examples:
        return user_prompt

    generation_input = {
        "user_prompt": user_prompt,
        "retrieved_intent_examples": json.loads(
            format_intent_examples_for_prompt(examples)
        ),
    }
    return json.dumps(generation_input, indent=2)


def prompt_to_model_data(
    user_prompt: str,
    *,
    telemetry: dict | None = None,
) -> dict:
    """Convert a natural language CAD request into structured model data."""
    client = create_openai_client()

    return create_json_response(
        client,
        model=openai_model("generation"),
        instructions=CAD_PROMPT_INSTRUCTIONS,
        input_text=build_generation_input(user_prompt),
        schema=OPENAI_RELATIONAL_CAD_MODEL_SCHEMA,
        schema_name="cad_model",
        telemetry=telemetry,
        reasoning_effort=openai_reasoning_effort("generation"),
    )


def prompt_to_design_intent(
    user_prompt: str,
    *,
    telemetry: dict | None = None,
) -> dict:
    """Convert a natural language CAD request into high-level design intent."""
    client = create_openai_client()

    response_intent = create_json_response(
        client,
        model=openai_model("intent"),
        instructions=CAD_INTENT_INSTRUCTIONS,
        input_text=build_intent_generation_input(user_prompt),
        schema=OPENAI_DESIGN_INTENT_SCHEMA,
        schema_name="cad_design_intent",
        telemetry=telemetry,
        reasoning_effort=openai_reasoning_effort("intent"),
    )
    return design_intent_from_openai(response_intent)


def repair_design_intent(
    user_prompt: str,
    failed_design_intent: dict,
    evaluation_feedback: dict,
    *,
    telemetry: dict | None = None,
) -> dict:
    """Ask the API to repair design intent using deterministic CAD feedback."""
    client = create_openai_client()
    repair_request = {
        "user_prompt": user_prompt,
        "failed_design_intent": design_intent_to_openai(failed_design_intent),
        "evaluation_feedback": evaluation_feedback,
    }
    response_intent = create_json_response(
        client,
        model=openai_model("intent_repair"),
        instructions=CAD_INTENT_REPAIR_INSTRUCTIONS,
        input_text=json.dumps(repair_request),
        schema=OPENAI_DESIGN_INTENT_SCHEMA,
        schema_name="cad_repaired_design_intent",
        telemetry=telemetry,
        reasoning_effort=openai_reasoning_effort("intent_repair"),
    )
    return design_intent_from_openai(response_intent)


def refine_design_intent(
    user_prompt: str,
    previous_design_intent: dict,
    correction: str,
    *,
    telemetry: dict | None = None,
) -> dict:
    """Revise a saved design intent using a focused user correction."""
    client = create_openai_client()
    refinement_request = {
        "original_user_prompt": user_prompt,
        "user_correction": correction,
        "previous_design_intent": design_intent_to_openai(
            previous_design_intent
        ),
    }
    response_intent = create_json_response(
        client,
        model=openai_model("intent_refinement"),
        instructions=CAD_INTENT_REFINEMENT_INSTRUCTIONS,
        input_text=json.dumps(refinement_request),
        schema=OPENAI_DESIGN_INTENT_SCHEMA,
        schema_name="cad_refined_design_intent",
        telemetry=telemetry,
        reasoning_effort=openai_reasoning_effort("intent_refinement"),
    )
    return design_intent_from_openai(response_intent)


def evaluate_design_intent_with_feedback(
    repair_prompt: str,
    design_intent: dict,
    max_repairs: int,
    *,
    telemetry: dict | None = None,
    initial_telemetry: dict | None = None,
    additional_evaluator=None,
) -> tuple[dict, dict | None, list[dict], dict]:
    """Evaluate one intent and repair it only when deterministic checks fail."""
    api_calls: list[dict] = []
    if initial_telemetry is not None:
        api_calls.append(initial_telemetry)
        if telemetry is not None:
            update_aggregate_telemetry(telemetry, api_calls)

    repair_history = []
    for attempt_number in range(max_repairs + 1):
        evaluation = evaluate_design_intent_candidate(design_intent)
        if additional_evaluator is not None:
            additional_feedback = additional_evaluator(design_intent)
            if additional_feedback:
                evaluation = dict(evaluation)
                evaluation["passed"] = False
                evaluation["feedback"] = dict(
                    evaluation.get("feedback", {})
                )
                evaluation["feedback"]["refinement_semantics"] = (
                    additional_feedback
                )
        if evaluation["passed"] or attempt_number == max_repairs:
            return (
                design_intent,
                evaluation.get("model_data"),
                repair_history,
                evaluation,
            )

        try:
            repair_telemetry = {} if telemetry is not None else None
            repaired_intent = repair_design_intent(
                repair_prompt,
                design_intent,
                evaluation["feedback"],
                telemetry=repair_telemetry,
            ) if repair_telemetry is not None else repair_design_intent(
                repair_prompt,
                design_intent,
                evaluation["feedback"],
            )
            if repair_telemetry is not None:
                api_calls.append(repair_telemetry)
                update_aggregate_telemetry(telemetry, api_calls)
        except Exception as error:
            error.intent_repair_history = repair_history
            error.intent_api_attempts = 1 + len(repair_history) + 1
            error.design_intent = design_intent
            if telemetry is not None:
                error.api_telemetry = dict(telemetry)
            raise

        repair_history.append({
            "attempt": attempt_number + 1,
            "evaluation_feedback": evaluation["feedback"],
            "failed_design_intent": design_intent,
            "repaired_design_intent": repaired_intent,
        })
        if repaired_intent == design_intent:
            repair_history[-1]["stopped_reason"] = "unchanged_candidate"
            return (
                design_intent,
                evaluation.get("model_data"),
                repair_history,
                evaluation,
            )
        design_intent = repaired_intent

    raise AssertionError("Unreachable design-intent repair loop state")


def prompt_to_design_intent_with_feedback(
    user_prompt: str,
    max_repairs: int | None = None,
    *,
    telemetry: dict | None = None,
) -> tuple[dict, dict | None, list[dict], dict]:
    """Generate intent, then conditionally complete or repair failed candidates."""
    if max_repairs is None:
        max_repairs = max_repair_attempts("intent")

    initial_telemetry = {} if telemetry is not None else None
    design_intent = prompt_to_design_intent(
        user_prompt,
        telemetry=initial_telemetry,
    ) if initial_telemetry is not None else prompt_to_design_intent(user_prompt)
    return evaluate_design_intent_with_feedback(
        user_prompt,
        design_intent,
        max_repairs,
        telemetry=telemetry,
        initial_telemetry=initial_telemetry,
    )


def refine_design_intent_with_feedback(
    user_prompt: str,
    previous_design_intent: dict,
    correction: str,
    max_repairs: int | None = None,
    *,
    telemetry: dict | None = None,
) -> tuple[dict, dict | None, list[dict], dict]:
    """Revise saved intent, then run the normal deterministic repair loop."""
    correction = correction.strip()
    if not correction:
        raise ValueError("Correction must not be empty")
    if max_repairs is None:
        max_repairs = max_repair_attempts("intent")

    initial_telemetry = {} if telemetry is not None else None
    design_intent = refine_design_intent(
        user_prompt,
        previous_design_intent,
        correction,
        telemetry=initial_telemetry,
    ) if initial_telemetry is not None else refine_design_intent(
        user_prompt,
        previous_design_intent,
        correction,
    )
    repair_prompt = (
        f"{user_prompt}\n\nUser-requested revision: {correction}"
    )
    return evaluate_design_intent_with_feedback(
        repair_prompt,
        design_intent,
        max_repairs,
        telemetry=telemetry,
        initial_telemetry=initial_telemetry,
        additional_evaluator=lambda candidate: (
            refinement_direction_feedback(
                previous_design_intent,
                candidate,
                correction,
            )
        ),
    )


def refinement_direction_feedback(
    previous_design_intent: dict,
    candidate_design_intent: dict,
    correction: str,
) -> dict | None:
    """Reject placement revisions that move opposite the requested direction."""
    direction = requested_refinement_direction(correction)
    if direction is None:
        return None

    previous_features = {
        feature.get("id"): feature
        for feature in previous_design_intent.get("features", [])
        if feature.get("id")
    }
    changed_controls = []
    wrong_controls = []
    for candidate_feature in candidate_design_intent.get("features", []):
        feature_id = candidate_feature.get("id")
        previous_feature = previous_features.get(feature_id)
        if previous_feature is None:
            continue

        previous_control = placement_direction_control(previous_feature)
        candidate_control = placement_direction_control(candidate_feature)
        if (
            previous_control is None
            or candidate_control is None
            or previous_control[0] != candidate_control[0]
        ):
            continue

        control_name, previous_value, inward_sign = previous_control
        _, candidate_value, _ = candidate_control
        delta = candidate_value - previous_value
        if abs(delta) <= 1e-9:
            continue

        changed_controls.append(feature_id)
        expected_sign = inward_sign if direction == "inward" else -inward_sign
        if delta * expected_sign <= 0:
            wrong_controls.append({
                "feature": feature_id,
                "control": control_name,
                "previous": previous_value,
                "candidate": candidate_value,
            })

    if wrong_controls:
        return {
            "code": "wrong_directional_placement_change",
            "message": (
                f"The correction requested movement {direction}, but one or "
                "more placement controls moved in the opposite direction."
            ),
            "requested_direction": direction,
            "wrong_changes": wrong_controls,
            "suggestion": (
                "Apply the direction using the documented placement-control "
                "semantics and preserve unrelated feature values."
            ),
        }
    if not changed_controls:
        return {
            "code": "missing_directional_placement_change",
            "message": (
                f"The correction requested movement {direction}, but no "
                "recognized placement distance changed."
            ),
            "requested_direction": direction,
            "suggestion": (
                "Change near_corners.margin, offset_from_edge.offset, or "
                "circular_pattern.radius in the requested direction."
            ),
        }
    return None


def requested_refinement_direction(correction: str) -> str | None:
    """Return a clear inward/outward direction expressed by a correction."""
    normalized = " ".join(correction.lower().split())
    inward = bool(re.search(
        r"\b(?:inward|towards? (?:the )?(?:center|centre)|"
        r"farther from (?:the )?(?:edges?|corners?)|"
        r"increase (?:the )?(?:edge )?clearance)\b",
        normalized,
    ))
    outward = bool(re.search(
        r"\b(?:outward|away from (?:the )?(?:center|centre)|"
        r"closer to (?:the )?(?:edges?|corners?)|(?:decrease|reduce) "
        r"(?:the )?(?:edge )?clearance)\b",
        normalized,
    ))
    if inward == outward:
        return None
    return "inward" if inward else "outward"


def placement_direction_control(feature: dict) -> tuple[str, float, int] | None:
    """Return placement field, numeric value, and its inward delta sign."""
    placement = feature.get("placement")
    if not isinstance(placement, dict):
        return None
    placement_type = placement.get("type")
    control_by_type = {
        "near_corners": ("margin", 1),
        "offset_from_edge": ("offset", 1),
        "circular_pattern": ("radius", -1),
    }
    control = control_by_type.get(placement_type)
    if control is None:
        return None
    field, inward_sign = control
    value = placement.get(field)
    if not isinstance(value, (int, float)):
        return None
    return f"{placement_type}.{field}", float(value), inward_sign


def update_aggregate_telemetry(
    telemetry: dict,
    api_calls: list[dict],
) -> None:
    """Summarize every generation/repair API call without losing call details."""
    telemetry.clear()
    telemetry["calls"] = [dict(call) for call in api_calls]
    telemetry["logical_api_calls"] = len(api_calls)
    telemetry["api_attempts"] = sum(
        int(call.get("api_attempts", 1))
        for call in api_calls
    )
    for field in (
        "api_seconds",
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "total_tokens",
    ):
        values = [
            call[field]
            for call in api_calls
            if isinstance(call.get(field), (int, float))
        ]
        if values:
            telemetry[field] = sum(values)

    if api_calls:
        telemetry["requested_model"] = api_calls[0].get("requested_model")
        telemetry["response_models"] = sorted({
            call["response_model"]
            for call in api_calls
            if call.get("response_model")
        })


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
    candidate_evaluation = evaluate_model_candidate(model_data)
    quality_report = candidate_evaluation["quality_report"]
    operation_effects = candidate_evaluation["operation_effects"]
    diagnostics = (
        check_model_data(model_data)
        if not quality_report.get("passed", False)
        else {
            "passed": True,
            "failure_type": None,
            "reason": "Model data validated and built successfully.",
            "suggested_fixes": [],
        }
    )
    needs_repair = (
        not diagnostics.get("passed", False)
        or quality_report_needs_repair(quality_report)
        or not operation_effects.get("passed", False)
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
    for failure in operation_effects.get("failures", []):
        suggestion = f"Correct the feature so it changes the model: {failure}"
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
            or (
                "operation_effect_failed"
                if not operation_effects.get("passed", False)
                else "quality_gate_failed"
            )
        ),
        "reason": (
            "; ".join(operation_effects.get("failures", []))
            if not operation_effects.get("passed", False)
            else diagnostics.get(
                "reason",
                "The model failed diagnostics or quality-gate checks.",
            )
        ),
        "suggested_fixes": suggested_fixes,
        "repairable_quality_codes": repairable_quality_codes,
        "diagnostics": diagnostics,
        "quality_report": quality_report,
        "operation_effects": operation_effects,
        "evaluation_feedback": candidate_evaluation["feedback"],
    }


def prompt_to_model_data_with_repair(
    user_prompt: str,
    max_repairs: int | None = None,
) -> tuple[dict, list[dict]]:
    """Generate CAD JSON and repair failed built candidates up to a safe cap."""
    if max_repairs is None:
        max_repairs = max_repair_attempts("direct")
    model_data = prompt_to_model_data(user_prompt)
    repair_history = []

    for attempt_number in range(max_repairs + 1):
        failure_analysis = build_repair_failure_analysis(model_data)
        if failure_analysis["passed"] or attempt_number == max_repairs:
            return model_data, repair_history

        repaired_model_data = repair_model_data(
            user_prompt,
            model_data,
            failure_analysis,
        )
        repair_history.append(
            {
                "attempt": attempt_number + 1,
                "failure_analysis": failure_analysis,
                "failed_model_data": model_data,
                "repaired_model_data": repaired_model_data,
            }
        )
        if repaired_model_data == model_data:
            repair_history[-1]["stopped_reason"] = "unchanged_candidate"
            return model_data, repair_history
        model_data = repaired_model_data

    raise AssertionError("Unreachable direct repair loop state")


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
