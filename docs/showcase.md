# Portfolio showcase

This concise set demonstrates the kinds of single connected mechanical parts
Prompt2ParametricCAD can currently build. Each prompt is paired with
project-authored design intent, lowered to the shared CAD-operation format, and
verified through schema, build, geometry, operation-effect, and
intent-alignment checks before it is included here.

These are reproducible deterministic examples, not a claim that every new
natural-language request will generate perfectly on the first attempt.

## Five verified parts

### 1. Patterned mounting plate

**Shows:** prismatic extrusion, rectangular feature patterns, and through-cut
holes.

> Create a 100 mm by 70 mm rectangular plate that is 8 mm thick with a 2 by 3
> grid of 5 mm through holes centered on the top face.

### 2. Sealed circular flange

**Shows:** circular profiles, bolt-circle placement, concentric openings, and
a revolved O-ring groove.

> Create a circular flange with eight bolt holes and a shallow circular O-ring
> groove around the center opening.

### 3. Half-cylinder cradle

**Shows:** partial revolves, an attached mounting plate, mounting holes, and a
shallow groove on the cradle.

> Create a half-cylinder cradle sitting on a separate rectangular mounting
> plate with two circular through holes in the plate and a shallow groove along
> the curved cradle.

### 4. Turned shaft with collars and grooves

**Shows:** full revolves, revolved additions and cuts, and end chamfers.

> Create a cylindrical shaft with two narrow grooves near one end, a larger
> collar near the other end, and a chamfer on both shaft ends.

### 5. D-shaped mounting plate

**Shows:** a non-rectangular base outline, multiple explicit extrusions, and a
linear hole pattern.

> Create a D-shaped plate with a flat back edge and rounded front, two
> rectangular side tabs, and three circular through holes along the centerline.

## Reproduce the STEP files

Run the verified showcase exporter from the repository root:

```powershell
$env:PYTHONPATH = "src"
python -m prompt2cad.showcase
```

It writes one STEP file per part under `generated/showcase/`. The output folder
is ignored by Git so the demo always shows freshly built geometry rather than
stale committed artifacts. To run the same checks without exporting files:

```powershell
python -m prompt2cad.showcase --validate-only
```

The underlying prompt-to-intent records live in
[`training/intent_examples/`](../training/intent_examples/), and the tracked
showcase manifest is [`docs/showcase.json`](showcase.json).
