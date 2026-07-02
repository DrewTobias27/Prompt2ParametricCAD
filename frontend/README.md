# Prompt2ParametricCAD Frontend

This is the React/Vite frontend for Prompt2ParametricCAD. It provides two ways
to build a part:

- Description mode: describe a CAD part in natural language and ask the backend
  to generate validated operation JSON.
- Manual builder mode: choose a base shape, add cuts/extrusions, preview drawing
  views, and run lightweight design-review checks before generating a STEP file.

The Python FastAPI backend still builds CAD models with CadQuery. During local
development, Vite proxies `/api/*` requests to `http://127.0.0.1:8000`.

## Local development

Use two terminals.

Terminal 1: run the Python backend from the repository root:

```powershell
.\scripts\run_web_app.ps1
```

Terminal 2: run the frontend:

```powershell
cd frontend
npm install
npm run dev
```

Then open:

```text
http://127.0.0.1:5173/
```

If requests fail, confirm the backend is running at `http://127.0.0.1:8000`.

## Manual builder notes

The manual builder is intended for users who want more control than a single
prompt gives them.

Recommended workflow:

1. Choose a base shape and exact dimensions.
2. Add one feature at a time.
3. Watch the drawing preview and design-review panel update.
4. Use feature-card badges to fix obvious placement or manufacturability issues.
5. Build the model once the preview and warnings look reasonable.

The starter presets are intentionally simple:

- Mounting plate
- Flange
- Boss block

They are useful smoke tests and examples for new users. Reference cases live in
`frontend/examples/manual-builder-cases.json`.

## Drawing preview

The drawing preview is a lightweight ANSI-style guide, not a replacement for a
real CAD drawing package. It currently supports:

- top/front/right third-angle layout
- base and feature dimensions with duplicate-dimension reduction
- center marks for circular features
- grouped repeated-feature callouts
- bolt-circle centerlines for circular hole patterns
- projected front/right views for simple cuts and extrusions

## Vercel deployment

Deploy the `frontend/` directory as the Vercel project root.

For a deployed backend, set:

```text
VITE_API_BASE_URL=https://your-backend-host.example.com
```

The CadQuery backend should be hosted separately on a Python-friendly platform.
