# Editable feature architecture

## Goal

Prompt2ParametricCAD should preserve more than the final STEP solid. A
successful model should also carry enough explicit design information to:

1. show a user named dimensions and feature controls;
2. change one or more values and rebuild the same ordered model;
3. preserve feature IDs, build order, support faces, and parent relationships;
4. replay the model into a native CAD system in a later exporter.

The first target is a reliable editable intermediate document. A native
SolidWorks `SLDPRT` writer is a later adapter, not a replacement for this
document.

## Top-down design

```mermaid
flowchart LR
    P["Prompt or guided builder"] --> I["Design intent"]
    I --> O["Validated operation JSON"]
    O --> D["Editable model document"]
    D --> C["CadQuery rebuild"]
    D --> S["Future SolidWorks replay adapter"]
    C --> Q["Geometry and semantic checks"]
    S --> N["Native sketches and features"]
```

The operation JSON remains the execution contract. The editable model document
adds the information a UI or native-CAD adapter needs without changing the
working interpreter:

- a versioned format and explicit units;
- stable feature IDs and build order;
- semantic parents plus the previous feature in model history;
- original and canonical support references;
- normalized sketch entities;
- named driving parameters with exact paths back to operation JSON;
- reference snapshots for later face/edge selection;
- explicit limitations when a feature is not fully parametric yet.

Parameter edits are transactional. They are applied to a copy of the source
operations, validated against the existing schema, and rebuilt through
CadQuery. The previous document remains unchanged if validation or geometry
construction fails.

## Fit with the current system

The existing architecture already provides most of the hard prerequisites:

| Existing layer | Reused for editable features |
| --- | --- |
| Operation JSON | Source of exact dimensions and feature controls |
| Feature graph | IDs, build order, parents, children, and operation snapshots |
| Sketch model | Named points, lines, arcs, circles, and sketch dimensions |
| Reference registry | Canonical faces, edges, axes, local frames, and aliases |
| JSON Schema | Rejects invalid parameter values before accepting an edit |
| CadQuery interpreter | Proves that an edited feature sequence still builds |

This makes an additive intermediate layer safer than replacing the interpreter
or attempting to infer a feature tree from a STEP file.

## Native SolidWorks strategy

A future Windows adapter should replay the editable document through the
SolidWorks automation API:

1. create a new part and establish document units;
2. create each sketch on its recorded plane or resolved support reference;
3. recreate named sketch entities, dimensions, and constraints;
4. create the corresponding extrude, cut, revolve, fillet, or chamfer;
5. resolve later targets from semantic selection recipes after each rebuild;
6. assign stable feature names and save the resulting `SLDPRT`.

The adapter should never use final B-rep edge numbers as its only source of
truth. It should prefer feature ownership, support aliases, local frames, and
geometric selection criteria, because topology can change when an earlier
dimension changes.

## Predicted failure modes and mitigations

| Risk | Design response |
| --- | --- |
| An edit creates invalid or disconnected geometry | Validate and rebuild a copy before returning a new document. |
| Feature IDs change after an insertion | Require explicit IDs for persistent editing and flag generated fallback IDs. |
| Face or edge IDs change after a rebuild | Store semantic aliases and local-frame snapshots; re-resolve references after every feature. |
| A feature depends on more than one earlier feature | Represent parents as a list even though the current graph usually supplies one. |
| Build order and semantic ownership are confused | Store `build_predecessor_id` separately from `parent_feature_ids`. |
| A pattern is flattened into several positions | Preserve every instance now and flag the operation for a later seed-plus-pattern representation. |
| Polyline or arc sketches have coordinates but no constraints | Expose their coordinates, but mark the sketch as coordinate-driven until constraints are added. |
| A failed edit partially mutates the saved model | Deep-copy source operations and return a new document only after a successful rebuild. |
| Native CAD and CadQuery disagree about a selection | Keep CadQuery as the regression oracle and add adapter-specific replay tests before claiming support. |

## Near-term scope

The achievable first milestone is:

- export a versioned editable document from any currently valid model;
- expose named sketch, placement, axis, and feature parameters;
- apply parameter changes and rebuild validated geometry;
- preserve IDs, relationships, and selection information across the rebuild;
- report which features still need constraints, explicit IDs, or true pattern
  nodes before native replay.

After this layer is proven, the next increment is a small editor API and UI for
changing dimensions. A narrow SolidWorks replay prototype should then start
with rectangle/circle sketches plus extrude and cut, before adding revolves,
patterns, and topology-sensitive edge treatments.
