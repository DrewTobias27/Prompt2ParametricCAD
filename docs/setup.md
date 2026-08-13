# Setup and development

## Prerequisites

- Python 3.11 or 3.12
- Node.js
- pnpm
- Git
- OpenAI API key for prompt generation

CadQuery includes compiled geometry dependencies. Use a clean virtual or Conda
environment if it conflicts with another Python installation.

## Install

```powershell
git clone https://github.com/DrewTobias27/Prompt2ParametricCAD.git
cd Prompt2ParametricCAD

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

cd frontend
pnpm install
cd ..
```

If PowerShell blocks environment activation or project scripts, use a process-
scoped bypass rather than changing machine-wide policy:

```powershell
powershell -ExecutionPolicy Bypass
```

## Credentials

Set the key only in an environment variable:

```powershell
$env:OPENAI_API_KEY = "your-key"
```

Do not paste keys into source, JSON, `.env` files that are not ignored, terminal
commands saved in documentation, or Git commits.

Optional model overrides:

```powershell
$env:PROMPT2CAD_OPENAI_MODEL = "gpt-5-mini"
$env:PROMPT2CAD_INTENT_REPAIR_MODEL = "gpt-5-mini"
$env:PROMPT2CAD_REASONING_EFFORT = "low"
```

### Compare generation models safely

The production default is `gpt-5.5` with low reasoning effort. It won the
repeated model matrix on production success, repair recovery, latency, and token
use. The model-matrix runner compares candidate models using the same prompts,
reasoning effort, strict schema, intent checks, geometry checks, and
operation-effect checks. Each production run records and scores its exact
unrepaired first-pass candidate before conditionally repairing it, so repairs do
not hide weak initial interpretation and the comparison does not spend a
duplicate sampling call:

```powershell
$env:PYTHONPATH = "src"
python -m prompt2cad.model_matrix_eval --reasoning-effort low
```

Use one run to screen every model. Then rerun the strongest two with
`--repetitions 3` so one lucky or unlucky sample does not decide production
routing.

The default matrix includes `gpt-5.5`, `gpt-5.6-sol`, `gpt-5.6-terra`, and
`gpt-5.6-luna`. Its correctness-first ranking uses strict pass/warn/fail counts,
then first-pass success, repair count, latency, and token use. Promote a model
through `PROMPT2CAD_INTENT_MODEL` only after it wins that representative matrix.
A stronger repair model can be configured separately with
`PROMPT2CAD_INTENT_REPAIR_MODEL`.

## Verify the environment

```powershell
.\scripts\check_setup.ps1
python -m pytest
```

If `python` or `pnpm` is not the desired executable:

```powershell
$env:PROMPT2CAD_PYTHON = "C:\Path\To\python.exe"
$env:PROMPT2CAD_NODE = "C:\Path\To\node.exe"
$env:PROMPT2CAD_PNPM = "C:\Path\To\pnpm.cmd"
```

## Run the complete application

The launch script builds React, then serves the frontend and FastAPI backend
together:

```powershell
.\scripts\run_app.ps1
```

Open `http://127.0.0.1:8000/`.

Useful options:

```powershell
.\scripts\run_app.ps1 -SkipFrontendBuild
.\scripts\run_app.ps1 -Port 8080
.\scripts\run_app.ps1 -Network
```

`-Network` binds to `0.0.0.0`. Only use it on a trusted private network.

## Frontend development

Use two terminals for hot reload.

Backend:

```powershell
$env:PYTHONPATH = "src"
python -m uvicorn prompt2cad.web_app:app --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd frontend
pnpm dev
```

Open `http://127.0.0.1:5173/`. Vite proxies `/api` requests to port 8000.

## Frontend QA

```powershell
cd frontend
pnpm build
pnpm qa
```

## Common problems

### `prompt2cad` cannot be imported

Install the package in editable mode with `python -m pip install -e ".[dev]"`,
or set `$env:PYTHONPATH = "src"` for a one-off command.

### Port 8000 is already in use

Stop the older server with `Ctrl+C`, or run:

```powershell
.\scripts\run_app.ps1 -Port 8001
```

### Frontend changes do not appear

Use Vite development mode, or rebuild before starting FastAPI. A hard refresh
may be needed after replacing a production build.

### Prompt generation says credentials are missing

The key must be set in the same terminal process that starts FastAPI. Open a new
terminal after setting a persistent user environment variable.
