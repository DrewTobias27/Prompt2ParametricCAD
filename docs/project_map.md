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
  executable CAD JSON, including reusable base profiles such as rectangles,
  circles, polygons, D-shaped plates, cylinders, half-cylinders, and capsules.
- `src/prompt2cad/web_app.py` exposes the FastAPI backend.
- `frontend/` contains the React/Vite web UI.

## Geometry intelligence

- `src/prompt2cad/feature_registry.py` and `feature_graph.py` track named
  features, references, faces, edges, and parent/child build order.
- `src/prompt2cad/sketch_model.py` represents sketch-level geometry for future
  editable feature-tree and SolidWorks export work.
- `src/prompt2cad/feature_tree_export.py` exports debug feature-tree data.
- `src/prompt2cad/intent_coverage.py` checks whether design intent covers the
  major semantic concepts requested by the prompt, such as mounting plates,
  holes, slots, grooves, bosses, ribs, chamfers, and fillets.

## Testing and evaluation

- `tests/` contains normal automated tests.
- `evals/cases/` contains exact geometry eval cases with known expected
  dimensions.
- `evals/intent_cases/` contains expected design-intent eval fixtures.
- `evals/intent_gap_tests.json` contains broader exploratory prompt cases with
  concept-level expectations.
- `evals/intent_stress_cases.json` contains newer stretch prompt cases for
  patterns, side-face features, edge treatments, revolved features, and
  relationship-heavy parts.
- `evals/intent_stress_cases_2.json` contains a second batch of stretch cases
  for nested targets, compound holes, U-brackets, rings, ribs, and ambiguous
  engineering relationships.
- `src/prompt2cad/evaluator.py` checks exact geometry fixture expectations.
- `src/prompt2cad/intent_evaluator.py` checks high-level design intent.
- `src/prompt2cad/concept_evaluator.py` checks whether generated CAD contains
  important prompt-level concepts.
- `src/prompt2cad/tiny_api_compare.py` compares direct JSON generation against
  design-intent generation. The intent path now also reports semantic coverage
  warnings when the JSON builds but omits a requested concept.
- `docs/demo_checklist.md` contains the laptop-demo runbook, safe prompts, and
  saved-demo fallback plan.

## Examples and training

- `examples/` contains hand-written executable CAD JSON examples.
- `training/intent_examples/` contains design-intent examples intended for
  future dataset/fine-tuning work. New examples should include
  `required_concepts` and semantic `role` fields so they train both geometry
  and design relationships.
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

## Performance notes

- The web backend keeps a small in-memory cache for exact successful prompt and
  suggestion responses. This only avoids repeated identical work in the same
  server session; it does not change first-run model output.
- Web responses include timing metadata for API, build, export, quality, and
  total time. Use this before guessing where speed problems are coming from.
- API comparison reports include pass/warn/fail counts plus average, total, and
  slowest-case timings.
- Prefer safe speed wins: exact caching, targeted eval runs, and better timing
  visibility. Avoid faster prompt/model paths unless they pass the same quality
  and concept checks as the slower path.

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

Run the newer stress prompt cases:

```powershell
$env:PYTHONPATH = "src"
& "C:\Users\Drew Tobias\Documents\Codex\2026-06-19\let\work\cadquery-env\Scripts\python.exe" -m prompt2cad.tiny_api_compare --prompt-file evals\intent_stress_cases.json --mode intent --output generated\tiny_api_compare\stress_report.json
```

Run the second stress prompt suite:

```powershell
$env:PYTHONPATH = "src"
& "C:\Users\Drew Tobias\Documents\Codex\2026-06-19\let\work\cadquery-env\Scripts\python.exe" -m prompt2cad.tiny_api_compare --prompt-file evals\intent_stress_cases_2.json --mode intent --output generated\tiny_api_compare\stress_report_2.json
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

Start the server for a laptop demo:

```powershell
.\scripts\run_demo_server.ps1
```
