# Prompt2ParametricCAD Frontend

This is the new React/Vite frontend for Prompt2ParametricCAD.

The Python FastAPI backend still builds CAD models with CadQuery. During local
development, Vite proxies `/api/*` requests to `http://127.0.0.1:8000`.

## Local development

In one terminal, run the Python backend from the repository root:

```powershell
.\scripts\run_web_app.ps1
```

In another terminal, run the frontend:

```powershell
cd frontend
npm install
npm run dev
```

Then open:

```text
http://127.0.0.1:5173/
```

## Vercel deployment

Deploy the `frontend/` directory as the Vercel project root.

For a deployed backend, set:

```text
VITE_API_BASE_URL=https://your-backend-host.example.com
```

The CadQuery backend should be hosted separately on a Python-friendly platform.
