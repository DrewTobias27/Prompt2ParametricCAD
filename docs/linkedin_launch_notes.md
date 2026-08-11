# LinkedIn launch notes

These are requirements for a later Prompt2ParametricCAD post. Do not draft or
publish the post until Drew asks.

## What the post should communicate

- Present the project cleanly and lead with what a visitor can do.
- Emphasize the live website and invite people to try it and share feedback.
- Show the strongest verified examples without implying that every CAD request
  is supported.
- Explain that the website downloads STEP files directly.
- Explain that users with Windows and SolidWorks can download the replay
  package and build an editable native `SLDPRT` with named sketches,
  dimensions, patterns, and ordered features.

## Release requirement

Do not link the SolidWorks claim publicly until the release gate in
`docs/hosting.md` passes against a package downloaded from the deployed website.

## Verified release evidence

Verified against the public deployment on August 10, 2026:

- A multi-feature mounting plate generated successfully from a natural-language
  prompt with four patterned holes, a raised boss, and a concentric through hole.
- A follow-up correction changed the four-hole edge margin from 10 mm to 14 mm
  and the boss height from 10 mm to 13 mm while preserving a valid single solid.
- The public STEP endpoint returned a non-empty model file.
- A SolidWorks replay package downloaded from the public site created a native
  `SLDPRT` with one solid, two native features, and twelve editable dimensions.
- The Python regression suite passed with 439 tests and zero skipped tests,
  including an installed-SolidWorks package build.
- The native SolidWorks verification suite passed all eight supported cases,
  including freeform edge selection and partial revolves.

## Recommended visuals

Use a small set that communicates different capabilities instead of many similar
parts:

1. A clean live-app capture showing the description, generated feature tree,
   download actions, and refinement box.
2. `cross-arm-hub-plate.png` for complex sketch geometry and repeated features.
3. `two-wall-u-bracket.png` for parent-child features and work on multiple faces.
4. `turned-shaft.png` for revolved geometry.
5. A real SolidWorks screenshot showing the generated native feature tree and an
   editable dimension. Do not substitute a STEP import screenshot for this proof.

The prepared portfolio renders are stored in the portfolio repository under
`public/assets/prompt2cad/renders/`.

## Final human checks

- Open the live site on a phone and confirm that the builder, output, and download
  controls remain readable without horizontal scrolling.
- Capture a clean desktop image or short recording without browser chrome,
  scrollbars, API keys, local paths, or unrelated tabs.
- Run one known-good prompt and one correction immediately before publishing.
- Download both the STEP file and SolidWorks package from the public site.
- Run the downloaded SolidWorks package on Windows with SolidWorks and capture
  the resulting native feature tree.
- Preview the finished LinkedIn post and portfolio link while signed out or in a
  private browser window.
