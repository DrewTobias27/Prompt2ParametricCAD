# Demo guide

## One-sentence description

Prompt2ParametricCAD converts a natural-language or guided mechanical design
into validated parametric features, builds the solid with CadQuery, and exports
a STEP file or a local SolidWorks replay package while retaining a
machine-readable feature graph.

## Prepare

```powershell
.\scripts\check_setup.ps1
.\scripts\run_app.ps1
```

For another device on the same private network:

```powershell
.\scripts\run_app.ps1 -Network
```

Open `http://127.0.0.1:8000/` locally, or use the host computer's IPv4 address
from the second device.

## Recommended walkthrough

1. Describe a mechanical part and generate it.
2. Show the generated operation JSON and quality result.
3. Download and open the STEP file.
4. Show the separate SolidWorks-package download and explain that it creates an
   editable `SLDPRT` locally for users who have Windows and SolidWorks.
5. Switch to the manual builder.
6. Add a base, a feature, a pattern, and a cut while showing the drawing preview.
7. Explain that both workflows produce the same operation representation.

Reliable starting prompt:

```text
Create a 100 mm by 60 mm by 8 mm rectangular mounting plate with four 8 mm
circular through holes near the corners and a centered 24 mm diameter raised
boss, 10 mm tall, with a 10 mm concentric through hole.
```

## Technical points

- The model returns structured design intent, not Python code.
- Intent is lowered into strict operation JSON.
- The backend validates targets and dimensions before building.
- CadQuery creates a real boundary-representation solid and STEP export.
- Feature graph data preserves order, dependencies, sketches, faces, and edges.
- Tests distinguish valid geometry from geometry that matches the request.

## Honest limitations

- Ambiguous or highly complex prompts can still lose spatial relationships.
- STEP does not preserve a native SolidWorks feature tree. The downloadable
  SolidWorks package instead replays the supported sketch, extrude, cut,
  revolve, pattern, countersink, chamfer, fillet, placement, and named-face
  vocabulary through an installed copy of SolidWorks.
- Curved-surface targeting and topology-changing detail features remain active
  development areas.

## Recovery

If a prompt fails, use the structured failure reason, simplify the request, or
show the guided builder. The demo should exercise the live pipeline; it does not
use pre-generated STEP fallback files.
