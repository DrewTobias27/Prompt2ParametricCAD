"""Benchmark first-pass and production design-intent CAD generation.

The default compares an unrepaired first pass with the geometry-aware feedback
loop. Direct CAD JSON remains available only for explicit fallback diagnostics.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import time
from typing import Any
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.request import Request
from urllib.request import urlopen

from prompt2cad.concept_evaluator import evaluate_model_concepts
from prompt2cad.design_intent import intent_to_model_data
from prompt2cad.design_intent import missing_required_intent_dimensions
from prompt2cad.evaluator import evaluate_model_data as evaluate_against_case
from prompt2cad.intent_evaluator import evaluate_design_intent
from prompt2cad.interpreter import build_model
from prompt2cad.intent_coverage import intent_coverage_failures
from prompt2cad.intent_alignment import evaluate_intent_alignment
from prompt2cad.operation_effects import evaluate_operation_effects
from prompt2cad.prompting import prompt_to_design_intent
from prompt2cad.prompting import prompt_to_design_intent_with_feedback
from prompt2cad.prompting import prompt_to_model_data
from prompt2cad.quality import check_model_quality
from prompt2cad.schema import validate_model_data


DEFAULT_PROMPTS = [
    (
        "Create a 100 mm by 70 mm rectangular mounting plate, 8 mm thick, "
        "with four 6 mm through holes near the corners and a centered "
        "30 mm diameter raised circular boss with a 12 mm through hole."
    ),
    (
        "Create a 90 mm by 55 mm rectangular block, 10 mm thick, with a "
        "28 mm by 20 mm raised rectangular boss centered on the top face, "
        "an 8 mm through hole through that boss, and a 24 mm by 5 mm blind "
        "rectangular slot cut from the right side."
    ),
]

DEFAULT_EVAL_CASES = [
    "circular_flange_six_bolt_holes",
    "rectangular_block_front_hole_top_boss",
    "rigorous_plate_holes_boss",
]

CANONICAL_TIMING_STAGES = [
    "api_seconds",
    "intent_checks_seconds",
    "lowering_seconds",
    "alignment_seconds",
    "validation_seconds",
    "build_seconds",
    "quality_seconds",
    "operation_effects_seconds",
    "pipeline_overhead_seconds",
]

API_USAGE_FIELDS = [
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "total_tokens",
]


def elapsed_seconds(started_at: float) -> float:
    """Return a stable, report-friendly elapsed time."""
    return round(time.perf_counter() - started_at, 3)


@contextmanager
def record_timing(performance: dict[str, float], stage: str):
    """Record one stage even when the measured operation raises."""
    started_at = time.perf_counter()
    try:
        yield
    finally:
        performance[stage] = elapsed_seconds(started_at)


def attach_error_performance(
    error: Exception,
    performance: dict[str, float],
    started_at: float,
) -> None:
    """Preserve completed stage timings on a failed generation attempt."""
    existing = getattr(error, "performance", {})
    error.performance = {
        **existing,
        **performance,
        "total_seconds": elapsed_seconds(started_at),
    }


def finalize_performance(
    performance: dict[str, float],
    total_seconds: float,
) -> dict[str, float]:
    """Attach total and otherwise-unmeasured orchestration time."""
    result = dict(performance)
    measured_seconds = sum(
        float(result.get(stage, 0.0))
        for stage in CANONICAL_TIMING_STAGES
        if stage != "pipeline_overhead_seconds"
    )
    result["total_seconds"] = total_seconds
    result["pipeline_overhead_seconds"] = round(
        max(0.0, total_seconds - measured_seconds),
        3,
    )
    return result


def safe_case_name(value: Any) -> str:
    """Return a stable filesystem-friendly case name."""
    text = str(value).strip().lower()
    safe = "".join(character if character.isalnum() else "_" for character in text)
    safe = "_".join(part for part in safe.split("_") if part)
    return safe or "case"


def error_details(error: Exception) -> dict[str, Any]:
    """Return useful error details without including secrets."""
    details = {
        "error_type": type(error).__name__,
        "message": str(error),
    }
    cause = error.__cause__ or error.__context__
    if cause is not None:
        details["cause_type"] = type(cause).__name__
        details["cause"] = str(cause)
    for attribute in [
        "design_intent",
        "intent_missing_required_dimensions",
        "model_data",
        "performance",
        "api_telemetry",
    ]:
        if hasattr(error, attribute):
            details[attribute] = getattr(error, attribute)
    return details


def check_openai_connection(timeout_seconds: int = 10) -> dict[str, Any]:
    """Check API reachability without running a model-generation request."""
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return {
            "passed": False,
            "reason": "OPENAI_API_KEY is not set in this terminal session.",
        }

    request = Request(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return {
                "passed": 200 <= response.status < 300,
                "status_code": response.status,
                "reason": response.reason,
            }
    except HTTPError as error:
        return {
            "passed": False,
            "status_code": error.code,
            "reason": error.reason,
            "error_type": type(error).__name__,
            "message": str(error),
        }
    except URLError as error:
        return {
            "passed": False,
            "error_type": type(error).__name__,
            "message": str(error),
            "reason": getattr(error, "reason", None),
        }


def evaluate_model_data(
    model_data: dict[str, Any],
    *,
    include_operation_effects: bool = True,
) -> dict[str, Any]:
    """Validate, build, and quality-check generated model data."""
    started_at = time.perf_counter()
    performance: dict[str, float] = {}
    try:
        with record_timing(performance, "validation_seconds"):
            validate_model_data(model_data)
        with record_timing(performance, "build_seconds"):
            part = build_model(model_data)
        with record_timing(performance, "quality_seconds"):
            quality_report = check_model_quality(
                model_data,
                build_succeeded=True,
                built_part=part,
            )
        result = {
            "build_succeeded": True,
            "quality_passed": quality_report.get("passed", False),
            "quality_report": quality_report,
        }
        if include_operation_effects:
            with record_timing(performance, "operation_effects_seconds"):
                operation_effects = evaluate_operation_effects(model_data)
            result.update({
                "operation_effects_passed": operation_effects["passed"],
                "operation_effect_failures": operation_effects["failures"],
                "operation_effect_warnings": operation_effects["warnings"],
                "operation_trace": operation_effects["trace"],
            })
        performance["evaluation_total_seconds"] = elapsed_seconds(started_at)
        result["performance"] = performance
        return result
    except Exception as error:
        attach_error_performance(error, performance, started_at)
        raise


def load_json(path: Path) -> dict[str, Any]:
    """Load JSON from disk."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(data: dict[str, Any], path: Path) -> None:
    """Save readable JSON to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
        file.write("\n")


def prompt_cases_from_prompts(prompts: list[str]) -> list[dict[str, Any]]:
    """Convert plain prompt strings into named comparison cases."""
    return [
        {
            "case": str(index),
            "prompt": prompt,
        }
        for index, prompt in enumerate(prompts, start=1)
    ]


def load_prompt_cases(path: Path) -> list[dict[str, Any]]:
    """Load exploratory prompt cases from a JSON file."""
    data = load_json(path)
    raw_cases = data["cases"] if isinstance(data, dict) else data
    cases = []

    for index, raw_case in enumerate(raw_cases, start=1):
        if isinstance(raw_case, str):
            cases.append({
                "case": str(index),
                "prompt": raw_case,
            })
            continue

        name = raw_case.get("name", str(index))
        cases.append({
            "case": name,
            "prompt": raw_case["prompt"],
            **{
                key: value
                for key, value in raw_case.items()
                if key not in {"name", "prompt"}
            },
        })

    return cases


def filter_prompt_cases(
    prompt_cases: list[dict[str, Any]],
    requested_case_names: list[str],
) -> list[dict[str, Any]]:
    """Return only requested prompt cases when a filter is supplied."""
    if not requested_case_names:
        return prompt_cases

    requested = set(requested_case_names)
    return [
        prompt_case
        for prompt_case in prompt_cases
        if str(prompt_case["case"]) in requested
    ]


def evaluate_model_against_case(
    model_data: dict[str, Any],
    eval_case: dict[str, Any],
) -> dict[str, Any]:
    """Run the existing case-specific evaluator against generated model data."""
    part = build_model(model_data)
    result = evaluate_against_case(model_data, eval_case, part)
    return {
        "eval_passed": result.passed,
        "eval_failures": result.failures,
    }


def run_direct(prompt: str) -> dict[str, Any]:
    """Generate final model JSON directly from the prompt."""
    started_at = time.perf_counter()
    performance: dict[str, float] = {}
    api_telemetry: dict[str, Any] = {}
    try:
        with record_timing(performance, "api_seconds"):
            model_data = prompt_to_model_data(prompt, telemetry=api_telemetry)
        evaluation = evaluate_model_data(model_data)
        performance.update(evaluation.pop("performance", {}))
        performance["total_seconds"] = elapsed_seconds(started_at)
        return {
            "model_data": model_data,
            "api_telemetry": api_telemetry,
            **evaluation,
            "performance": performance,
        }
    except Exception as error:
        error.api_telemetry = api_telemetry
        attach_error_performance(error, performance, started_at)
        raise


def run_intent(prompt: str) -> dict[str, Any]:
    """Generate design intent, then lower it deterministically to model JSON."""
    started_at = time.perf_counter()
    performance: dict[str, float] = {}
    api_telemetry: dict[str, Any] = {}
    try:
        with record_timing(performance, "api_seconds"):
            design_intent = prompt_to_design_intent(
                prompt,
                telemetry=api_telemetry,
            )
        with record_timing(performance, "intent_checks_seconds"):
            coverage_failures = intent_coverage_failures(design_intent)
            missing_dimensions = missing_required_intent_dimensions(design_intent)
        with record_timing(performance, "lowering_seconds"):
            model_data = intent_to_model_data(design_intent)
        with record_timing(performance, "alignment_seconds"):
            intent_alignment = evaluate_intent_alignment(design_intent, model_data)
        evaluation = evaluate_model_data(model_data)
        performance.update(evaluation.pop("performance", {}))
        performance["total_seconds"] = elapsed_seconds(started_at)
    except Exception as error:
        if "design_intent" in locals():
            error.design_intent = design_intent
        if "missing_dimensions" in locals():
            error.intent_missing_required_dimensions = missing_dimensions
        if "model_data" in locals():
            error.model_data = model_data
        error.api_telemetry = api_telemetry
        attach_error_performance(error, performance, started_at)
        raise
    return {
        "design_intent": design_intent,
        "api_telemetry": api_telemetry,
        "intent_coverage_passed": not coverage_failures,
        "intent_coverage_failures": coverage_failures,
        "intent_missing_required_dimensions": missing_dimensions,
        "intent_alignment_passed": intent_alignment["passed"],
        "intent_alignment_failures": intent_alignment["failures"],
        "model_data": model_data,
        **evaluation,
        "performance": performance,
    }


def run_intent_feedback(prompt: str) -> dict[str, Any]:
    """Run the production intent path, including bounded geometry feedback."""
    started_at = time.perf_counter()
    performance: dict[str, float] = {}
    api_telemetry: dict[str, Any] = {}
    try:
        with record_timing(performance, "api_seconds"):
            (
                design_intent,
                model_data,
                repair_history,
                candidate_evaluation,
            ) = prompt_to_design_intent_with_feedback(
                prompt,
                telemetry=api_telemetry,
            )
        if model_data is None:
            raise ValueError(
                "The design-intent feedback loop did not produce CAD model data"
            )
        with record_timing(performance, "intent_checks_seconds"):
            coverage_failures = intent_coverage_failures(design_intent)
            missing_dimensions = missing_required_intent_dimensions(design_intent)
        with record_timing(performance, "alignment_seconds"):
            intent_alignment = evaluate_intent_alignment(design_intent, model_data)
        evaluation = evaluate_model_data(model_data)
        performance.update(evaluation.pop("performance", {}))
        performance["total_seconds"] = elapsed_seconds(started_at)
    except Exception as error:
        if "design_intent" in locals():
            error.design_intent = design_intent
        if "missing_dimensions" in locals():
            error.intent_missing_required_dimensions = missing_dimensions
        if "model_data" in locals():
            error.model_data = model_data
        error.api_telemetry = api_telemetry
        attach_error_performance(error, performance, started_at)
        raise

    first_pass_intent = (
        repair_history[0]["failed_design_intent"]
        if repair_history
        else design_intent
    )
    first_call_telemetry = (
        api_telemetry.get("calls", [{}])[0]
        if api_telemetry.get("calls")
        else {}
    )
    first_pass_result = evaluate_existing_intent(
        first_pass_intent,
        api_telemetry={
            **first_call_telemetry,
            "logical_api_calls": 1,
        },
    )

    return {
        "design_intent": design_intent,
        "api_telemetry": api_telemetry,
        "repair_count": len(repair_history),
        "recovered_after_feedback": bool(repair_history),
        "intent_repair_history": repair_history,
        "candidate_evaluation": candidate_evaluation,
        "first_pass_result": first_pass_result,
        "intent_coverage_passed": not coverage_failures,
        "intent_coverage_failures": coverage_failures,
        "intent_missing_required_dimensions": missing_dimensions,
        "intent_alignment_passed": intent_alignment["passed"],
        "intent_alignment_failures": intent_alignment["failures"],
        "model_data": model_data,
        **evaluation,
        "performance": performance,
    }


def evaluate_existing_intent(
    design_intent: dict[str, Any],
    *,
    api_telemetry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply all local checks to an already-generated design intent."""
    result: dict[str, Any] = {
        "mode": "intent",
        "design_intent": design_intent,
        "api_telemetry": api_telemetry or {},
    }
    try:
        coverage_failures = intent_coverage_failures(design_intent)
        missing_dimensions = missing_required_intent_dimensions(design_intent)
        model_data = intent_to_model_data(design_intent)
        intent_alignment = evaluate_intent_alignment(design_intent, model_data)
        result.update({
            "intent_coverage_passed": not coverage_failures,
            "intent_coverage_failures": coverage_failures,
            "intent_missing_required_dimensions": missing_dimensions,
            "intent_alignment_passed": intent_alignment["passed"],
            "intent_alignment_failures": intent_alignment["failures"],
            "model_data": model_data,
            **evaluate_model_data(model_data),
        })
        result["status"] = status_for_result(result)
    except Exception as error:  # Keep failed first-pass evidence in the report.
        result.update(error_details(error))
        result["status"] = "fail"
    result["elapsed_seconds"] = round(
        float(result["api_telemetry"].get("api_seconds", 0.0)),
        2,
    )
    return result


def run_case(prompt: str, mode: str) -> dict[str, Any]:
    """Run one prompt through one API path and return a compact result."""
    started_at = time.perf_counter()
    try:
        if mode == "direct":
            result = run_direct(prompt)
        elif mode == "intent":
            result = run_intent(prompt)
        elif mode == "intent_feedback":
            result = run_intent_feedback(prompt)
        else:
            raise ValueError(f"Unsupported mode: {mode}")
        total_seconds = elapsed_seconds(started_at)
        performance = finalize_performance(
            result.get("performance", {}),
            total_seconds,
        )
        return {
            "mode": mode,
            "status": status_for_result(result),
            "elapsed_seconds": round(total_seconds, 2),
            **result,
            "performance": performance,
        }
    except Exception as error:  # noqa: BLE001 - command-line report should capture any failure.
        total_seconds = elapsed_seconds(started_at)
        details = error_details(error)
        if mode == "intent_feedback" and isinstance(
            details.get("design_intent"),
            dict,
        ):
            aggregate_telemetry = details.get("api_telemetry", {})
            first_call = (
                aggregate_telemetry.get("calls", [{}])[0]
                if aggregate_telemetry.get("calls")
                else aggregate_telemetry
            )
            details["first_pass_result"] = evaluate_existing_intent(
                details["design_intent"],
                api_telemetry={**first_call, "logical_api_calls": 1},
            )
        performance = finalize_performance(
            details.get("performance", {}),
            total_seconds,
        )
        return {
            "mode": mode,
            "status": "fail",
            "elapsed_seconds": round(total_seconds, 2),
            **details,
            "performance": performance,
        }


def iter_report_results(report: dict[str, Any]):
    """Yield each case/result pair in a comparison report."""
    for case in report.get("cases", []):
        for result in case.get("results", []):
            yield case, result


def attach_report_summary(report: dict[str, Any]) -> dict[str, Any]:
    """Attach pass/fail counts and timing summaries to a report."""
    results = list(iter_report_results(report))
    status_counts = {"pass": 0, "warn": 0, "fail": 0}
    mode_counts: dict[str, int] = {}
    timed_results = []
    stage_samples: dict[str, list[float]] = {
        stage: [] for stage in CANONICAL_TIMING_STAGES
    }
    usage_samples: dict[str, list[int]] = {
        field: [] for field in API_USAGE_FIELDS
    }

    for case, result in results:
        status = result.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

        mode = result.get("mode", "unknown")
        mode_counts[mode] = mode_counts.get(mode, 0) + 1

        if "elapsed_seconds" in result:
            timed_results.append({
                "case": case.get("case"),
                "mode": mode,
                "status": status,
                "elapsed_seconds": float(result["elapsed_seconds"]),
            })

        performance = result.get("performance", {})
        for stage in CANONICAL_TIMING_STAGES:
            value = performance.get(stage)
            if isinstance(value, (int, float)):
                stage_samples[stage].append(float(value))

        api_telemetry = result.get("api_telemetry", {})
        for field in API_USAGE_FIELDS:
            value = api_telemetry.get(field)
            if isinstance(value, (int, float)):
                usage_samples[field].append(int(value))

    total_elapsed_seconds = round(
        sum(result["elapsed_seconds"] for result in timed_results),
        2,
    )
    average_elapsed_seconds = (
        round(total_elapsed_seconds / len(timed_results), 2)
        if timed_results
        else 0
    )
    slowest_results = sorted(
        timed_results,
        key=lambda result: result["elapsed_seconds"],
        reverse=True,
    )[:3]
    performance_totals = {
        stage: round(sum(samples), 3)
        for stage, samples in stage_samples.items()
        if samples
    }
    performance_averages = {
        stage: round(sum(samples) / len(samples), 3)
        for stage, samples in stage_samples.items()
        if samples
    }
    dominant_stage = (
        max(performance_totals, key=performance_totals.get)
        if performance_totals
        else None
    )

    report["summary"] = {
        "case_count": len(report.get("cases", [])),
        "result_count": len(results),
        "status_counts": status_counts,
        "mode_counts": mode_counts,
        "total_elapsed_seconds": total_elapsed_seconds,
        "average_elapsed_seconds": average_elapsed_seconds,
        "slowest_results": slowest_results,
        "performance_totals": performance_totals,
        "performance_averages": performance_averages,
        "performance_sample_counts": {
            stage: len(samples)
            for stage, samples in stage_samples.items()
            if samples
        },
        "dominant_stage": dominant_stage,
        "api_usage_totals": {
            field: sum(samples)
            for field, samples in usage_samples.items()
            if samples
        },
        "api_usage_averages": {
            field: round(sum(samples) / len(samples), 1)
            for field, samples in usage_samples.items()
            if samples
        },
    }
    return report


def status_for_result(result: dict[str, Any]) -> str:
    """Return pass/warn status for a successful generation result."""
    status = "pass" if result.get("build_succeeded") and result.get("quality_passed") else "warn"
    if result.get("intent_missing_required_dimensions"):
        status = "warn"
    if result.get("eval_passed") is False:
        status = "warn"
    if result.get("concept_passed") is False:
        status = "warn"
    if result.get("intent_eval_passed") is False:
        status = "warn"
    if result.get("intent_coverage_passed") is False:
        status = "warn"
    if result.get("intent_alignment_passed") is False:
        status = "warn"
    if result.get("operation_effects_passed") is False:
        status = "warn"
    if result.get("operation_effect_warnings"):
        status = "warn"
    return status


def attach_eval_result(
    result: dict[str, Any],
    *,
    eval_case: dict[str, Any] | None,
    model_output_path: Path | None,
) -> dict[str, Any]:
    """Attach saved model path and eval-case result when available."""
    first_pass_result = result.get("first_pass_result")
    if isinstance(first_pass_result, dict):
        attach_eval_result(
            first_pass_result,
            eval_case=eval_case,
            model_output_path=None,
        )

    model_data = result.get("model_data")
    if model_data is None:
        return result

    if model_output_path is not None:
        save_json(model_data, model_output_path)
        result["model_output_path"] = str(model_output_path)

    if eval_case is not None:
        try:
            eval_result = evaluate_model_against_case(model_data, eval_case)
            result.update(eval_result)
            if not eval_result["eval_passed"] and result["status"] == "pass":
                result["status"] = "warn"
        except Exception as error:  # noqa: BLE001 - eval report should capture any failure.
            result.update({
                "eval_passed": False,
                "eval_failures": [str(error)],
                "eval_error": error_details(error),
            })
            if result["status"] == "pass":
                result["status"] = "warn"

    return result


def attach_prompt_case_expectations(
    result: dict[str, Any],
    prompt_case: dict[str, Any],
) -> dict[str, Any]:
    """Attach exploratory prompt-case concept and intent evaluations."""
    first_pass_result = result.get("first_pass_result")
    if isinstance(first_pass_result, dict):
        attach_prompt_case_expectations(first_pass_result, prompt_case)

    expected_concepts = prompt_case.get("expected_concepts")
    model_data = result.get("model_data")
    if expected_concepts is not None and model_data is not None:
        try:
            geometry_summary = (
                result.get("quality_report", {})
                .get("geometry_summary")
            )
            concept_result = evaluate_model_concepts(
                model_data,
                expected_concepts,
                geometry_summary=geometry_summary,
            )
            result["concept_passed"] = concept_result.passed
            result["concept_failures"] = concept_result.failures
        except Exception as error:  # noqa: BLE001 - preserve API output on evaluator bugs.
            result["concept_passed"] = False
            result["concept_failures"] = [
                f"Concept evaluator failed: {error}"
            ]
            result["concept_error"] = error_details(error)
        if not result["concept_passed"] and result["status"] == "pass":
            result["status"] = "warn"

    expected_intent = prompt_case.get("expected_intent")
    design_intent = result.get("design_intent")
    if expected_intent is not None and design_intent is not None:
        try:
            intent_result = evaluate_design_intent(
                design_intent,
                {
                    "name": prompt_case["case"],
                    "expected_intent": expected_intent,
                },
            )
            result["intent_eval_passed"] = intent_result.passed
            result["intent_eval_failures"] = intent_result.failures
        except Exception as error:  # noqa: BLE001 - preserve API output on evaluator bugs.
            result["intent_eval_passed"] = False
            result["intent_eval_failures"] = [
                f"Intent evaluator failed: {error}"
            ]
            result["intent_eval_error"] = error_details(error)
        if not result["intent_eval_passed"] and result["status"] == "pass":
            result["status"] = "warn"

    return result


def rescore_report(
    report_path: Path,
    *,
    output_path: Path,
    prompt_cases: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Recompute local checks for an existing API report without API calls."""
    report = load_json(report_path)
    prompt_case_lookup = {
        str(prompt_case["case"]): prompt_case
        for prompt_case in (prompt_cases or [])
    }

    for case in report.get("cases", []):
        prompt_case = {
            **case,
            **prompt_case_lookup.get(str(case.get("case")), {}),
        }
        for result in case.get("results", []):
            rescore_started_at = time.perf_counter()
            model_data = result.get("model_data")
            if result.get("design_intent") is not None:
                try:
                    design_intent = result["design_intent"]
                    coverage_failures = intent_coverage_failures(design_intent)
                    result["intent_coverage_passed"] = not coverage_failures
                    result["intent_coverage_failures"] = coverage_failures
                    result["intent_missing_required_dimensions"] = (
                        missing_required_intent_dimensions(design_intent)
                    )
                    model_data = intent_to_model_data(design_intent)
                    result["model_data"] = model_data
                    intent_alignment = evaluate_intent_alignment(
                        design_intent,
                        model_data,
                    )
                    result["intent_alignment_passed"] = intent_alignment["passed"]
                    result["intent_alignment_failures"] = intent_alignment["failures"]
                except Exception as error:  # noqa: BLE001 - report should capture failures.
                    result.update(error_details(error))
                    result["status"] = "fail"
                    attach_rescore_performance(result, rescore_started_at)
                    continue

            if model_data is not None:
                try:
                    local_result = evaluate_model_data(model_data)
                    result.update(local_result)
                    clear_error_details(result)
                except Exception as error:  # noqa: BLE001 - report should capture failures.
                    result.update(error_details(error))
                    result["status"] = "fail"
                    attach_rescore_performance(result, rescore_started_at)
                    continue

            attach_prompt_case_expectations(result, prompt_case)
            if model_data is not None:
                result["status"] = status_for_result(result)
            attach_rescore_performance(result, rescore_started_at)

    report["rescored_from"] = str(report_path)
    report["api_call_budget"] = 0
    attach_report_summary(report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def attach_rescore_performance(
    result: dict[str, Any],
    started_at: float,
) -> None:
    """Keep original API duration separate from new local rescore timing."""
    if "elapsed_seconds" in result and "original_elapsed_seconds" not in result:
        result["original_elapsed_seconds"] = result["elapsed_seconds"]

    total_seconds = elapsed_seconds(started_at)
    result["elapsed_seconds"] = round(total_seconds, 2)
    result["performance"] = finalize_performance(
        result.get("performance", {}),
        total_seconds,
    )


def clear_error_details(result: dict[str, Any]) -> None:
    """Remove stale error fields after a saved result successfully re-scores."""
    for key in ["error_type", "message", "cause_type", "cause"]:
        result.pop(key, None)


def compare_prompts(
    prompts: list[str],
    *,
    output_path: Path,
    skip_preflight: bool = False,
    modes: list[str] | None = None,
) -> dict[str, Any]:
    """Run a tiny comparison and save the full report."""
    return compare_prompt_cases(
        prompt_cases_from_prompts(prompts),
        output_path=output_path,
        skip_preflight=skip_preflight,
        modes=modes,
    )


def compare_prompt_cases(
    prompt_cases: list[dict[str, Any]],
    *,
    output_path: Path,
    skip_preflight: bool = False,
    modes: list[str] | None = None,
) -> dict[str, Any]:
    """Run cases through the selected generation paths."""
    modes = modes or ["intent_feedback"]
    report = {
        "api_call_budget": len(prompt_cases) * len(modes),
        "modes": modes,
        "configured_model": os.getenv("PROMPT2CAD_OPENAI_MODEL"),
        "preflight": None,
        "cases": [],
    }

    if not skip_preflight:
        preflight = check_openai_connection()
        report["preflight"] = preflight
        if not preflight["passed"]:
            attach_report_summary(report)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            return report

    models_dir = output_path.parent / "models"
    for prompt_case in prompt_cases:
        case_name = str(prompt_case["case"])
        prompt = prompt_case["prompt"]
        results = []

        for mode in modes:
            result = run_case(prompt, mode)
            model_output_path = models_dir / mode / f"{safe_case_name(case_name)}.json"
            result = attach_eval_result(
                result,
                eval_case=None,
                model_output_path=model_output_path,
            )
            results.append(
                attach_prompt_case_expectations(
                    result,
                    {
                        **prompt_case,
                        "case": case_name,
                    },
                )
            )

        case_result = {
            **prompt_case,
            "case": case_name,
            "prompt": prompt,
            "results": results,
        }
        report["cases"].append(case_result)
        write_report_checkpoint(report, output_path)

    attach_report_summary(report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def compare_eval_cases(
    case_names: list[str],
    *,
    cases_dir: Path,
    output_path: Path,
    skip_preflight: bool = False,
    modes: list[str] | None = None,
) -> dict[str, Any]:
    """Run API generation paths against existing evaluator case files."""
    modes = modes or ["intent_feedback"]
    report = {
        "api_call_budget": len(case_names) * len(modes),
        "modes": modes,
        "configured_model": os.getenv("PROMPT2CAD_OPENAI_MODEL"),
        "cases_dir": str(cases_dir),
        "preflight": None,
        "cases": [],
    }

    if not skip_preflight:
        preflight = check_openai_connection()
        report["preflight"] = preflight
        if not preflight["passed"]:
            attach_report_summary(report)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            return report

    models_dir = output_path.parent / "models"
    for case_name in case_names:
        case_path = cases_dir / f"{case_name}.json"
        eval_case = load_json(case_path)
        prompt = eval_case["prompt"]
        results = []

        for mode in modes:
            result = run_case(prompt, mode)
            model_output_path = models_dir / mode / f"{case_name}.json"
            results.append(
                attach_eval_result(
                    result,
                    eval_case=eval_case,
                    model_output_path=model_output_path,
                )
            )

        report["cases"].append({
            "case": case_name,
            "prompt": prompt,
            "case_path": str(case_path),
            "results": results,
        })
        write_report_checkpoint(report, output_path)

    attach_report_summary(report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def write_report_checkpoint(
    report: dict[str, Any],
    output_path: Path,
) -> None:
    """Persist completed cases so an interrupted batch does not lose API work."""
    attach_report_summary(report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def print_summary(report: dict[str, Any], output_path: Path) -> None:
    """Print a compact terminal summary of the comparison."""
    print(f"WROTE {output_path}")
    preflight = report.get("preflight")
    if preflight and not preflight["passed"]:
        print("PREFLIGHT FAIL")
        print(f"  {preflight}")
        print("API calls used: 0")
        return

    print(f"API calls used: {report['api_call_budget']}")
    summary = report.get("summary", {})
    if summary:
        status_counts = summary.get("status_counts", {})
        print(
            "RESULTS "
            f"pass={status_counts.get('pass', 0)} "
            f"warn={status_counts.get('warn', 0)} "
            f"fail={status_counts.get('fail', 0)} "
            f"avg={summary.get('average_elapsed_seconds', 0)}s "
            f"total={summary.get('total_elapsed_seconds', 0)}s"
        )
        slowest_results = summary.get("slowest_results", [])
        if slowest_results:
            slowest = ", ".join(
                f"{result['case']}:{result['mode']}="
                f"{result['elapsed_seconds']}s"
                for result in slowest_results
            )
            print(f"SLOWEST {slowest}")
        performance_averages = summary.get("performance_averages", {})
        if performance_averages:
            stage_text = " ".join(
                f"{timing_stage_label(stage)}={value}s"
                for stage, value in performance_averages.items()
            )
            print(f"AVERAGE STAGES {stage_text}")
        usage_averages = summary.get("api_usage_averages", {})
        if usage_averages:
            usage_text = " ".join(
                f"{api_usage_label(field)}={value}"
                for field, value in usage_averages.items()
            )
            print(f"AVERAGE API TOKENS {usage_text}")

    for case in report["cases"]:
        print(f"CASE {case['case']}: {case['prompt'][:90]}")
        for result in case["results"]:
            detail = result.get("message", "")
            if result.get("cause"):
                detail = f"{detail} Cause: {result['cause']}"
            if not detail:
                detail = (
                    f"quality_passed={result.get('quality_passed')} "
                    f"eval_passed={result.get('eval_passed', 'n/a')}"
                )
            if result.get("intent_missing_required_dimensions"):
                detail = (
                    f"{detail} "
                    "intent_missing_required_dimensions="
                    f"{len(result['intent_missing_required_dimensions'])}"
                )
            if result.get("eval_failures"):
                detail = f"{detail} eval_failures={len(result['eval_failures'])}"
            if result.get("concept_failures"):
                detail = f"{detail} concept_failures={len(result['concept_failures'])}"
            if result.get("intent_eval_failures"):
                detail = (
                    f"{detail} "
                    f"intent_eval_failures={len(result['intent_eval_failures'])}"
                )
            if result.get("intent_coverage_failures"):
                detail = (
                    f"{detail} "
                    f"intent_coverage_failures="
                    f"{len(result['intent_coverage_failures'])}"
                )
            if result.get("intent_alignment_failures"):
                detail = (
                    f"{detail} intent_alignment_failures="
                    f"{len(result['intent_alignment_failures'])}"
                )
            if result.get("operation_effect_failures"):
                detail = (
                    f"{detail} operation_effect_failures="
                    f"{len(result['operation_effect_failures'])}"
                )
            if result.get("operation_effect_warnings"):
                detail = (
                    f"{detail} operation_effect_warnings="
                    f"{len(result['operation_effect_warnings'])}"
                )
            print(
                f"  {result['status'].upper()} {result['mode']} "
                f"{result['elapsed_seconds']}s {detail}"
            )
            performance = result.get("performance", {})
            stage_text = " ".join(
                f"{timing_stage_label(stage)}={performance[stage]}s"
                for stage in CANONICAL_TIMING_STAGES
                if stage in performance
            )
            if stage_text:
                print(f"    TIMING {stage_text}")
            api_telemetry = result.get("api_telemetry", {})
            if api_telemetry:
                model = api_telemetry.get("response_model") or api_telemetry.get(
                    "requested_model",
                    "unknown",
                )
                usage_text = " ".join(
                    f"{api_usage_label(field)}={api_telemetry[field]}"
                    for field in API_USAGE_FIELDS
                    if field in api_telemetry
                )
                print(f"    API model={model} {usage_text}".rstrip())


def timing_stage_label(stage: str) -> str:
    """Return compact terminal labels for timing-stage keys."""
    return {
        "api_seconds": "api",
        "intent_checks_seconds": "intent_checks",
        "lowering_seconds": "lowering",
        "alignment_seconds": "alignment",
        "validation_seconds": "validation",
        "build_seconds": "build",
        "quality_seconds": "quality",
        "operation_effects_seconds": "op_effects",
        "pipeline_overhead_seconds": "overhead",
    }.get(stage, stage.removesuffix("_seconds"))


def api_usage_label(field: str) -> str:
    """Return compact terminal labels for API usage fields."""
    return {
        "input_tokens": "input",
        "cached_input_tokens": "cached",
        "output_tokens": "output",
        "reasoning_tokens": "reasoning",
        "total_tokens": "total",
    }[field]


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark CAD intent with optional production geometry feedback."
        )
    )
    parser.add_argument(
        "--prompt",
        action="append",
        default=[],
        help="Prompt to test. Omit to use two small default engineering prompts.",
    )
    parser.add_argument(
        "--prompt-file",
        type=Path,
        help=(
            "JSON file containing exploratory prompt cases. Supports either "
            "an array of prompt strings/objects or an object with a cases array."
        ),
    )
    parser.add_argument(
        "--prompt-case",
        action="append",
        default=[],
        help=(
            "Run only a named case from --prompt-file. May be passed more "
            "than once."
        ),
    )
    parser.add_argument(
        "--eval-case",
        action="append",
        default=[],
        help=(
            "Existing eval case to test by filename without .json. "
            "When supplied, the generated model is checked by that eval case."
        ),
    )
    parser.add_argument(
        "--hard-eval-suite",
        action="store_true",
        help=(
            "Run a small harder suite of existing eval cases. "
            f"Defaults to: {', '.join(DEFAULT_EVAL_CASES)}."
        ),
    )
    parser.add_argument(
        "--cases-dir",
        type=Path,
        default=Path("evals/cases"),
        help="Folder containing eval case JSON files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("generated/tiny_api_compare/report.json"),
        help="Where to write the full JSON report.",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip the no-token API reachability check before generation.",
    )
    parser.add_argument(
        "--model",
        help=(
            "OpenAI model for this benchmark run. Sets only the current "
            "process, so production configuration is unchanged."
        ),
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=["none", "minimal", "low", "medium", "high", "xhigh", "max"],
        help=(
            "Optional reasoning effort for this benchmark. Omit to preserve "
            "the production default. Start with low for a latency comparison."
        ),
    )
    parser.add_argument(
        "--mode",
        action="append",
        choices=["direct", "intent", "intent_feedback"],
        help=(
            "Generation path to run. Omit to run the production feedback loop, "
            "which records its exact first-pass candidate for paired scoring. "
            "Direct is retained only for explicit fallback diagnostics."
        ),
    )
    parser.add_argument(
        "--rescore-report",
        type=Path,
        help=(
            "Recompute local quality/concept checks for an existing report "
            "without making API calls."
        ),
    )
    return parser.parse_args()


def main() -> None:
    """Run the tiny comparison from the command line."""
    args = parse_args()
    if args.model is not None:
        os.environ["PROMPT2CAD_OPENAI_MODEL"] = args.model
    if args.reasoning_effort is not None:
        os.environ["PROMPT2CAD_REASONING_EFFORT"] = args.reasoning_effort
    if args.rescore_report is not None:
        prompt_cases = (
            filter_prompt_cases(load_prompt_cases(args.prompt_file), args.prompt_case)
            if args.prompt_file is not None
            else None
        )
        report = rescore_report(
            args.rescore_report,
            output_path=args.output,
            prompt_cases=prompt_cases,
        )
        print_summary(report, args.output)
        return

    eval_cases = args.eval_case or (DEFAULT_EVAL_CASES if args.hard_eval_suite else [])
    if eval_cases:
        report = compare_eval_cases(
            eval_cases,
            cases_dir=args.cases_dir,
            output_path=args.output,
            skip_preflight=args.skip_preflight,
            modes=args.mode,
        )
        print_summary(report, args.output)
        return

    if args.prompt_file is not None:
        report = compare_prompt_cases(
            filter_prompt_cases(
                load_prompt_cases(args.prompt_file),
                args.prompt_case,
            ),
            output_path=args.output,
            skip_preflight=args.skip_preflight,
            modes=args.mode,
        )
        print_summary(report, args.output)
        return

    prompts = args.prompt or DEFAULT_PROMPTS
    report = compare_prompts(
        prompts,
        output_path=args.output,
        skip_preflight=args.skip_preflight,
        modes=args.mode,
    )
    print_summary(report, args.output)


if __name__ == "__main__":
    main()
