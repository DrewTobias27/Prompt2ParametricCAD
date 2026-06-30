"""Local web app for Prompt2CAD."""

from pathlib import Path
import re

import cadquery as cq
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from prompt2cad.interpreter import build_model
from prompt2cad.prompting import prompt_to_model_data_with_repair
from prompt2cad.prompting import suggest_base_model_data
from prompt2cad.prompting import suggest_feature_model_data
from prompt2cad.schema import validate_model_data


class CADRequest(BaseModel):
    prompt: str


class CADBuildRequest(BaseModel):
    model_data: dict
    filename_hint: str = "manual-builder-model"


class CADSuggestBaseRequest(BaseModel):
    profile: str
    description: str = ""
    distance: float | None = None


class CADSuggestFeatureRequest(BaseModel):
    operation_type: str
    target: str
    profile: str
    description: str = ""


app = FastAPI()
GENERATED_DIR = Path("generated/web")
WEB_DIR = Path(__file__).parent / "web"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/")
def home():
    """Return the home page."""
    return FileResponse(WEB_DIR / "index.html")


def make_safe_filename(prompt: str) -> str:
    """Convert a prompt into a safe STEP filename."""
    name = prompt.lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    name = name.strip("-")
    name = name[:60]

    if not name:
        name = "prompt2cad-model"

    return f"{name}.step"


def export_model_data(model_data: dict, filename_hint: str) -> dict:
    """Validate, build, export, and return web response data for a CAD model."""
    validate_model_data(model_data)
    part = build_model(model_data)
    step_filename = make_safe_filename(filename_hint)
    step_path = GENERATED_DIR / step_filename
    cq.exporters.export(part, str(step_path))

    return {
        "status": "success",
        "model_data": model_data,
        "step_file": str(step_path),
        "download_url": f"/download/{step_filename}",
    }


def with_repair_history(response_data: dict, repair_history: list[dict]) -> dict:
    """Attach repair history to a web response when repair was attempted."""
    if repair_history:
        response_data["repair_history"] = repair_history

    return response_data


@app.get("/download/{filename}")
def download_step_file(filename: str):
    """Download a generated STEP file."""
    step_path = GENERATED_DIR / filename
    return FileResponse(
        path=step_path,
        filename=filename,
        media_type="application/step",
    )


@app.post("/generate")
def generate_cad(request: CADRequest):
    """Generate CAD model data from a natural language prompt."""
    try:
        model_data, repair_history = prompt_to_model_data_with_repair(
            request.prompt,
            max_repairs=1,
        )
        return with_repair_history(
            export_model_data(model_data, request.prompt),
            repair_history,
        )
    except Exception as error:
        return {
            "status": "error",
            "message": str(error),
            "model_data": model_data if "model_data" in locals() else None,
            "repair_history": repair_history if "repair_history" in locals() else [],
        }


@app.post("/build")
def build_cad(request: CADBuildRequest):
    """Build CAD directly from structured model data."""
    model_data = request.model_data

    try:
        return export_model_data(model_data, request.filename_hint)
    except Exception as error:
        return {
            "status": "error",
            "message": str(error),
            "model_data": model_data if "model_data" in locals() else None,
        }


@app.post("/suggest-base")
def suggest_base(request: CADSuggestBaseRequest):
    """Suggest one base extrusion model for the manual builder."""
    try:
        model_data = suggest_base_model_data(
            profile=request.profile,
            description=request.description,
            distance=request.distance,
        )
        validate_model_data(model_data)

        operations = model_data["operations"]
        if len(operations) != 1:
            raise ValueError("Suggested base model must contain exactly one operation")

        operation = operations[0]
        if operation["type"] != "extrude":
            raise ValueError("Suggested base operation must be an extrusion")

        if operation["profile"] != request.profile:
            raise ValueError(
                "Suggested base operation profile did not match selected profile"
            )

        return {
            "status": "success",
            "model_data": model_data,
        }
    except Exception as error:
        return {
            "status": "error",
            "message": str(error),
            "model_data": model_data if "model_data" in locals() else None,
        }


@app.post("/suggest-feature")
def suggest_feature(request: CADSuggestFeatureRequest):
    """Suggest one feature operation for the manual builder."""
    try:
        model_data = suggest_feature_model_data(
            operation_type=request.operation_type,
            target=request.target,
            profile=request.profile,
            description=request.description,
        )
        validate_model_data(model_data)

        operations = model_data["operations"]
        if len(operations) != 1:
            raise ValueError("Suggested feature must contain exactly one operation")

        operation = operations[0]
        if operation["type"] != request.operation_type:
            raise ValueError("Suggested feature operation type did not match selection")

        if operation["target"] != request.target:
            raise ValueError("Suggested feature target did not match selection")

        if operation["profile"] != request.profile:
            raise ValueError("Suggested feature profile did not match selection")

        return {
            "status": "success",
            "model_data": model_data,
        }
    except Exception as error:
        return {
            "status": "error",
            "message": str(error),
            "model_data": model_data if "model_data" in locals() else None,
        }
