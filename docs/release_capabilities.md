# Release capability and composition audit

Prompt2ParametricCAD supports a finite CAD operation grammar that can produce
an unlimited number of feature sequences. It is therefore not possible to
enumerate every possible part. Release confidence comes from testing every
declared operation and profile family, all pairwise interactions, and the
multi-feature chains most likely to lose references after an edit.

## Verified release matrix

The generated audit currently contains 286 deterministic cases.

| Category | Cases | What it proves |
| --- | ---: | --- |
| Base profiles | 15 | Five profile families as extrusions plus full and partial revolves |
| Top-face profile pairs | 50 | Every base profile with every additive or subtractive child profile |
| Nested boss/cut pairs | 25 | Every additive profile targeted by every cut profile |
| Planar face supports | 60 | Five profiles, add/cut, and top/bottom/front/back/left/right faces |
| Native patterns | 33 | Mirror, circular, and two-direction linear patterns for additions, cuts, and countersinks |
| Revolved features | 10 | Five profiles for additive and subtractive revolves |
| Edge treatments | 10 | Chamfer and fillet on every base profile family |
| Composition and repair chains | 83 | Nested additions, stacked through-cuts, features after cuts/fillets, child edge treatments, pattern-instance children, side-face patterns, and revolved end-face features |

Every case must pass these deterministic gates:

1. strict operation-schema validation;
2. one connected, valid CadQuery solid;
3. complete SolidWorks replay-plan lowering with no dropped operations;
4. transactional parameter mutation and CadQuery rebuild;
5. STEP export/re-import with matching body count, volume, and XYZ spans;
6. when native execution is enabled, SolidWorks creation, geometry comparison,
   persistent-reference verification, save/reopen, parameter mutation, rebuild,
   second save/reopen, and a second geometry comparison.

The August 2026 release audit passed all 286 STEP round trips and all 286 native
SolidWorks cases after four generalized fixes found by the matrix: local
feature frames replaced ambiguous global face tags, native polygons were
aligned to the CadQuery phase, merged freeform bosses stopped publishing a
consumed interface face, and curved edge groups gained a cardinality-guarded
semantic fallback.

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
patterns, Hole Wizard countersinks, chamfers, fillets, and persistent semantic
references. Standard widths, heights, diameters, depths, distances, revolve
angles, pattern controls, and non-centered rectangle/circle placements have
named automated mutation bindings. Centered placement is held by a coincident
relation rather than a zero-valued driving dimension.

Polygon and freeform sketches are still native and can be edited manually in
SolidWorks, but every vertex coordinate and polygon topology value is not yet
exposed as a named automated mutation binding. The audit reports this coverage
separately so native construction is not confused with complete parameter API
coverage.

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

Run every generated case through STEP export/re-import:

```powershell
prompt2cad-capability-audit --export-steps `
  --output-root generated\capability-release
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
