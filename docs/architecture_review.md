# Architecture review: feature-tree direction

This project is moving from "prompt to a STEP file" toward "prompt/manual input
to editable CAD features." That shift changes the most important design
question:

> Can the system preserve enough feature, sketch, reference, and build-order
> information to rebuild or export the part as editable CAD later?

## What is strong now

- The operation list has been lifted into a `FeatureGraph`.
- Each `FeatureNode` stores operation type, operation number, parent target,
  child relationships, created references, and a normalized sketch.
- Sketches now use structural ids such as `p001`, `l001`, `a001`, and `c001`,
  with semantic names stored as aliases instead of primary ids.
- Feature references now use canonical names such as `base.face.f001`, with
  compatibility aliases such as `base.top`.
- Multi-instance rectangular extrusions can create instance references such as
  `feature_1.inst001.face.f001`.
- The registry has scaffolding for non-planar surfaces, edges, vertices,
  axes, points, and sketch entities.
- The feature-tree debug export exposes the internal model in JSON, which gives
  us a way to inspect the future SolidWorks export payload before attempting a
  real SLDPRT workflow.

## Generalization risks

### Semantic face names still exist at the API/UI boundary

`base.top`, `base.front`, and similar names are still useful for users and the
language model, but they should remain aliases. The internal system should keep
using canonical ids like `base.face.f001`.

Future work:

- Teach the web app to display semantic aliases while storing canonical ids.
- Let the API return aliases for readability but prefer canonical references
  in debug/export data.

### Rectangular prism face extraction is much stronger than other profiles

Rectangles are easy because six faces are predictable. Circles, polygons,
polylines, sketches, revolved features, and curved surfaces need richer
reference extraction.

Future work:

- Register polygon side faces as `feature.face.f###`.
- Register extruded circle curved surfaces as `feature.surface.s001`.
- Register revolved surfaces generically as surfaces with axis/radius/profile
  metadata.
- Register sketch-derived extrusion faces by following sketch entity ids.

### Multi-instance references are now named, but patterns are not first-class

The system can name `feature_1.inst001` and `feature_1.inst002`, but it does
not yet represent "this is a linear/mirror/circular pattern feature."

Future work:

- Add `PatternNode` or pattern metadata to `FeatureNode`.
- Track source instance, transform, and instance count.
- Let a future SolidWorks export choose between exporting separate features or
  a real pattern feature.

### Stale references are not fully solved

The graph can reject targets whose parent feature does not exist, but it cannot
yet prove that a later cut did not remove a face that was registered earlier.

Future work:

- Add post-operation reference validation by checking whether a reference frame
  still intersects the current solid.
- Mark references as valid, stale, or unknown.
- Avoid silently using stale references during edit/rebuild/export.

## Performance and complexity review

### Potential inefficiencies

- `build_model_with_graph` builds geometry and graph together. This is simple,
  but future editing may need graph-only operations that do not run CadQuery.
- Reference registration currently stores metadata copies and debug-export
  dictionaries. That is fine now, but debug export should stay optional.
- The interpreter still has several retries/fallbacks for virtual side targets.
  Those are useful while the system is young, but should shrink as the graph
  becomes more capable.

### Complexity risks

- `interpreter.py` is still the busiest file. It handles validation, geometry
  construction, fallback targeting, feature reference registration, cuts,
  extrudes, revolves, and repair behavior.
- The web app still thinks mostly in semantic targets. That is good for users
  but should be isolated from internal reference ids.
- Schema, prompt instructions, interpreter, feature graph, and web UI all need
  to evolve together. If one lags, the system may build geometry that the graph
  cannot represent cleanly.

Future work:

- Split interpreter geometry tools by operation type once the feature graph
  stabilizes.
- Add a graph-only parser path for validation/export without building STEP.
- Keep debug export as the contract between graph and future SolidWorks export.

## SolidWorks export readiness

A real editable SolidWorks export will need:

- build order
- feature ids and names
- target references
- sketch planes or reference frames
- sketch entities
- dimensions
- constraints
- operation type and parameters
- parent/child dependencies
- rebuild validation

The current `FeatureGraph` + `SketchDefinition` + `FeatureRegistry` combination
now covers the first usable version of that structure, but constraints and
true topology persistence are still missing.

## Recommended next steps

1. Register sketch entities as feature references:
   - `base.sketch.p001`
   - `base.sketch.l001`
   - `feature_1.sketch.c001`
2. Add graph-only validation/export that does not require CadQuery.
3. Register references for polygon, circle, and sketch-based extrusions.
4. Add pattern metadata for mirror/circular/repeated features.
5. Prototype a SolidWorks macro/export adapter from the debug feature tree,
   before trying direct `.sldprt` writing.
