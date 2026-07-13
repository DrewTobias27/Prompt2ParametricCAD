"""Run a tiny, controlled comparison of prompt-generation API paths.

The default run is intentionally small:
- 2 prompts
- direct JSON generation vs. design-intent lowering
- no repair loop

That means 4 API calls total unless extra prompts are supplied.
"""

from __future__ import annotations

import argparse
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
from prompt2cad.prompting import prompt_to_design_intent
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


def evaluate_model_data(model_data: dict[str, Any]) -> dict[str, Any]:
    """Validate, build, and quality-check generated model data."""
    validate_model_data(model_data)
    part = build_model(model_data)
    quality_report = check_model_quality(
        model_data,
        build_succeeded=True,
        built_part=part,
    )
    return {
        "build_succeeded": True,
        "quality_passed": quality_report.get("passed", False),
        "quality_report": quality_report,
    }


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
    model_data = prompt_to_model_data(prompt)
    return {
        "model_data": model_data,
        **evaluate_model_data(model_data),
    }


def run_intent(prompt: str) -> dict[str, Any]:
    """Generate design intent, then lower it deterministically to model JSON."""
    design_intent = prompt_to_design_intent(prompt)
    missing_dimensions = missing_required_intent_dimensions(design_intent)
    try:
        model_data = intent_to_model_data(design_intent)
    except Exception as error:
        error.design_intent = design_intent
        error.intent_missing_required_dimensions = missing_dimensions
        raise
    try:
        evaluation = evaluate_model_data(model_data)
    except Exception as error:
        error.design_intent = design_intent
        error.intent_missing_required_dimensions = missing_dimensions
        error.model_data = model_data
        raise
    return {
        "design_intent": design_intent,
        "intent_missing_required_dimensions": missing_dimensions,
        "model_data": model_data,
        **evaluation,
    }


def run_case(prompt: str, mode: str) -> dict[str, Any]:
    """Run one prompt through one API path and return a compact result."""
    started_at = time.perf_counter()
    try:
        if mode == "direct":
            result = run_direct(prompt)
        elif mode == "intent":
            result = run_intent(prompt)
        else:
            raise ValueError(f"Unsupported mode: {mode}")
        return {
            "mode": mode,
            "status": status_for_result(result),
            "elapsed_seconds": round(time.perf_counter() - started_at, 2),
            **result,
        }
    except Exception as error:  # noqa: BLE001 - command-line report should capture any failure.
        return {
            "mode": mode,
            "status": "fail",
            "elapsed_seconds": round(time.perf_counter() - started_at, 2),
            **error_details(error),
        }


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
    return status


def attach_eval_result(
    result: dict[str, Any],
    *,
    eval_case: dict[str, Any] | None,
    model_output_path: Path | None,
) -> dict[str, Any]:
    """Attach saved model path and eval-case result when available."""
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
    expected_concepts = prompt_case.get("expected_concepts")
    model_data = result.get("model_data")
    if expected_concepts is not None and model_data is not None:
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
        if not concept_result.passed and result["status"] == "pass":
            result["status"] = "warn"

    expected_intent = prompt_case.get("expected_intent")
    design_intent = result.get("design_intent")
    if expected_intent is not None and design_intent is not None:
        intent_result = evaluate_design_intent(
            design_intent,
            {
                "name": prompt_case["case"],
                "expected_intent": expected_intent,
            },
        )
        result["intent_eval_passed"] = intent_result.passed
        result["intent_eval_failures"] = intent_result.failures
        if not intent_result.passed and result["status"] == "pass":
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
            model_data = result.get("model_data")
            if model_data is None and result.get("design_intent") is not None:
                try:
                    design_intent = result["design_intent"]
                    result["intent_missing_required_dimensions"] = (
                        missing_required_intent_dimensions(design_intent)
                    )
                    model_data = intent_to_model_data(design_intent)
                    result["model_data"] = model_data
                except Exception as error:  # noqa: BLE001 - report should capture failures.
                    result.update(error_details(error))
                    result["status"] = "fail"
                    continue

            if model_data is not None:
                try:
                    local_result = evaluate_model_data(model_data)
                    result.update(local_result)
                    clear_error_details(result)
                except Exception as error:  # noqa: BLE001 - report should capture failures.
                    result.update(error_details(error))
                    result["status"] = "fail"
                    continue

            attach_prompt_case_expectations(result, prompt_case)
            if model_data is not None:
                result["status"] = status_for_result(result)

    report["rescored_from"] = str(report_path)
    report["api_call_budget"] = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


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
    """Run prompt cases through direct and intent generation paths."""
    modes = modes or ["direct", "intent"]
    report = {
        "api_call_budget": len(prompt_cases) * len(modes),
        "modes": modes,
        "preflight": None,
        "cases": [],
    }

    if not skip_preflight:
        preflight = check_openai_connection()
        report["preflight"] = preflight
        if not preflight["passed"]:
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
    modes = modes or ["direct", "intent"]
    report = {
        "api_call_budget": len(case_names) * len(modes),
        "modes": modes,
        "cases_dir": str(cases_dir),
        "preflight": None,
        "cases": [],
    }

    if not skip_preflight:
        preflight = check_openai_connection()
        report["preflight"] = preflight
        if not preflight["passed"]:
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

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


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
            print(
                f"  {result['status'].upper()} {result['mode']} "
                f"{result['elapsed_seconds']}s {detail}"
            )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run a tiny API-path comparison: direct JSON vs design intent."
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
        "--mode",
        action="append",
        choices=["direct", "intent"],
        help=(
            "Generation mode to run. Pass once for a single mode or twice to "
            "choose both. Omit to run direct and intent."
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
