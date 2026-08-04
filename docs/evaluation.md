# Evaluation

Prompt2ParametricCAD tests three different questions:

1. Is the software implementation correct?
2. Does generated JSON build valid geometry?
3. Does the geometry actually express the requested design intent?

No single check answers all three.

## Test layers

| Layer | What it catches |
| --- | --- |
| Unit tests | Schema, lowering, references, patterns, evaluator behavior |
| Fixture evals | Interpreter and geometry regressions without API variability |
| Intent evals | Missing concepts, relationships, dimensions, and feature roles |
| Operation effects | Features that build but do not materially add or remove geometry |
| API benchmarks | Model accuracy, latency, tokens, warnings, and build failures |

## Unit and integration tests

```powershell
python -m pytest
```

## Fixture and generated-model evals

Generate model files when needed:

```powershell
$env:PYTHONPATH = "src"
python -m prompt2cad.eval_generator --overwrite
```

Evaluate all cases:

```powershell
prompt2cad-eval --models-dir generated\evals --cases-dir evals\cases
```

Evaluate one case:

```powershell
prompt2cad-eval --models-dir generated\evals --cases-dir evals\cases `
  --case rigorous_plate_holes_boss
```

Tracked fixtures in `evals/fixtures/` make backend regressions deterministic.
Intent cases in `evals/intent_cases/` verify semantic concepts before and after
lowering.

## API stress benchmarks

The focused runner records API latency, token usage, local stage timings,
quality reports, intent coverage, concept assertions, operation effects, and
feedback-loop recovery. By default it runs the production geometry-feedback
path and stores the exact first-pass candidate inside the same result for paired
scoring. Direct JSON generation is an explicit fallback diagnostic, not the
default benchmark.

```powershell
$env:PYTHONPATH = "src"
python -m prompt2cad.tiny_api_compare --help
python -m prompt2cad.model_matrix_eval --help
```

Use tracked case files and write reports under `generated/tiny_api_compare/`.
Generated reports are intentionally ignored by Git; the cases and evaluator
logic are the durable regression assets.

## Repair logs

Failed or repaired generations are written under `generated/repair_logs/`.
Promote a useful real-world failure into a tracked fixture:

```powershell
python -m prompt2cad.repair_log_tools generated\repair_logs\example.json `
  --name repaired_example
```

Review promoted data before committing it. A good eval case should describe the
required concepts and relationships, not merely copy one model output.

## Interpreting results

- `PASS`: all configured structural, geometric, and semantic checks passed.
- `WARN`: valid geometry was built, but one or more requested concepts or
  feature effects were not proven.
- `FAIL`: the pipeline could not produce valid connected geometry, or a required
  assertion failed.

A valid solid is not automatically the requested part. Semantic checks and
operation-effect checks should remain enabled when comparing generation models.
