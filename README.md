# Prompt2ParametricCAD

A learning-focused project exploring how structured design instructions can
generate validated parametric CAD models with Python and CadQuery.

## Repository structure

```text
lessons/    Runnable snapshots of the project's learning progression
src/        Evolving application code
examples/   Clean example operation files
prompts/    Natural-language prompt examples
tests/      Automated application tests
generated/  Output location reserved for generated CAD files
```

## Lessons

- Lesson 1: Parameterized plate generation from JSON
- Lesson 2: Ordered JSON operation interpreter
- Lesson 3: Patterned holes and operation-aware validation
- Lesson 4: Tagged workplanes plus circular and rectangular cuts/extrusions

## Current capabilities

- Builds CadQuery models from ordered JSON operations
- Supports base extrusions and revolved base solids
- Supports additive extrusions and cuts on tagged faces
- Supports rectangular, circular, polygon, polyline, and line/arc sketch profiles
- Supports repeated feature positions for simple patterns
- Uses named face tags such as `base.top` and `base.front` for later operations
- Validates that generated parts are single connected valid solids
- Exports generated models as STEP files
- Includes an early OpenAI Structured Outputs prototype for converting natural language into CAD JSON

## Example CLI usage

Generate a STEP file from a saved JSON model:

```powershell
python -m prompt2cad.cli examples/api_rectangular_plate.json generated/api_rectangular_plate.step
```

The current OpenAI prototype can convert a simple natural-language prompt into
a rectangular base extrusion JSON structure. API-generated outputs can be saved
as examples and tested locally without making repeated API calls.

Each historical lesson remains self-contained and writes its ignored CAD
exports beside its own script. New application code writes outputs to
`generated/`.
