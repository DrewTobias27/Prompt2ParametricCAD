"""Local web app for Prompt2CAD."""

from collections import OrderedDict
from copy import deepcopy
import json
from pathlib import Path
import re
from time import perf_counter
from typing import Any

import cadquery as cq
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from prompt2cad.interpreter import build_model
from prompt2cad.design_intent import intent_to_model_data
from prompt2cad.generation_log import save_generation_log
from prompt2cad.prompting import prompt_to_design_intent
from prompt2cad.prompting import prompt_to_model_data_with_repair
from prompt2cad.prompting import suggest_base_model_data
from prompt2cad.prompting import suggest_feature_model_data
from prompt2cad.quality import check_model_quality
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


class DemoBuildRequest(BaseModel):
    demo_id: str


app = FastAPI()
GENERATED_DIR = Path("generated/web")
WEB_DIR = Path(__file__).parent / "web"
REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_MAX_ENTRIES = 64
SUCCESS_RESPONSE_CACHE: OrderedDict[str, dict] = OrderedDict()
GENERATED_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


DEMO_EXAMPLES = [
    {
        "id": "flange",
        "title": "Circular flange with bolt holes",
        "prompt": (
            "Create an 80 mm diameter circular flange, 8 mm thick, with six "
            "6 mm circular through holes evenly spaced around the center."
        ),
        "fallback_model_path": REPO_ROOT
        / "examples"
        / "library"
        / "circular_flange_six_bolt_holes.json",
    },
    {
        "id": "block-side-hole-boss",
        "title": "Block with side hole and top boss",
        "prompt": (
            "Create an 80 by 50 by 20 mm rectangular block. Add a centered "
            "10 mm circular through hole on the front face and a raised "
            "rectangular boss on the top face."
        ),
        "fallback_model_path": REPO_ROOT
        / "examples"
        / "library"
        / "rectangular_block_front_hole_top_boss.json",
    },
    {
        "id": "l-plate-cut",
        "title": "L-shaped plate with rectangular cut",
        "prompt": (
            "Create an L-shaped plate with a rectangular through cut near "
            "the inside corner."
        ),
        "fallback_model_path": REPO_ROOT
        / "examples"
        / "library"
        / "l_shaped_plate_rectangular_cut.json",
    },
    {
        "id": "capsule",
        "title": "Capsule revolved from true arcs",
        "prompt": (
            "Create a capsule-shaped cylinder with hemispherical ends, "
            "20 mm diameter and 80 mm long."
        ),
        "fallback_model_path": REPO_ROOT
        / "examples"
        / "library"
        / "capsule_revolve_with_arc_sketch.json",
    },
]


@app.get("/")
def home():
    """Return the home page."""
    return FileResponse(WEB_DIR / "index.html")


@app.get("/demo-examples")
def demo_examples():
    """Return curated demo prompts and saved fallback examples."""
    return {
        "examples": [
            {
                "id": example["id"],
                "title": example["title"],
                "prompt": example["prompt"],
                "has_saved_fallback": example["fallback_model_path"].exists(),
            }
            for example in DEMO_EXAMPLES
        ]
    }


def make_safe_filename(prompt: str) -> str:
    """Convert a prompt into a safe STEP filename."""
    name = prompt.lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    name = name.strip("-")
    name = name[:60]

    if not name:
        name = "prompt2cad-model"

    return f"{name}.step"


def seconds_since(started_at: float) -> float:
    """Return rounded elapsed seconds for user-facing performance data."""
    return round(perf_counter() - started_at, 3)


def cache_key(kind: str, payload: dict[str, Any]) -> str:
    """Return a stable key for exact-result caching."""
    import json

    return (
        f"{kind}:"
        + json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    )


def request_payload(request: BaseModel) -> dict[str, Any]:
    """Return request data for cache keys across Pydantic versions."""
    if hasattr(request, "model_dump"):
        return request.model_dump()
    return request.dict()


def get_cached_success_response(key: str) -> dict | None:
    """Return a cached successful response copy, if available."""
    cached_response = SUCCESS_RESPONSE_CACHE.get(key)
    if cached_response is None:
        return None

    SUCCESS_RESPONSE_CACHE.move_to_end(key)
    response = deepcopy(cached_response)
    performance = dict(response.get("performance", {}))
    performance["cache_hit"] = True
    performance["served_from_cache"] = True
    response["performance"] = performance
    return response


def cache_success_response(key: str, response_data: dict) -> None:
    """Cache a successful response without changing caller-visible behavior."""
    if response_data.get("status") != "success":
        return

    SUCCESS_RESPONSE_CACHE[key] = deepcopy(response_data)
    SUCCESS_RESPONSE_CACHE.move_to_end(key)
    while len(SUCCESS_RESPONSE_CACHE) > CACHE_MAX_ENTRIES:
        SUCCESS_RESPONSE_CACHE.popitem(last=False)


def export_model_data(model_data: dict, filename_hint: str) -> dict:
    """Validate, build, export, and return web response data for a CAD model."""
    started_at = perf_counter()
    validate_model_data(model_data)
    validation_seconds = seconds_since(started_at)

    build_started_at = perf_counter()
    part = build_model(model_data)
    build_seconds = seconds_since(build_started_at)

    export_started_at = perf_counter()
    step_filename = make_safe_filename(filename_hint)
    step_path = GENERATED_DIR / step_filename
    cq.exporters.export(part, str(step_path))
    export_seconds = seconds_since(export_started_at)

    quality_started_at = perf_counter()
    quality_report = check_model_quality(
        model_data,
        build_succeeded=True,
        built_part=part,
        exported_path=step_path,
    )
    quality_seconds = seconds_since(quality_started_at)

    return {
        "status": "success",
        "model_data": model_data,
        "quality_report": quality_report,
        "step_file": str(step_path),
        "download_url": f"/download/{step_filename}",
        "performance": {
            "validation_seconds": validation_seconds,
            "build_seconds": build_seconds,
            "export_seconds": export_seconds,
            "quality_seconds": quality_seconds,
            "export_model_total_seconds": seconds_since(started_at),
            "cache_hit": False,
        },
    }


def load_demo_model_data(demo_id: str) -> tuple[dict, str]:
    """Load whitelisted saved demo model data."""
    for example in DEMO_EXAMPLES:
        if example["id"] == demo_id:
            example_data = json.loads(
                example["fallback_model_path"].read_text(encoding="utf-8")
            )
            return example_data.get("model_data", example_data), example["title"]

    raise ValueError(f"Unknown demo example: {demo_id}")


def with_repair_history(response_data: dict, repair_history: list[dict]) -> dict:
    """Attach repair history to a web response when repair was attempted."""
    if repair_history:
        response_data["repair_history"] = repair_history

    return response_data


def attach_generation_log(
    response_data: dict,
    *,
    prompt: str,
    repair_history: list[dict],
    error_message: str | None = None,
    generation_mode: str = "prompt",
) -> dict:
    """Save useful prompt-generation failures/repairs and attach log path."""
    if not repair_history and error_message is None:
        return response_data

    log_path = save_generation_log(
        prompt=prompt,
        status=response_data.get("status", "unknown"),
        final_model_data=response_data.get("model_data"),
        repair_history=repair_history,
        quality_report=response_data.get("quality_report"),
        error_message=error_message,
        generation_mode=generation_mode,
    )
    response_data["generation_log"] = str(log_path)
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
    started_at = perf_counter()
    key = cache_key("generate", {"prompt": request.prompt})
    cached_response = get_cached_success_response(key)
    if cached_response is not None:
        cached_response["performance"]["total_seconds"] = seconds_since(started_at)
        return cached_response

    try:
        api_started_at = perf_counter()
        model_data, repair_history = prompt_to_model_data_with_repair(
            request.prompt,
            max_repairs=1,
        )
        api_seconds = seconds_since(api_started_at)
        response_data = with_repair_history(
            export_model_data(model_data, request.prompt),
            repair_history,
        )
        performance = dict(response_data.get("performance", {}))
        performance.update({
            "api_seconds": api_seconds,
            "total_seconds": seconds_since(started_at),
            "cache_hit": False,
        })
        response_data["performance"] = performance
        response_data = attach_generation_log(
            response_data,
            prompt=request.prompt,
            repair_history=repair_history,
        )
        cache_success_response(key, response_data)
        return response_data
    except Exception as error:
        repair_history = repair_history if "repair_history" in locals() else []
        response_data = {
            "status": "error",
            "message": str(error),
            "model_data": model_data if "model_data" in locals() else None,
            "quality_report": (
                check_model_quality(model_data, build_error=str(error))
                if "model_data" in locals()
                else check_model_quality(None)
            ),
            "repair_history": repair_history,
            "performance": {
                "total_seconds": seconds_since(started_at),
                "cache_hit": False,
            },
        }
        return attach_generation_log(
            response_data,
            prompt=request.prompt,
            repair_history=repair_history,
            error_message=str(error),
        )


@app.post("/generate-intent")
def generate_cad_from_design_intent(request: CADRequest):
    """Generate CAD through the experimental design-intent pipeline."""
    started_at = perf_counter()
    key = cache_key("generate-intent", {"prompt": request.prompt})
    cached_response = get_cached_success_response(key)
    if cached_response is not None:
        cached_response["performance"]["total_seconds"] = seconds_since(started_at)
        return cached_response

    try:
        api_started_at = perf_counter()
        design_intent = prompt_to_design_intent(request.prompt)
        api_seconds = seconds_since(api_started_at)

        lowering_started_at = perf_counter()
        model_data = intent_to_model_data(design_intent)
        lowering_seconds = seconds_since(lowering_started_at)

        response_data = export_model_data(
            model_data,
            f"intent {request.prompt}",
        )
        response_data["design_intent"] = design_intent
        response_data["generation_mode"] = "design_intent"
        performance = dict(response_data.get("performance", {}))
        performance.update({
            "api_seconds": api_seconds,
            "lowering_seconds": lowering_seconds,
            "total_seconds": seconds_since(started_at),
            "cache_hit": False,
        })
        response_data["performance"] = performance
        cache_success_response(key, response_data)
        return response_data
    except Exception as error:
        return {
            "status": "error",
            "message": str(error),
            "design_intent": design_intent if "design_intent" in locals() else None,
            "model_data": model_data if "model_data" in locals() else None,
            "quality_report": (
                check_model_quality(model_data, build_error=str(error))
                if "model_data" in locals()
                else check_model_quality(None)
            ),
            "generation_mode": "design_intent",
            "performance": {
                "total_seconds": seconds_since(started_at),
                "cache_hit": False,
            },
        }


@app.post("/build")
def build_cad(request: CADBuildRequest):
    """Build CAD directly from structured model data."""
    started_at = perf_counter()
    model_data = request.model_data

    try:
        response_data = export_model_data(model_data, request.filename_hint)
        performance = dict(response_data.get("performance", {}))
        performance["total_seconds"] = seconds_since(started_at)
        response_data["performance"] = performance
        return response_data
    except Exception as error:
        return {
            "status": "error",
            "message": str(error),
            "model_data": model_data if "model_data" in locals() else None,
            "quality_report": (
                check_model_quality(model_data, build_error=str(error))
                if "model_data" in locals()
                else check_model_quality(None)
            ),
            "performance": {
                "total_seconds": seconds_since(started_at),
                "cache_hit": False,
            },
        }


@app.post("/build-demo")
def build_demo(request: DemoBuildRequest):
    """Build a saved demo model without making an API call."""
    started_at = perf_counter()
    try:
        model_data, title = load_demo_model_data(request.demo_id)
        response_data = export_model_data(model_data, f"demo {title}")
        response_data["generation_mode"] = "saved_demo"
        performance = dict(response_data.get("performance", {}))
        performance["total_seconds"] = seconds_since(started_at)
        response_data["performance"] = performance
        return response_data
    except Exception as error:
        return {
            "status": "error",
            "message": str(error),
            "model_data": None,
            "generation_mode": "saved_demo",
            "performance": {
                "total_seconds": seconds_since(started_at),
                "cache_hit": False,
            },
        }


@app.post("/suggest-base")
def suggest_base(request: CADSuggestBaseRequest):
    """Suggest one base extrusion model for the manual builder."""
    started_at = perf_counter()
    key = cache_key(
        "suggest-base",
        request_payload(request),
    )
    cached_response = get_cached_success_response(key)
    if cached_response is not None:
        cached_response["performance"]["total_seconds"] = seconds_since(started_at)
        return cached_response

    try:
        api_started_at = perf_counter()
        model_data = suggest_base_model_data(
            profile=request.profile,
            description=request.description,
            distance=request.distance,
        )
        api_seconds = seconds_since(api_started_at)
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

        response_data = {
            "status": "success",
            "model_data": model_data,
            "performance": {
                "api_seconds": api_seconds,
                "total_seconds": seconds_since(started_at),
                "cache_hit": False,
            },
        }
        cache_success_response(key, response_data)
        return response_data
    except Exception as error:
        return {
            "status": "error",
            "message": str(error),
            "model_data": model_data if "model_data" in locals() else None,
            "performance": {
                "total_seconds": seconds_since(started_at),
                "cache_hit": False,
            },
        }


@app.post("/suggest-feature")
def suggest_feature(request: CADSuggestFeatureRequest):
    """Suggest one feature operation for the manual builder."""
    started_at = perf_counter()
    key = cache_key(
        "suggest-feature",
        request_payload(request),
    )
    cached_response = get_cached_success_response(key)
    if cached_response is not None:
        cached_response["performance"]["total_seconds"] = seconds_since(started_at)
        return cached_response

    try:
        api_started_at = perf_counter()
        model_data = suggest_feature_model_data(
            operation_type=request.operation_type,
            target=request.target,
            profile=request.profile,
            description=request.description,
        )
        api_seconds = seconds_since(api_started_at)
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

        response_data = {
            "status": "success",
            "model_data": model_data,
            "performance": {
                "api_seconds": api_seconds,
                "total_seconds": seconds_since(started_at),
                "cache_hit": False,
            },
        }
        cache_success_response(key, response_data)
        return response_data
    except Exception as error:
        return {
            "status": "error",
            "message": str(error),
            "model_data": model_data if "model_data" in locals() else None,
            "performance": {
                "total_seconds": seconds_since(started_at),
                "cache_hit": False,
            },
        }
