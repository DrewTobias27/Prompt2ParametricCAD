"""Local web app for Prompt2CAD."""

from collections import OrderedDict
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
from time import perf_counter
from typing import Any

import cadquery as cq
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from prompt2cad.editable_model import model_data_to_editable_document
from prompt2cad.editable_model import rebuild_with_parameter_updates
from prompt2cad.interpreter import build_model
from prompt2cad.design_intent import intent_to_model_data
from prompt2cad.generation_log import save_generation_log
from prompt2cad.prompting import max_repair_attempts
from prompt2cad.prompting import prompt_to_design_intent_with_feedback
from prompt2cad.prompting import prompt_to_model_data_with_repair
from prompt2cad.prompting import refine_design_intent_with_feedback
from prompt2cad.prompting import suggest_base_model_data
from prompt2cad.prompting import suggest_feature_model_data
from prompt2cad.quality import check_model_quality
from prompt2cad.schema import validate_model_data
from prompt2cad.solidworks_package import create_solidworks_package
from prompt2cad.web_runtime import cleanup_step_files
from prompt2cad.web_runtime import environment_int
from prompt2cad.web_runtime import SlidingWindowRateLimiter


class CADRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)


class CADRefineRequest(BaseModel):
    original_prompt: str = Field(min_length=1, max_length=2000)
    correction: str = Field(min_length=1, max_length=1000)
    design_intent: dict
    revision: int = 1


class CADBuildRequest(BaseModel):
    model_data: dict
    filename_hint: str = "manual-builder-model"


class CADEditableModelRequest(BaseModel):
    model_data: dict


class CADSolidWorksPackageRequest(BaseModel):
    model_data: dict
    filename_hint: str = "prompt2cad-model"


class CADParameterEditRequest(BaseModel):
    model_data: dict
    updates: dict[str, Any]
    filename_hint: str = "edited-model"


class CADSuggestBaseRequest(BaseModel):
    profile: str
    description: str = ""
    distance: float | None = None


class CADSuggestFeatureRequest(BaseModel):
    operation_type: str
    target: str
    profile: str
    description: str = ""


app = FastAPI(
    title="Prompt2ParametricCAD API",
    description="Generate, validate, build, and export parametric CAD models.",
    version="0.2.0",
)
GENERATED_DIR = Path("generated/web")
REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIST_DIR = REPO_ROOT / "frontend" / "dist"
CACHE_MAX_ENTRIES = 64
MAX_AUTOMATIC_API_CALLS = 4
PUBLIC_RATE_LIMIT_REQUESTS = environment_int(
    "PROMPT2CAD_PUBLIC_RATE_LIMIT_REQUESTS",
    0,
)
PUBLIC_RATE_LIMIT_WINDOW_SECONDS = environment_int(
    "PROMPT2CAD_PUBLIC_RATE_LIMIT_WINDOW_SECONDS",
    3600,
    minimum=1,
)
STEP_MAX_AGE_SECONDS = environment_int(
    "PROMPT2CAD_STEP_MAX_AGE_SECONDS",
    3600,
)
STEP_MAX_FILES = environment_int("PROMPT2CAD_STEP_MAX_FILES", 50)
RATE_LIMITED_PATHS = {
    "/generate",
    "/refine",
    "/suggest-base",
    "/suggest-feature",
}
PUBLIC_RATE_LIMITER = SlidingWindowRateLimiter(
    limit=PUBLIC_RATE_LIMIT_REQUESTS,
    window_seconds=PUBLIC_RATE_LIMIT_WINDOW_SECONDS,
)
SUCCESS_RESPONSE_CACHE: OrderedDict[str, dict] = OrderedDict()
GENERATED_DIR.mkdir(parents=True, exist_ok=True)

if (FRONTEND_DIST_DIR / "assets").exists():
    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_DIST_DIR / "assets"),
        name="frontend-assets",
    )


def request_client_key(request: Request) -> str:
    """Return the best available client address from a managed reverse proxy."""
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"


@app.middleware("http")
async def limit_public_ai_requests(request: Request, call_next):
    """Protect public AI-backed routes from accidental or automated overuse."""
    if request.method != "POST" or request.url.path not in RATE_LIMITED_PATHS:
        return await call_next(request)

    allowed, remaining, retry_after = PUBLIC_RATE_LIMITER.check(
        request_client_key(request)
    )
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={
                "status": "error",
                "message": "Generation limit reached. Please try again later.",
            },
            headers={"Retry-After": str(retry_after)},
        )

    response = await call_next(request)
    if PUBLIC_RATE_LIMIT_REQUESTS > 0:
        response.headers["X-RateLimit-Limit"] = str(PUBLIC_RATE_LIMIT_REQUESTS)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
    return response


@app.get("/")
def home():
    """Serve the production frontend or a useful API status response."""
    frontend_index = FRONTEND_DIST_DIR / "index.html"
    if frontend_index.exists():
        return FileResponse(frontend_index)

    return {
        "name": app.title,
        "status": "ok",
        "frontend": "not built",
        "message": "Run the Vite frontend or build frontend/dist.",
    }


@app.get("/health")
def health():
    """Return a lightweight backend health check."""
    return {"status": "ok"}


def make_safe_filename(prompt: str) -> str:
    """Convert a prompt into a safe STEP filename."""
    name = prompt.lower()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    name = name.strip("-")
    name = name[:60]

    if not name:
        name = "prompt2cad-model"

    prompt_hash = sha256(prompt.encode("utf-8")).hexdigest()[:8]
    return f"{name}-{prompt_hash}.step"


def seconds_since(started_at: float) -> float:
    """Return rounded elapsed seconds for user-facing performance data."""
    return round(perf_counter() - started_at, 3)


def cache_key(kind: str, payload: dict[str, Any]) -> str:
    """Return a stable key for exact-result caching."""
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


def cleanup_generated_downloads() -> None:
    """Prune temporary downloads and remove stale responses from the cache."""
    removed_paths = cleanup_step_files(
        GENERATED_DIR,
        max_age_seconds=STEP_MAX_AGE_SECONDS,
        max_files=STEP_MAX_FILES,
    )
    if not removed_paths:
        return

    removed_filenames = {path.name for path in removed_paths}
    stale_cache_keys = [
        key
        for key, response in SUCCESS_RESPONSE_CACHE.items()
        if Path(response.get("step_file", "")).name in removed_filenames
    ]
    for key in stale_cache_keys:
        SUCCESS_RESPONSE_CACHE.pop(key, None)


def export_model_data(
    model_data: dict,
    filename_hint: str,
    *,
    built_part: cq.Workplane | None = None,
) -> dict:
    """Validate, build, export, and return web response data for a CAD model."""
    started_at = perf_counter()
    validate_model_data(model_data)
    validation_seconds = seconds_since(started_at)

    build_started_at = perf_counter()
    part = built_part if built_part is not None else build_model(model_data)
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
    export_model_total_seconds = seconds_since(started_at)
    cleanup_generated_downloads()

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
            "export_model_total_seconds": export_model_total_seconds,
            "local_processing_seconds": export_model_total_seconds,
            "cache_hit": False,
            "build_reused": built_part is not None,
        },
    }


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


def should_try_direct_fallback(error: Exception) -> bool:
    """Return whether a failed intent attempt merits a direct-generation retry."""
    status_code = getattr(error, "status_code", None)
    if status_code is not None and status_code != 400:
        return False

    message = str(error).lower()
    nonrecoverable_phrases = (
        "missing credentials",
        "invalid api key",
        "incorrect api key",
        "insufficient_quota",
        "rate limit",
        "connection error",
        "timed out",
        "timeout",
    )
    return not any(phrase in message for phrase in nonrecoverable_phrases)


def combined_seconds(*values: float) -> float:
    """Return rounded combined timing values."""
    return round(sum(values), 3)


def operation_label(operation: dict, index: int) -> str:
    """Return a stable, readable label for a lowered CAD operation."""
    operation_id = operation.get("id")
    return str(operation_id) if operation_id else f"operation_{index + 1}"


def summarize_operation_changes(
    previous_model_data: dict,
    revised_model_data: dict,
) -> dict:
    """Summarize meaningful operation-level changes between two revisions."""
    previous_operations = previous_model_data.get("operations", [])
    revised_operations = revised_model_data.get("operations", [])
    previous_operation_order = [
        operation_label(operation, index)
        for index, operation in enumerate(previous_operations)
    ]
    revised_operation_order = [
        operation_label(operation, index)
        for index, operation in enumerate(revised_operations)
    ]
    previous_by_label = {
        operation_label(operation, index): operation
        for index, operation in enumerate(previous_operations)
    }
    revised_by_label = {
        operation_label(operation, index): operation
        for index, operation in enumerate(revised_operations)
    }

    added_operations = [
        operation_label(operation, index)
        for index, operation in enumerate(revised_operations)
        if operation_label(operation, index) not in previous_by_label
    ]
    removed_operations = [
        operation_label(operation, index)
        for index, operation in enumerate(previous_operations)
        if operation_label(operation, index) not in revised_by_label
    ]
    changed_operations = [
        operation_label(operation, index)
        for index, operation in enumerate(revised_operations)
        if operation_label(operation, index) in previous_by_label
        and operation != previous_by_label[operation_label(operation, index)]
    ]
    operation_order_changed = (
        set(previous_operation_order) == set(revised_operation_order)
        and previous_operation_order != revised_operation_order
    )
    change_count = len(
        added_operations + removed_operations + changed_operations
    ) + int(operation_order_changed)
    return {
        "has_operation_changes": change_count > 0,
        "change_count": change_count,
        "added_operations": added_operations,
        "removed_operations": removed_operations,
        "changed_operations": changed_operations,
        "operation_order_changed": operation_order_changed,
    }


@app.get("/download/{filename}")
def download_step_file(filename: str):
    """Download a generated STEP file."""
    step_path = (GENERATED_DIR / filename).resolve()
    generated_directory = GENERATED_DIR.resolve()
    if (
        step_path.parent != generated_directory
        or step_path.suffix.lower() != ".step"
        or not step_path.is_file()
    ):
        raise HTTPException(status_code=404, detail="STEP file not found")
    return FileResponse(
        path=step_path,
        filename=filename,
        media_type="application/step",
    )


@app.post("/solidworks-package")
def download_solidworks_package(request: CADSolidWorksPackageRequest):
    """Return a validated local replay bundle for native SLDPRT creation."""
    try:
        package = create_solidworks_package(
            request.model_data,
            request.filename_hint,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=f"SolidWorks package is unavailable: {error}",
        ) from error
    except FileNotFoundError as error:
        raise HTTPException(
            status_code=500,
            detail="SolidWorks package assets are unavailable on the server.",
        ) from error

    return StreamingResponse(
        iter([package.content]),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{package.filename}"',
            "Cache-Control": "no-store",
            "X-Prompt2CAD-Package-Version": str(package.manifest["version"]),
            "X-Prompt2CAD-Numeric-Parameters": str(
                package.manifest["editability"]["numeric_parameter_count"]
            ),
            "X-Prompt2CAD-Named-Bindings": str(
                package.manifest["editability"]["named_binding_count"]
            ),
            "X-Prompt2CAD-Relation-Controls": str(
                package.manifest["editability"]["relation_controlled_count"]
            ),
            "X-Prompt2CAD-Unsupported-Parameters": str(
                package.manifest["editability"]["unsupported_count"]
            ),
            "X-Prompt2CAD-Control-Coverage": str(
                package.manifest["editability"]["control_coverage_ratio"]
            ),
            "Access-Control-Expose-Headers": (
                "Content-Disposition, X-Prompt2CAD-Package-Version, "
                "X-Prompt2CAD-Numeric-Parameters, "
                "X-Prompt2CAD-Named-Bindings, "
                "X-Prompt2CAD-Relation-Controls, "
                "X-Prompt2CAD-Unsupported-Parameters, "
                "X-Prompt2CAD-Control-Coverage"
            ),
        },
    )


@app.post("/generate")
def generate_cad(request: CADRequest):
    """Generate CAD through one intent-first pipeline with direct fallback."""
    started_at = perf_counter()
    key = cache_key("generate", {"prompt": request.prompt})
    cached_response = get_cached_success_response(key)
    if cached_response is not None:
        cached_response["performance"]["total_seconds"] = seconds_since(started_at)
        return cached_response

    design_intent = None
    intent_model_data = None
    intent_repair_history = []
    intent_evaluation = None
    intent_repair_limit = max_repair_attempts("intent")
    intent_api_started_at = perf_counter()
    intent_api_seconds = 0.0
    lowering_seconds = 0.0

    try:
        (
            design_intent,
            intent_model_data,
            intent_repair_history,
            intent_evaluation,
        ) = prompt_to_design_intent_with_feedback(
            request.prompt,
            max_repairs=intent_repair_limit,
        )
        intent_api_seconds = seconds_since(intent_api_started_at)

        lowering_started_at = perf_counter()
        if intent_model_data is None:
            intent_model_data = intent_to_model_data(design_intent)
        lowering_seconds = seconds_since(lowering_started_at)

        if not intent_evaluation.get("passed", False):
            raise ValueError(
                "Design-intent candidate failed feedback evaluation: "
                + json.dumps(intent_evaluation.get("feedback", {}))
            )

        response_data = export_model_data(intent_model_data, request.prompt)
        if response_data.get("quality_report", {}).get("status") == "fail":
            raise ValueError("Design-intent model failed the geometry quality gate")

        response_data["design_intent"] = design_intent
        if intent_repair_history:
            response_data["intent_repair_history"] = intent_repair_history
        response_data["generation_mode"] = "automatic"
        response_data["generation_path"] = "design_intent"
        response_data["revision"] = 1
        response_data["pipeline_attempts"] = [
            {"path": "design_intent", "status": "success"}
        ]
        performance = dict(response_data.get("performance", {}))
        performance.update({
            "api_seconds": intent_api_seconds,
            "intent_api_seconds": intent_api_seconds,
            "lowering_seconds": lowering_seconds,
            "local_processing_seconds": combined_seconds(
                lowering_seconds,
                performance.get("export_model_total_seconds", 0.0),
            ),
            "total_seconds": seconds_since(started_at),
            "cache_hit": False,
        })
        response_data["performance"] = performance
        cache_success_response(key, response_data)
        return response_data

    except Exception as intent_error:
        intent_failure = intent_error
        intent_repair_history = getattr(
            intent_error,
            "intent_repair_history",
            intent_repair_history,
        )
        if intent_api_seconds == 0.0:
            intent_api_seconds = seconds_since(intent_api_started_at)
        if "lowering_started_at" in locals() and lowering_seconds == 0.0:
            lowering_seconds = seconds_since(lowering_started_at)

    intent_attempt = {
        "path": "design_intent",
        "status": "failed",
        "message": str(intent_failure),
    }

    intent_repairs_exhausted = bool(
        intent_repair_limit > 0
        and len(intent_repair_history) >= intent_repair_limit
    )
    intent_api_attempts = getattr(
        intent_failure,
        "intent_api_attempts",
        1 + len(intent_repair_history),
    )
    remaining_api_calls = max(
        0,
        MAX_AUTOMATIC_API_CALLS - intent_api_attempts,
    )
    if (
        not should_try_direct_fallback(intent_failure)
        or intent_repairs_exhausted
        or remaining_api_calls == 0
    ):
        response_data = {
            "status": "error",
            "message": str(intent_failure),
            "design_intent": design_intent,
            "model_data": intent_model_data,
            "quality_report": (
                check_model_quality(intent_model_data, build_error=str(intent_failure))
                if intent_model_data is not None
                else check_model_quality(None)
            ),
            "generation_mode": "automatic",
            "generation_path": "design_intent",
            "pipeline_attempts": [intent_attempt],
            "intent_repair_history": intent_repair_history,
            "performance": {
                "api_seconds": intent_api_seconds,
                "intent_api_seconds": intent_api_seconds,
                "lowering_seconds": lowering_seconds,
                "total_seconds": seconds_since(started_at),
                "cache_hit": False,
            },
        }
        return attach_generation_log(
            response_data,
            prompt=request.prompt,
            repair_history=[],
            error_message=str(intent_failure),
            generation_mode="automatic",
        )

    repair_history = []
    direct_model_data = None
    direct_api_started_at = perf_counter()
    try:
        direct_model_data, repair_history = prompt_to_model_data_with_repair(
            request.prompt,
            max_repairs=min(
                max_repair_attempts("direct"),
                max(0, remaining_api_calls - 1),
            ),
        )
        direct_api_seconds = seconds_since(direct_api_started_at)
        response_data = with_repair_history(
            export_model_data(direct_model_data, request.prompt),
            repair_history,
        )
        response_data["generation_mode"] = "automatic"
        response_data["generation_path"] = "direct_fallback"
        response_data["revision"] = 1
        response_data["fallback_reason"] = str(intent_failure)
        response_data["pipeline_attempts"] = [
            intent_attempt,
            {"path": "direct", "status": "success"},
        ]
        if design_intent is not None:
            response_data["design_intent"] = design_intent
        if intent_repair_history:
            response_data["intent_repair_history"] = intent_repair_history

        performance = dict(response_data.get("performance", {}))
        performance.update({
            "api_seconds": combined_seconds(
                intent_api_seconds,
                direct_api_seconds,
            ),
            "intent_api_seconds": intent_api_seconds,
            "direct_api_seconds": direct_api_seconds,
            "lowering_seconds": lowering_seconds,
            "local_processing_seconds": combined_seconds(
                lowering_seconds,
                performance.get("export_model_total_seconds", 0.0),
            ),
            "total_seconds": seconds_since(started_at),
            "cache_hit": False,
        })
        response_data["performance"] = performance
        response_data = attach_generation_log(
            response_data,
            prompt=request.prompt,
            repair_history=repair_history,
            error_message=f"Design-intent path failed: {intent_failure}",
            generation_mode="automatic_direct_fallback",
        )
        cache_success_response(key, response_data)
        return response_data

    except Exception as direct_error:
        direct_api_seconds = seconds_since(direct_api_started_at)
        combined_error = (
            f"Design-intent path failed: {intent_failure}. "
            f"Direct fallback failed: {direct_error}"
        )
        response_data = {
            "status": "error",
            "message": combined_error,
            "design_intent": design_intent,
            "model_data": direct_model_data or intent_model_data,
            "quality_report": (
                check_model_quality(
                    direct_model_data or intent_model_data,
                    build_error=str(direct_error),
                )
                if direct_model_data is not None or intent_model_data is not None
                else check_model_quality(None)
            ),
            "repair_history": repair_history,
            "intent_repair_history": intent_repair_history,
            "generation_mode": "automatic",
            "generation_path": "failed",
            "pipeline_attempts": [
                intent_attempt,
                {
                    "path": "direct",
                    "status": "failed",
                    "message": str(direct_error),
                },
            ],
            "performance": {
                "api_seconds": combined_seconds(
                    intent_api_seconds,
                    direct_api_seconds,
                ),
                "intent_api_seconds": intent_api_seconds,
                "direct_api_seconds": direct_api_seconds,
                "lowering_seconds": lowering_seconds,
                "total_seconds": seconds_since(started_at),
                "cache_hit": False,
            },
        }
        return attach_generation_log(
            response_data,
            prompt=request.prompt,
            repair_history=repair_history,
            error_message=combined_error,
            generation_mode="automatic",
        )


@app.post("/refine")
def refine_cad(request: CADRefineRequest):
    """Apply a focused correction to a previously generated design intent."""
    started_at = perf_counter()
    correction = request.correction.strip()
    revision = max(1, request.revision)
    if not correction:
        return {
            "status": "error",
            "message": "Enter a correction before applying it.",
            "design_intent": request.design_intent,
            "revision": revision,
            "performance": {
                "total_seconds": seconds_since(started_at),
                "cache_hit": False,
            },
        }

    key = cache_key(
        "refine",
        {
            "original_prompt": request.original_prompt,
            "correction": correction,
            "design_intent": request.design_intent,
            "revision": revision,
        },
    )
    cached_response = get_cached_success_response(key)
    if cached_response is not None:
        cached_response["performance"]["total_seconds"] = seconds_since(started_at)
        return cached_response

    design_intent = request.design_intent
    previous_model_data = None
    refined_model_data = None
    revision_summary = None
    refinement_history = []
    refinement_evaluation = None
    refinement_telemetry: dict = {}
    api_started_at = perf_counter()

    try:
        previous_model_data = intent_to_model_data(request.design_intent)
        (
            design_intent,
            refined_model_data,
            refinement_history,
            refinement_evaluation,
        ) = refine_design_intent_with_feedback(
            request.original_prompt,
            request.design_intent,
            correction,
            max_repairs=max_repair_attempts("intent"),
            telemetry=refinement_telemetry,
        )
        api_seconds = seconds_since(api_started_at)

        if not refinement_evaluation.get("passed", False):
            raise ValueError(
                "Refined design-intent candidate failed feedback evaluation: "
                + json.dumps(refinement_evaluation.get("feedback", {}))
            )

        lowering_started_at = perf_counter()
        if refined_model_data is None:
            refined_model_data = intent_to_model_data(design_intent)
        lowering_seconds = seconds_since(lowering_started_at)
        revision_summary = summarize_operation_changes(
            previous_model_data,
            refined_model_data,
        )
        if not revision_summary["has_operation_changes"]:
            raise ValueError(
                "The correction did not change the generated CAD operations. "
                "Try a more specific correction."
            )

        response_data = export_model_data(
            refined_model_data,
            f"revision-{revision + 1} {request.original_prompt}",
        )
        if response_data.get("quality_report", {}).get("status") == "fail":
            raise ValueError("Refined model failed the geometry quality gate")

        response_data["design_intent"] = design_intent
        if refinement_history:
            response_data["intent_repair_history"] = refinement_history
        response_data["generation_mode"] = "automatic_refinement"
        response_data["generation_path"] = "design_intent_refinement"
        response_data["revision"] = revision + 1
        response_data["refinement"] = {
            "from_revision": revision,
            "correction": correction,
        }
        response_data["revision_summary"] = revision_summary
        response_data["pipeline_attempts"] = [
            {
                "path": "design_intent_refinement",
                "status": "success",
            }
        ]
        performance = dict(response_data.get("performance", {}))
        performance.update({
            "api_seconds": refinement_telemetry.get("api_seconds", api_seconds),
            "intent_api_seconds": refinement_telemetry.get(
                "api_seconds",
                api_seconds,
            ),
            "lowering_seconds": lowering_seconds,
            "logical_api_calls": refinement_telemetry.get("logical_api_calls"),
            "total_seconds": seconds_since(started_at),
            "cache_hit": False,
        })
        response_data["performance"] = {
            key: value
            for key, value in performance.items()
            if value is not None
        }
        cache_success_response(key, response_data)
        return response_data

    except Exception as error:
        api_seconds = seconds_since(api_started_at)
        refinement_history = getattr(
            error,
            "intent_repair_history",
            refinement_history,
        )
        return {
            "status": "error",
            "message": str(error),
            "design_intent": design_intent,
            "model_data": refined_model_data,
            "revision_summary": revision_summary,
            "intent_repair_history": refinement_history,
            "generation_mode": "automatic_refinement",
            "generation_path": "design_intent_refinement",
            "revision": revision,
            "refinement": {
                "from_revision": revision,
                "correction": correction,
            },
            "quality_report": (
                check_model_quality(refined_model_data, build_error=str(error))
                if refined_model_data is not None
                else check_model_quality(None)
            ),
            "performance": {
                "api_seconds": refinement_telemetry.get("api_seconds", api_seconds),
                "intent_api_seconds": refinement_telemetry.get(
                    "api_seconds",
                    api_seconds,
                ),
                "logical_api_calls": refinement_telemetry.get(
                    "logical_api_calls"
                ),
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


@app.post("/editable-model")
def editable_model(request: CADEditableModelRequest):
    """Return named editable features and parameters for valid model data."""
    started_at = perf_counter()
    try:
        document = model_data_to_editable_document(request.model_data)
        return {
            "status": "success",
            "editable_model": document.to_dict(),
            "performance": {
                "total_seconds": seconds_since(started_at),
            },
        }
    except Exception as error:
        return {
            "status": "error",
            "message": str(error),
            "editable_model": None,
            "performance": {
                "total_seconds": seconds_since(started_at),
            },
        }


@app.post("/edit-parameters")
def edit_parameters(request: CADParameterEditRequest):
    """Apply named parameter changes and export only a validated rebuild."""
    started_at = perf_counter()
    document = None
    try:
        document = model_data_to_editable_document(request.model_data)
        rebuild_started_at = perf_counter()
        part, updated_document = rebuild_with_parameter_updates(
            document,
            request.updates,
        )
        rebuild_seconds = seconds_since(rebuild_started_at)
        response_data = export_model_data(
            updated_document.source_model_data,
            request.filename_hint,
            built_part=part,
        )
        response_data["editable_model"] = updated_document.to_dict()
        performance = dict(response_data.get("performance", {}))
        performance.update({
            "editable_rebuild_seconds": rebuild_seconds,
            "total_seconds": seconds_since(started_at),
        })
        response_data["performance"] = performance
        return response_data
    except Exception as error:
        return {
            "status": "error",
            "message": str(error),
            "model_data": request.model_data,
            "editable_model": document.to_dict() if document is not None else None,
            "edit_rejected": True,
            "performance": {
                "total_seconds": seconds_since(started_at),
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
