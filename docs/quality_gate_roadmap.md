# Quality Gate Roadmap

The quality gate is the long-term testing spine for Prompt2ParametricCAD. It
should make generated CAD output explainable, repairable, and measurable across
the full prompt-to-model pipeline.

## Current layers

1. Schema checks
   - Validate operation JSON against the Prompt2ParametricCAD schema.
   - Catch missing fields, invalid operation shapes, and invalid primitive data.

2. Structural checks
   - Check operation order, feature IDs, target existence, target kind, positions,
     revolve axes, and required dimensions.

3. Build checks
   - Verify CadQuery can build the operation sequence.

4. Export checks
   - Verify STEP output exists and is non-empty.

5. Repair-loop feedback
   - Feed structured quality issues and build diagnostics back into bounded API
     repair attempts.
   - Surface repair history in the frontend so generation failures are visible.

6. Repair/eval logging
   - Save repaired or failed prompt generations to local JSON logs under
     `generated/repair_logs/`.
   - Preserve the original prompt, failed model data, diagnostics, quality
     report, repaired model data, and final result for future eval/training use.

## Permanent improvement targets

1. Progressive build diagnostics
   - Identify the first operation that fails during build.
   - Attach operation number, operation id, failure message, and suggested fix.

2. Geometry summary and geometry validation
   - Record solid count, validity, bounding box, volume, face count, and edge
     count after build.
   - Flag disconnected solids, invalid geometry, unexpected zero volume, and
     suspicious bounding boxes.

3. Feature graph reference validation
   - Replace inferred reference strings with actual references produced by the
     backend `FeatureGraph` and `FeatureRegistry`.
   - Use true reference kind metadata instead of string heuristics.

4. Prompt/design-intent checks
   - Compare generated model data against prompt-derived design intent.
   - Check relationships like centered, near corners, circular pattern, symmetric,
     through hole, side face, boss on base, and feature count.

5. Repair prompt generation
   - Convert quality issues into concise repair instructions for the API.
   - Use the same report format for UI display, eval reports, and repair loops.

6. Partial scoring
   - Move beyond pass/fail to staged scores for generated output quality.
   - Preserve partial success when base geometry is correct but relationships or
     secondary features are imperfect.

7. Issue grouping and severity policy
   - Reduce noisy duplicate errors.
   - Group schema/structure/build symptoms by operation.
   - Standardize which findings are errors, warnings, or info.

8. Manufacturing/design-review checks
   - Add DFM-style constraints after geometry checks are stronger.
   - Check edge distance, hole spacing, wall thickness, slot proportions,
     over-thin material, and risky chamfers/fillets.

## Near-term sequence

1. Integrate quality reports into eval output summaries.
2. Build a command to promote selected repair logs into eval fixtures.
3. Use feature graph references for target validation instead of lightweight
   target-kind inference.
4. Add prompt/design-intent checks for relationships and feature counts.
5. Add partial scoring for generated output quality.
