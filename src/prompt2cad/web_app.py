"""Local web app for Prompt2CAD."""

from pathlib import Path

import cadquery as cq
from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from prompt2cad.interpreter import build_model
from prompt2cad.prompting import prompt_to_model_data
from prompt2cad.schema import validate_model_data


class CADRequest(BaseModel):
    prompt: str


app = FastAPI()
GENERATED_DIR = Path("generated/web")
GENERATED_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/", response_class=HTMLResponse)
def home():
    """Return the home page."""
    return """
    <!doctype html>
    <html>
        <head>
            <title>Prompt2CAD Web App</title>
        </head>
        <body>
            <h1>Prompt2CAD</h1>
            <p>Turn natural language into parametric CAD.</p>
            <textarea id="prompt" rows="4" cols="50" placeholder="Enter your CAD prompt here..."></textarea><br>
            <button id="generateButton" onclick="generateCAD()">Generate CAD</button>
            <pre id="output"></pre>
            <p id="status"></p>
            <a id="downloadLink" href="#" style="display: none;">Download STEP file</a>
            <script>
                function generateCAD() {
                    const button = document.getElementById("generateButton");
                    const downloadLink = document.getElementById("downloadLink");
                    const prompt = document.getElementById("prompt").value;
                    const status = document.getElementById("status");
                    status.textContent = "Generating CAD model...";
                    button.disabled = true;
                    button.textContent = "Generating...";
                    fetch("/generate", {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({ prompt: prompt })
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === "success") {
                            status.textContent = "Success";
                            downloadLink.style.display = "block";
                            downloadLink.href = data.download_url;
                        } else {
                            status.textContent = "Error: " + data.message;
                            downloadLink.style.display = "none";
                        }
                        document.getElementById("output").textContent = JSON.stringify(data, null, 2);
                    })
                    .catch(error => {
                        status.textContent = "Error: " + error;
                        console.error("Error:", error);
                        downloadLink.style.display = "none";
                    })
                    .finally(() => {
                        button.disabled = false;
                        button.textContent = "Generate CAD";
                    });
                }
            </script>
        </body>
    </html>
    """


@app.get("/download/latest_model.step")
def download_latest_step():
    step_path = GENERATED_DIR / "latest_model.step"
    return FileResponse(
        path=step_path,
        filename="prompt2cad_model.step",
        media_type="application/step",
    )


@app.post("/generate")
def generate_cad(request: CADRequest):
    """Generate CAD model data from a natural language prompt."""
    try:
        model_data = prompt_to_model_data(request.prompt)
        validate_model_data(model_data)
        part = build_model(model_data)
        step_path = GENERATED_DIR / "latest_model.step"
        cq.exporters.export(part, str(step_path))
        return {
            "status": "success",
            "model_data": model_data,
            "step_file": str(step_path),
            "download_url": "/download/latest_model.step",
        }
    except Exception as error:
        return {
            "status": "error",
            "message": str(error),
            "model_data": model_data if "model_data" in locals() else None,
        }
