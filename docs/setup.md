# Windows setup guide

This guide describes how to set up Prompt2ParametricCAD on Windows from a fresh
clone.

CadQuery can be more sensitive to Python environment details than a normal web
app, so the most important rule is: use one clean Python environment and run all
commands from that environment.

## 1. Clone the repository

```powershell
git clone https://github.com/DrewTobias27/Prompt2ParametricCAD.git
cd Prompt2ParametricCAD
```

## 2. Create and activate a Python environment

Use Python 3.12 if possible, since that is the version currently used by the
working development environment.

One common option is a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation scripts, run this once for the current user:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then close and reopen the terminal, activate the environment again, and continue.

## 3. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If CadQuery installation fails through `pip`, use a Conda environment instead.
CadQuery often behaves better through Conda on some machines.

## 4. Check the setup

Run the setup checker:

```powershell
.\scripts\check_setup.ps1
```

If PowerShell blocks the script, either use the execution-policy command from
step 2 or run the checker with a one-time process bypass:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check_setup.ps1
```

The checker verifies:

- Python is available
- required packages import correctly
- `PYTHONPATH` is pointed at `src`
- a tiny CadQuery model can be built through the project interpreter
- whether `OPENAI_API_KEY` is available for prompt-based generation

The OpenAI key is optional for local JSON builds and fixture-backed evals. It is
only required when using prompt generation.

## 5. Run tests

```powershell
$env:PYTHONPATH = "src"
python -m pytest
```

## 6. Run evals

Some evals use tracked fixtures and do not require API calls.

```powershell
$env:PYTHONPATH = "src"
python -m prompt2cad.eval_runner --models-dir generated\evals --cases-dir evals\cases
```

If generated eval JSON files are missing, generate fixture-backed and API-backed
eval outputs:

```powershell
$env:PYTHONPATH = "src"
python -m prompt2cad.eval_generator --overwrite
```

API-backed eval generation requires `OPENAI_API_KEY`.

## 7. Run the web app

```powershell
.\scripts\run_web_app.ps1
```

Then open:

```text
http://127.0.0.1:8000/
```

Leave that terminal running while using the web app. Press `Ctrl+C` to stop it.

## 8. Run a laptop demo server

To run the CAD backend on this computer and open the frontend from another
laptop on the same network:

```powershell
.\scripts\run_demo_server.ps1
```

Then open `http://THIS-COMPUTER-IP:8000/` from the laptop. See
`docs/demo_checklist.md` for the full demo runbook and fallback plan.

## Optional: set an OpenAI API key

For the current PowerShell session:

```powershell
$env:OPENAI_API_KEY = "your-api-key-here"
```

For future PowerShell sessions:

```powershell
[Environment]::SetEnvironmentVariable("OPENAI_API_KEY", "your-api-key-here", "User")
```

After setting a persistent key, open a new terminal before running the web app.

Never commit API keys into the repository.

## Optional: use a specific Python executable

The helper scripts use `python` from the active environment by default. If you
need to point them to a specific interpreter, set `PROMPT2CAD_PYTHON`:

```powershell
$env:PROMPT2CAD_PYTHON = "C:\Path\To\python.exe"
.\scripts\check_setup.ps1
.\scripts\run_web_app.ps1
```

This is useful when several Python environments are installed.
