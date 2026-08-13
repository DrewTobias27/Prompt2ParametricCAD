# Release capability and composition audit

Prompt2ParametricCAD supports a finite CAD operation grammar that can produce
an unlimited number of feature sequences. It is therefore not possible to
enumerate every possible part. Release confidence comes from testing every
declared operation and profile family, all pairwise interactions, and the
multi-feature chains most likely to lose references after an edit.

## Verified release matrix

The generated audit currently contains 292 deterministic cases.

| Category | Cases | What it proves |
| --- | ---: | --- |
| Base profiles | 15 | Five profile families as extrusions plus full and partial revolves |
| Top-face profile pairs | 50 | Every base profile with every additive or subtractive child profile |
| Nested boss/cut pairs | 25 | Every additive profile targeted by every cut profile |
| Planar face supports | 60 | Five profiles, add/cut, and top/bottom/front/back/left/right faces |
| Native patterns | 33 | Mirror, circular, and two-direction linear patterns for additions, cuts, and countersinks |
| Revolved features | 10 | Five profiles for additive and subtractive revolves |
| Edge treatments | 10 | Chamfer and fillet on every base profile family |
| Composition and repair chains | 89 | Nested additions, stacked through-cuts, features after cuts/fillets, child edge treatments, pattern-instance children, cardinal and angled-face patterns, and revolved end-face features |

Every case must pass these deterministic gates:

1. strict operation-schema validation;
2. one connected, valid CadQuery solid;
3. complete SolidWorks replay-plan lowering with no dropped operations;
4. transactional parameter mutation and CadQuery rebuild;
5. STEP export/re-import with matching body count, volume, and XYZ spans;
6. when native execution is enabled, SolidWorks creation, first save/reopen,
   native history/helper/geometry/reference verification, parameter mutation,
   rebuild, second save/reopen, and a second geometry comparison.

The focused ten-part native gate separately enforces that its edit scenarios
exercise both binding strategies, every binding unit, signed placement
controls, all three pattern families, circular count/angle, and both
linear-pattern count/spacing directions. Creation coverage alone cannot satisfy
the release gate.

The August 2026 native audit passed the original 286 STEP round trips and all
286 native SolidWorks cases after four generalized fixes found by the matrix:
local feature frames replaced ambiguous global face tags, native polygons were
aligned to the CadQuery phase, merged freeform bosses stopped publishing a
consumed interface face, and curved edge groups gained a cardinality-guarded
semantic fallback. The six subsequently added angled-planar pattern cases were
then verified in focused installed-SolidWorks runs. All six passed native
creation, CadQuery/SolidWorks geometry comparison, persistent-reference
resolution, parameter mutation, rebuild, save/reopen, and a second geometry
comparison. Together, those runs established a 292-case native baseline. The
subsequent polygon-diameter and Hole Wizard placement-control changes pass the
same deterministic plans and compile against the installed SolidWorks APIs;
their focused installed-application rerun remains part of the final public
release gate.

## Checked-in corpus parity

A separate 49-case regression traverses every operation model in
`examples/models`, every validated library model, every evaluation fixture,
and every reviewed design-intent training example through editable-document
construction and native replay planning. This protects the examples people
actually see and use, rather than relying only on generated combinations.

## Golden end-to-end release gate

A second, deliberately compact matrix starts from seven reviewed
prompt-to-design-intent examples instead of operation JSON. It covers corner
patterns, counterbores, wall-mounted holes, revolved collars and grooves,
partial-revolve flat faces, a multi-level cross-arm hub, and an open tray. Each
case must pass:

1. design-intent vocabulary, required-dimension, and alignment checks;
2. deterministic lowering to operation JSON and operation-effect evaluation;
3. CadQuery construction and STEP export/re-import geometry comparison;
4. a declared transactional parameter edit with unchanged build order; and
5. complete SolidWorks replay planning with a native binding for every edited
   parameter.

This matrix is deterministic and does not spend API calls. Live model
interpretation remains covered by the separate semantic API suite.

## Supported construction vocabulary

| Construction | Typical use | Valid composition |
| --- | --- | --- |
| Base extrusion | Plates, blocks, brackets, freeform outlines | First feature; supports planar child faces |
| Base revolve | Shafts, rings, partial cylinders, axisymmetric bodies | First feature; supports front/back end-face children |
| Added extrusion | Bosses, walls, ribs, tabs, posts, rims | May target a prior planar face and may own later children |
| Cut extrusion | Holes, pockets, slots, openings | Blind or through; a through-cut may cross aligned stacked material |
| Added/cut revolve | Collars, rings, grooves, radial details | Uses a datum sketch and axis; may follow a revolved base |
| Mirror pattern | Symmetric repeated features | Additions, cuts, and countersinks |
| Circular pattern | Bolt circles and radial repeats | Additions, cuts, and countersinks |
| Linear pattern | Rows and rectangular grids | One- or two-direction additions, cuts, and countersinks |
| Countersink | Tapered fastener seats | Native SolidWorks Hole Wizard feature; blind or through |
| Chamfer/fillet | Edge finishing | Semantic edge groups on base or additive features |

Profiles available to extrusions, cuts, and revolves are rectangle, circle,
regular polygon, closed polyline, and closed line/arc sketch. Pattern instances
receive stable instance references such as `posts.inst002.top`, allowing later
features to target one repeated body.

## Recommended build and repair order

For a complex part, the most dependable feature tree is:

1. create the largest stable base extrusion or revolve;
2. add primary walls, bosses, hubs, and ribs;
3. add child bosses or cuts on those features using their local face IDs;
4. create one stable seed and pattern it instead of drawing unrelated copies;
5. apply holes, pockets, and through-cuts from the nearest correct planar face;
6. apply chamfers and fillets to the feature whose edges they own.

Repairs should preserve that structure:

| Problem | Preferred repair |
| --- | --- |
| Wrong size | Edit the named sketch or feature dimension and rebuild |
| Wrong location | Edit X/Y placement, pattern radius/spacing, or the owning relationship |
| Missing repeated child | Target the correct stable pattern-instance face |
| Cut stops too early | Change blind depth or use one through-cut along the intended direction |
| Dangling child reference | Retarget it to an existing earlier planar face; do not invent a face alias |
| Edge treatment fails after topology changes | Keep it adjacent to its owning feature or reselect the semantic edge group |
| Edit creates disconnected/invalid geometry | Reject the revision and retain the previous validated document |
| Prompt result is semantically wrong | Use the correction workflow, which revises saved design intent and reruns the same validators |

Upstream edits can move every downstream support frame. The release tests
therefore mutate both upstream and downstream dimensions rather than checking
only whether an initial file can be saved.

## Native editability boundary

SolidWorks output contains ordered native sketches, boss/cut/revolve features,
patterns, Hole Wizard countersinks, chamfers, fillets, persistent semantic face
references, and explicitly named pattern/support helpers. Standard widths,
heights, diameters, depths, distances, revolve
angles, pattern controls, and non-centered rectangle/circle placements have
named automated mutation bindings. Centered placement is held by a coincident
relation rather than a zero-valued driving dimension.

Native geometry parity requires more than a successful rebuild. The verifier
compares body count, volume, surface area, every absolute bounding-box limit,
and center of mass against CadQuery. This catches equal-size geometry built in
the wrong location and materially different shapes that happen to share a
volume or envelope.

Polyline vertices plus explicit-sketch start, end, and arc-through coordinates
are exposed through stable native dimensions when nonzero. Zero coordinates use
native horizontal/vertical relations. Three-point arc centers and radii are
derived from those source points so the sketch is not over-constrained. The
audit reports named mutation bindings, relation-controlled zero coordinates,
derived reference geometry, side-limited coordinate bindings, and genuinely
unsupported parameters separately instead of treating every missing native
dimension as a feature gap. Raw revolve-axis endpoints are retained by the
native construction line but classified as derived geometry because four
endpoint coordinates redundantly encode one axis; they are not counted as
automated controls or as lost geometry. Replay-plan version 11 also records a
canonical axis anchor, unit direction, normal, signed offset, and direction
angle. Equivalent endpoint pairs therefore describe the same downstream axis
without changing the proven native construction-line builder.
A nonzero coordinate may be edited on its current side of the origin; moving
it across or onto the origin requires regenerating the package so the sketch
relation and direction are rebuilt safely. Polygon side count remains fixed at
native sketch creation and is reported as unsupported topology.

Hole Wizard countersink position points use the same named X/Y placement
controls as other profiles. Patterned countersinks retain one editable seed;
the native mirror, circular, or linear pattern controls the remaining copies.

## Intentional limits

The current release does not claim support for:

- assemblies or intentionally disconnected multi-body parts;
- lofts, sweeps, shells, drafts, sheet-metal features, or true helical threads;
- sketching directly on arbitrary curved surfaces; use a supported planar face
  or an explicit datum/revolved operation instead;
- arbitrary freeform face names outside the published semantic reference set;
- guaranteed semantic correctness for every natural-language request.

STEP preserves final geometry but not native feature history. Native `SLDPRT`
creation requires the downloaded SolidWorks package and a compatible local
SolidWorks installation.

## Reproduce the gates

Run the quick representative regression tests:

```powershell
python -m pytest tests\test_capability_audit.py
```

Check every committed model and intent example against native replay planning:

```powershell
python -m pytest tests\test_native_corpus_parity.py
```

Run every generated case through STEP export/re-import:

```powershell
prompt2cad-capability-audit --export-steps `
  --output-root generated\capability-release
```

Run the compact golden prompt-to-native-plan matrix:

```powershell
prompt2cad-release-matrix `
  --output-root generated\release-matrix
```

On a configured SolidWorks workstation, continue those same seven golden cases
through native creation and their declared save/reopen edits:

```powershell
prompt2cad-release-matrix --execute-native `
  --verify-native-editability `
  --output-root generated\release-matrix-native
```

Run the full installed-SolidWorks mutation matrix:

```powershell
prompt2cad-capability-audit --execute-native `
  --verify-native-editability `
  --output-root generated\capability-native-release
```

Run the curated live semantic gate against the same public service used by
portfolio visitors:

```powershell
prompt2cad-live-eval `
  --prompt-file evals\release_semantic_cases.json `
  --api-base-url https://prompt2parametriccad.onrender.com `
  --require-all-pass `
  --output generated\release-semantic\deployed-report.json
```

The ten live cases cover exact corner offsets, compound counterbores, aligned
wall bores, nested feature ownership, revolved shaft details, nonrectangular
parent/child patterns, angularly offset radial patterns, hollow trays,
coplanar side tabs, and edge-treated slot plates. A warning fails this gate;
valid geometry alone is insufficient when dimensions or relationships differ
from the request.

The native command is intentionally long-running. Use `--category` or repeated
`--case` arguments for focused development runs.
