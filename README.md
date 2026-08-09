# Prompt2ParametricCAD

Prompt2ParametricCAD turns natural-language design intent or guided user input
into validated, parametric CAD features. It uses an intermediate JSON
representation to separate language understanding from geometry construction,
then builds real solids with CadQuery and exports STEP files.

The project is designed around inspectable design intent—not one-off mesh
generation. Every model can be validated, evaluated, rebuilt in feature order,
and represented as a dependency graph for future editable CAD export.

## Highlights

- Natural-language generation through OpenAI Structured Outputs
- Guided manual builder for deterministic part construction
- Design-intent layer for dimensions, placement, patterns, and feature
  relationships
- Strict JSON schema and progressive geometry validation
- CadQuery solid construction and STEP export
- Feature graph with stable IDs, parents, children, sketches, faces, and edges
- Automatic repair fallback with structured diagnostics
- Focused result refinement that preserves prior design intent and validates each revision
- Deterministic fixtures and API benchmarks for semantic and geometric quality
- React drawing preview and live design-review warnings

## Portfolio showcase

A concise, reproducible set of eleven verified mechanical parts demonstrates the
current vocabulary across patterned plates, flanges, full revolves, grooves,
edge treatments, and non-rectangular outlines. See the
[portfolio showcase](docs/showcase.md) and run `python -m prompt2cad.showcase`
to regenerate its STEP files locally.

## Supported CAD vocabulary

| Area | Current support |
| --- | --- |
| Base profiles | Rectangle, circle, polygon, polyline, line/arc sketch |
| Base operations | Extrude, full revolve, partial revolve |
| Added features | Extrude, cut, revolve, revolved cut |
| Feature placement | Face targets, offsets, symmetry, linear and circular patterns |
| Hole features | Through, blind, counterbore, countersink |
| Detail features | Fillet, chamfer, rounded slots and pockets |
| References | Canonical face/edge IDs plus readable aliases such as `base.top` |
| Outputs | STEP geometry, operation JSON, feature-tree debug JSON |

Complex CAD requests remain an active research problem. The system is strongest
on single connected mechanical parts built from sketches, extrusions, cuts,
revolves, patterns, and common detail features.

## How it works

```text
Natural-language prompt ──> design intent ──> operation JSON ──┐
                                                               ├─> validation
Guided manual builder ──────────────────────> operation JSON ──┘
                                                                    │
                                                                    v
                                            feature graph <── CadQuery build
                                                                    │
                                            quality checks <────────┤
                                                                    v
                                                               STEP export
```

The automatic path tries the relationship-aware design-intent pipeline first.
If that representation cannot express or lower a request, a bounded direct-JSON
compatibility path is available. Both paths produce the same validated operation
format before geometry is built.

After a successful intent-based result, the description builder can apply a
focused correction such as “move the holes inward” or “make the boss taller.”
The application revises the saved design intent, runs the same geometry checks,
rejects no-op responses that leave the CAD operations unchanged, exports a new
STEP revision only when valid, and leaves the prior revision available to
restore if the correction does not succeed.

## Quick start

Requirements:

- Python 3.11 or 3.12
- Node.js and pnpm
- An OpenAI API key for natural-language generation

The current setup and launch helpers are tested on Windows.

Install the backend and development dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Install the frontend:

```powershell
cd frontend
pnpm install
cd ..
```

Set the API key in the terminal that will run the backend:

```powershell
$env:OPENAI_API_KEY = "your-key"
```

Build the frontend and start the complete application:

```powershell
.\scripts\run_app.ps1
```

Open `http://127.0.0.1:8000/`. Use `-Network` to make the app available to
another device on the same private network:

```powershell
.\scripts\run_app.ps1 -Network
```

See [docs/setup.md](docs/setup.md) for development mode, environment overrides,
and troubleshooting.

## Command-line examples

Once installed in editable mode, build a STEP file from saved operation JSON:

```powershell
prompt2cad examples\models\api_rectangular_plate.json generated\plate.step
```

Export its feature-tree representation:

```powershell
prompt2cad-feature-tree examples\models\api_rectangular_plate.json `
  --output generated\plate-feature-tree.json
```

Run the automated tests:

```powershell
python -m pytest
```

Run deterministic and generated-model evaluations:

```powershell
prompt2cad-eval --models-dir generated\evals --cases-dir evals\cases
```

Generate training-ready design-intent records:

```powershell
prompt2cad-training-data --format openai_messages `
  --output generated\training\intent.jsonl
```

More evaluation workflows are documented in
[docs/evaluation.md](docs/evaluation.md).

## Repository layout

```text
src/prompt2cad/   Python package: intent, schema, interpreter, graph, API, evals
frontend/         React/Vite application and frontend QA scripts
examples/library/ Curated prompt/model examples used for retrieval
examples/models/  Standalone operation-JSON examples
examples/prompts/ Natural-language sample prompts
evals/            Evaluation cases and deterministic model fixtures
training/         Reviewed prompt-to-design-intent examples
tests/            Python unit and integration tests
scripts/          Setup and application launch helpers
docs/             Architecture, setup, evaluation, and demo documentation
generated/        Ignored local STEP files, reports, logs, and training exports
```

## Project status

This is a working prototype and portfolio project, not a replacement for a
production CAD system. STEP export preserves the final solid but does not
preserve a native SolidWorks feature tree. The internal feature graph and sketch
representation are scaffolding for that longer-term goal.

Current priorities are:

1. Broader design-intent vocabulary and more reliable spatial relationships.
2. Stable face and edge references after topology-changing operations.
3. Stronger semantic evaluation of whether geometry matches the prompt.
4. Native-CAD export experiments that retain sketches and feature history.

For implementation details and known constraints, see
[docs/architecture.md](docs/architecture.md).
