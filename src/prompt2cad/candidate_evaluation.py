"""Evaluate generated CAD candidates before accepting or repairing them."""

from __future__ import annotations

from typing import Any

from prompt2cad.design_intent import intent_to_model_data
from prompt2cad.design_intent import missing_required_intent_dimensions
from prompt2cad.intent_alignment import evaluate_intent_alignment
from prompt2cad.intent_coverage import intent_coverage_failures
from prompt2cad.operation_effects import evaluate_operation_effects
from prompt2cad.quality import check_model_quality


REPAIRABLE_QUALITY_WARNING_CODES = {
    "edge_operation_targets_face",
    "face_operation_targets_edge",
}


def evaluate_model_candidate(model_data: dict[str, Any] | None) -> dict[str, Any]:
    """Build a model and verify geometry plus every operation's physical effect."""
    quality_report = check_model_quality(model_data, include_build=True)
    operation_effects = empty_operation_effects()

    if quality_report.get("passed") and model_data is not None:
        try:
            operation_effects = evaluate_operation_effects(model_data)
        except Exception as error:  # Geometry diagnostics must stay report-shaped.
            operation_effects = {
                "passed": False,
                "failures": [f"Operation-effect evaluation failed: {error}"],
                "warnings": [],
                "trace": [],
            }

    passed = bool(
        quality_report.get("passed")
        and operation_effects.get("passed")
        and not quality_report_needs_repair(quality_report)
    )
    return {
        "passed": passed,
        "quality_report": quality_report,
        "operation_effects": operation_effects,
        "feedback": compact_model_feedback(
            quality_report,
            operation_effects,
        ),
    }


def quality_report_needs_repair(quality_report: dict[str, Any]) -> bool:
    """Return whether errors or actionable target warnings require repair."""
    if not quality_report.get("passed", False):
        return True

    return any(
        issue.get("code") in REPAIRABLE_QUALITY_WARNING_CODES
        for issue in quality_report.get("issues", [])
    )


def evaluate_design_intent_candidate(
    design_intent: dict[str, Any],
) -> dict[str, Any]:
    """Lower, build, and evaluate one design-intent candidate."""
    coverage_failures = intent_coverage_failures(design_intent)
    missing_dimensions = missing_required_intent_dimensions(design_intent)
    try:
        model_data = intent_to_model_data(design_intent)
    except Exception as error:
        return {
            "passed": False,
            "model_data": None,
            "intent_coverage_failures": coverage_failures,
            "missing_required_dimensions": missing_dimensions,
            "quality_report": None,
            "operation_effects": empty_operation_effects(),
            "feedback": {
                "intent_coverage_failures": coverage_failures,
                "missing_required_dimensions": missing_dimensions,
                "lowering_error": str(error),
                "suggested_action": (
                    "Correct the design-intent structure, required dimensions, "
                    "feature order, targets, or placements before lowering again."
                ),
            },
        }

    model_evaluation = evaluate_model_candidate(model_data)
    intent_alignment = evaluate_intent_alignment(design_intent, model_data)
    feedback = {
        "intent_coverage_failures": coverage_failures,
        "missing_required_dimensions": missing_dimensions,
        "intent_alignment_failures": intent_alignment["failures"],
        **model_evaluation["feedback"],
    }
    return {
        "passed": (
            not coverage_failures
            and not missing_dimensions
            and intent_alignment["passed"]
            and model_evaluation["passed"]
        ),
        "model_data": model_data,
        "intent_coverage_failures": coverage_failures,
        "missing_required_dimensions": missing_dimensions,
        "intent_alignment": intent_alignment,
        "quality_report": model_evaluation["quality_report"],
        "operation_effects": model_evaluation["operation_effects"],
        "feedback": feedback,
    }


def compact_model_feedback(
    quality_report: dict[str, Any],
    operation_effects: dict[str, Any],
) -> dict[str, Any]:
    """Return only actionable, bounded facts for an API repair request."""
    issues = [
        {
            key: issue.get(key)
            for key in (
                "severity",
                "stage",
                "code",
                "message",
                "suggestion",
                "operation_number",
                "operation_id",
            )
            if issue.get(key) is not None
        }
        for issue in quality_report.get("issues", [])
        if issue.get("severity") in {"error", "warning"}
    ]
    return {
        "quality_status": quality_report.get("status"),
        "quality_issues": issues,
        "geometry_summary": quality_report.get("geometry_summary"),
        "operation_effect_failures": operation_effects.get("failures", []),
        "operation_effect_warnings": operation_effects.get("warnings", []),
        "operation_trace": compact_operation_trace(operation_effects.get("trace", [])),
    }


def compact_operation_trace(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep geometry deltas and failed instances without repeating full models."""
    compact_trace = []
    for entry in trace:
        failed_instances = [
            instance
            for instance in entry.get("instance_effects", [])
            if not instance.get("affected_model", False)
        ]
        compact_trace.append({
            "operation_number": entry.get("operation_number"),
            "operation_id": entry.get("operation_id"),
            "operation_type": entry.get("operation_type"),
            "target": entry.get("target"),
            "volume_delta": entry.get("volume_delta"),
            "solid_count_after": entry.get("solid_count_after"),
            "failed_instances": failed_instances,
        })
    return compact_trace


def empty_operation_effects() -> dict[str, Any]:
    """Return a neutral operation-effect report when a model cannot be built."""
    return {
        "passed": True,
        "failures": [],
        "warnings": [],
        "trace": [],
    }
