# Project map

Prompt2ParametricCAD has grown into a few related systems. Use this map when
you are deciding where new work belongs.

## Core source

- `src/prompt2cad/interpreter.py` builds CadQuery geometry from executable CAD
  JSON.
- `src/prompt2cad/schema.py` defines the executable CAD JSON schema.
- `src/prompt2cad/prompting.py` calls the OpenAI API and contains prompting
  instructions.
- `src/prompt2cad/design_intent.py` lowers high-level design intent into
  executable CAD JSON.
- `src/prompt2cad/web_app.py` exposes the FastAPI backend.
- `frontend/` contains the React/Vite web UI.

## Geometry intelligence

- `src/prompt2cad/feature_registry.py` and `feature_graph.py` track named
  features, references, faces, edges, and parent/child build order.
- `src/prompt2cad/sketch_model.py` represents sketch-level geometry for future
  editable feature-tree and SolidWorks export work.
- `src/prompt2cad/feature_tree_export.py` exports debug feature-tree data.

## Testing and evaluation

- `tests/` contains normal automated tests.
- `evals/cases/` contains exact geometry eval cases with known expected
  dimensions.
- `evals/intent_cases/` contains expected design-intent eval fixtures.
- `evals/intent_gap_tests.json` contains broader exploratory prompt cases with
  concept-level expectations.
- `src/prompt2cad/evaluator.py` checks exact geometry fixture expectations.
- `src/prompt2cad/intent_evaluator.py` checks high-level design intent.
- `src/prompt2cad/concept_evaluator.py` checks whether generated CAD contains
  important prompt-level concepts.
- `src/prompt2cad/tiny_api_compare.py` compares direct JSON generation against
  design-intent generation.

## Examples and training

- `examples/` contains hand-written executable CAD JSON examples.
- `training/intent_examples/` contains design-intent examples intended for
  future dataset/fine-tuning work.
- `data/external/` is for downloaded external datasets and should stay out of
  git.

## Generated or disposable files

These folders are useful locally but should generally not be treated as source:

- `generated/`
- `frontend/dist/`
- `frontend/node_modules/`
- `.pytest_cache/`
- `.pytest-tmp/`
- `__pycache__/`

## Common commands

Run focused backend tests:

```powershell
$env:PYTHONPATH = "src"
& "C:\Users\Drew Tobias\Documents\Codex\2026-06-19\let\work\cadquery-env\Scripts\python.exe" -m pytest tests\test_design_intent.py tests\test_concept_evaluator.py tests\test_tiny_api_compare.py -q
```

Run the exploratory API comparison:

```powershell
$env:PYTHONPATH = "src"
& "C:\Users\Drew Tobias\Documents\Codex\2026-06-19\let\work\cadquery-env\Scripts\python.exe" -m prompt2cad.tiny_api_compare --prompt-file evals\intent_gap_tests.json
```

Run only the design-intent path:

```powershell
$env:PYTHONPATH = "src"
& "C:\Users\Drew Tobias\Documents\Codex\2026-06-19\let\work\cadquery-env\Scripts\python.exe" -m prompt2cad.tiny_api_compare --prompt-file evals\intent_gap_tests.json --mode intent
```

Re-score an existing API report without making new API calls:

```powershell
$env:PYTHONPATH = "src"
& "C:\Users\Drew Tobias\Documents\Codex\2026-06-19\let\work\cadquery-env\Scripts\python.exe" -m prompt2cad.tiny_api_compare --rescore-report generated\tiny_api_compare\report.json --prompt-file evals\intent_gap_tests.json --output generated\tiny_api_compare\rescored_report.json
```

Start the backend web app:

```powershell
$env:PYTHONPATH = "src"
& "C:\Users\Drew Tobias\Documents\Codex\2026-06-19\let\work\cadquery-env\Scripts\python.exe" -m uvicorn prompt2cad.web_app:app --host 127.0.0.1 --port 8000
```
