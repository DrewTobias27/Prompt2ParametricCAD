# Prompt2ParametricCAD

Prompt2ParametricCAD is a prototype system for generating editable-style
parametric CAD models from structured operations and natural-language design
prompts.

The project converts a CAD request into a validated JSON feature sequence, then
interprets that sequence with [CadQuery](https://cadquery.readthedocs.io/) to
build and export a STEP model. The long-term goal is to move from simple STEP
generation toward a feature-aware representation that can support better editing,
debugging, and eventual export into CAD systems with recognizable feature trees.

## What it does

- Converts natural-language prompts into CAD operation JSON with OpenAI
  Structured Outputs
- Provides a manual web builder for creating parts without writing JSON by hand
- Builds CadQuery models from ordered parametric operations
- Exports generated models as STEP files
- Supports geometry validation before export
- Tracks a feature graph with build order, parent/child relationships, sketches,
  face references, and aliases
- Includes regression evals for both generated operation JSON and built geometry

## Current CAD capabilities

Supported base features:

- Rectangular extrusions
- Circular extrusions
- Polygon extrusions
- Polyline and line/arc sketch extrusions
- Full and partial revolved solids

Supported added features:

- Additive extrusions
- Cutting extrusions
- Additive revolves
- Cutting revolves
- Repeated feature positions
- Mirror-style and circular-pattern feature placement in the web builder

Supported sketch/profile types:

- Rectangle
- Circle
- Polygon
- Polyline
- Line/arc sketch profiles

Supported references:

- Canonical feature references such as `base.face.f001`
- Readable aliases such as `base.top`, `base.front`, and `feature_1.right`
- Parent/child feature tracking for downstream feature-tree work

## Repository structure

```text
src/prompt2cad/   Core package: schema, interpreter, prompting, web app, evals
frontend/         React/Vite frontend scaffold for the Vercel-ready UI
examples/         Example CAD operation JSON files
evals/cases/      Evaluation definitions and expected constraints
evals/fixtures/   Hand-authored reference models for deterministic evals
prompts/          Prompt examples for API testing
tests/            Automated tests
scripts/          Local helper scripts
generated/        Ignored output folder for generated JSON, STEP, and debug files
docs/             Design notes and architecture review
lessons/          Historical development snapshots
```

For a deeper system overview, see `docs/architecture.md`.
For fresh setup instructions, see `docs/setup.md`.
For a portfolio/interview walkthrough, see `docs/demo_script.md`.

## Running the web app

Install the project dependencies into your Python environment:

```powershell
python -m pip install -r requirements.txt
```

To verify the local environment:

```powershell
.\scripts\check_setup.ps1
```

From the repository root, start the local server:

```powershell
.\scripts\run_web_app.ps1
```

Then open:

```text
http://127.0.0.1:8000/
```

## React frontend migration

The repository also includes a new React/Vite frontend in `frontend/`. This is
the starting point for the Vercel-ready UI while the existing FastAPI-served web
app remains available.

Start the Python backend first:

```powershell
.\scripts\run_web_app.ps1
```

Then, in a second terminal:

```powershell
cd frontend
pnpm install
pnpm dev
```

Open:

```text
http://127.0.0.1:5173/
```

For deployment notes, see `docs/frontend_migration.md`.

The web app has two main workflows:

1. Describe a part in natural language and generate CAD through the OpenAI API.
2. Use the manual builder to choose a base shape, dimensions, features, cuts,
   extrusions, and patterns.

The API workflow requires an `OPENAI_API_KEY` environment variable in the
terminal running the server. The manual-builder workflow can generate structured
model data without relying as heavily on natural-language prompting.

## Command-line usage

Generate a STEP file from a saved operation JSON file:

```powershell
$env:PYTHONPATH = "src"
python -m prompt2cad.cli examples/api_rectangular_plate.json generated/api_rectangular_plate.step
```

Export a debug feature tree from a saved operation JSON file:

```powershell
$env:PYTHONPATH = "src"
python -m prompt2cad.feature_tree_export examples/api_rectangular_plate.json --output generated/api_rectangular_plate_feature_tree.json
```

Generate eval models from prompts:

```powershell
$env:PYTHONPATH = "src"
python -m prompt2cad.eval_generator --overwrite
```

Run evals against generated models:

```powershell
$env:PYTHONPATH = "src"
python -m prompt2cad.eval_runner --models-dir generated\evals --cases-dir evals\cases
```

Run a single eval case:

```powershell
$env:PYTHONPATH = "src"
python -m prompt2cad.eval_runner --models-dir generated\evals --cases-dir evals\cases --case rigorous_plate_holes_boss
```

Some eval cases can use tracked fixture models from `evals/fixtures/`, so they
can run deterministically without making API calls.

Intent eval cases live in `evals/intent_cases/`. They check whether generated
design intent chose the right CAD concepts, such as `near_corners`,
`circular_pattern`, `rectangular_pattern`, `offset_from_edge`, and `slot`,
before the intent is lowered into operation JSON.

Export prompt-to-design-intent training data:

```powershell
$env:PYTHONPATH = "src"
python -m prompt2cad.training_data --format generic --output generated\training\intent_training.jsonl
```

Export chat-style supervised fine-tuning records:

```powershell
$env:PYTHONPATH = "src"
python -m prompt2cad.training_data --format openai_messages --output generated\training\intent_openai_messages.jsonl
```

Training examples live in `training/intent_examples/`. Each example stores a
natural-language prompt and the expected design-intent JSON. The exporter lowers
each intent example into CAD model data and checks that it validates and builds
before writing it to JSONL.

## Testing

Run the automated test suite:

```powershell
$env:PYTHONPATH = "src"
python -m pytest
```

The test suite covers:

- JSON schema validation
- CAD operation interpretation
- Sketch and arc representation
- Feature graph and reference naming
- Feature-tree debug export
- Web/eval helper behavior
- Geometry-focused evaluator checks

Recent evaluator improvements check more than operation presence. Evals can now
assert connected solid count, solid validity, bounding-box dimensions, approximate
volume, repeated feature counts, required graph references, aliases, feature
parents, and sketch profiles.

## Dependencies

The current prototype uses:

- Python
- CadQuery
- FastAPI
- Uvicorn
- OpenAI Python SDK
- pytest

Pinned package versions are listed in `requirements.txt`.

## Roadmap

Near-term priorities:

- Improve feature placement on side faces, curved faces, and corner-adjacent
  geometry
- Make manual-builder feature targeting clearer and more reliable
- Expand deterministic eval fixtures for difficult geometry cases
- Improve front-end polish and generated-part previews

Longer-term priorities:

- Strengthen the feature graph into a more complete editable feature tree
- Preserve sketch entities, references, dimensions, and parent/child dependencies
  in a CAD-system-friendly format
- Add more robust validation and repair suggestions for invalid generated parts
- Explore export paths beyond neutral STEP files, including workflows that better
  preserve parametric intent
