# Frontend migration plan

The current FastAPI app serves a plain HTML/CSS/JavaScript interface from
`src/prompt2cad/web/`. That interface still works and should remain available
while the project moves toward a portfolio-ready frontend.

The new frontend starts in `frontend/` as a React + Vite app.

## Why split the frontend

- The manual builder has grown into a real product UI, not a simple page.
- React components make feature cards, drawing preview panels, and design-review
  warnings easier to maintain.
- Vite gives a clean local development server.
- Vercel can deploy the frontend cleanly once the backend is hosted elsewhere.

## Development architecture

```text
React/Vite frontend  ->  FastAPI backend  ->  CadQuery model builder
localhost:5173       ->  localhost:8000   ->  STEP files
```

During local development, Vite proxies `/api/*` requests to the FastAPI server.

## Backend remains Python

The CAD generation backend should stay Python-based because CadQuery and the
geometry validation pipeline run there. Vercel is a good frontend host, but it is
not the best place to run CadQuery-heavy geometry generation.

Likely backend hosting options later:

- Render
- Railway
- Fly.io
- a small VPS

## Migration steps

1. Scaffold React/Vite frontend.
2. Connect prompt generation and manual model build endpoints.
3. Port the full manual builder state from the static web app.
4. Port the drawing preview into React components.
5. Port design review warnings into testable frontend utility modules.
6. Deploy frontend to Vercel.
7. Deploy FastAPI backend separately and set `VITE_API_BASE_URL`.
