# Prompt2ParametricCAD

A learning-focused project exploring how structured design instructions can
generate validated parametric CAD models with Python and CadQuery.

## Repository structure

```text
lessons/    Runnable snapshots of the project’s learning progression
src/        Evolving application code beginning with the next lesson
examples/   Clean example operation files
tests/      Automated application tests
generated/  Output location reserved for the evolving application
```

## Lessons

- Lesson 1: Parameterized plate generation from JSON
- Lesson 2: Ordered JSON operation interpreter
- Lesson 3: Patterned holes and operation-aware validation
- Lesson 4: Tagged workplanes plus circular and rectangular cuts/extrusions

## Current capabilities

- Rectangular base extrusions
- Circular and rectangular additive extrusions
- Circular and rectangular blind or through-cuts
- Patterned circular cuts
- Stable tagged workplane references
- Input, geometry, and connected-solid validation

The next phase will extract proven interpreter behavior into `src/` rather
than copying the full lesson script again.

Each historical lesson remains self-contained and writes its ignored CAD
exports beside its own script. New application code will write outputs to
`generated/`.
