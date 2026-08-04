"""Compare OpenAI models on semantic CAD intent and built geometry."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
from typing import Any, Iterator

from prompt2cad.tiny_api_compare import check_openai_connection
from prompt2cad.tiny_api_compare import compare_eval_cases
from prompt2cad.tiny_api_compare import compare_prompt_cases
from prompt2cad.tiny_api_compare import filter_prompt_cases
from prompt2cad.tiny_api_compare import load_prompt_cases


DEFAULT_MODELS = [
    "gpt-5.5",
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
]
DEFAULT_PROMPT_CASES = [
    "corner_bosses_with_concentric_holes",
    "counterbored_bolt_circle",
    "u_bracket_one_hole_per_wall",
    "nested_boss_side_cross_hole",
    "stepped_shaft_collars_grooves_end_bore",
    "half_cylinder_plate_holes_and_groove",
    "open_tray_rim_and_bottom_drain",
    "d_plate_side_tabs_with_tab_holes",
]
DEFAULT_EVAL_CASES = [
    "circular_flange_six_bolt_holes",
    "mixed_plate_hole_and_posts",
    "rectangular_block_front_hole_top_boss",
]
DEFAULT_OUTPUT_ROOT = Path("generated/model_matrix")


@contextmanager
def temporary_environment(values: dict[str, str]) -> Iterator[None]:
    """Temporarily configure a model benchmark without changing production."""
    original = {name: os.environ.get(name) for name in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for name, value in original.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def safe_model_name(model: str) -> str:
    """Return a stable folder name for one model ID."""
    return "".join(
        character if character.isalnum() or character in {"-", "_"} else "-"
        for character in model
    )


def iter_results(report: dict[str, Any], mode: str | None = None):
    """Yield results from a benchmark report, optionally for one mode."""
    for case in report.get("cases", []):
        for result in case.get("results", []):
            if mode == "intent" and isinstance(result.get("first_pass_result"), dict):
                yield result["first_pass_result"]
                continue
            if mode is None or result.get("mode") == mode:
                yield result


def result_metrics(reports: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    """Summarize strict outcomes, retries, latency, and token use for one mode."""
    results = [result for report in reports for result in iter_results(report, mode)]
    status_counts = {"pass": 0, "warn": 0, "fail": 0}
    for result in results:
        status = result.get("status", "fail")
        status_counts[status] = status_counts.get(status, 0) + 1

    elapsed = [
        float(result["elapsed_seconds"])
        for result in results
        if isinstance(result.get("elapsed_seconds"), (int, float))
    ]
    tokens = [
        int(result.get("api_telemetry", {}).get("total_tokens", 0))
        for result in results
    ]
    logical_calls = [
        int(result.get("api_telemetry", {}).get("logical_api_calls", 1))
        for result in results
    ]
    repair_counts = [int(result.get("repair_count", 0)) for result in results]
    return {
        "result_count": len(results),
        "status_counts": status_counts,
        "strict_pass_rate": (
            round(status_counts["pass"] / len(results), 4) if results else 0.0
        ),
        "average_seconds": round(sum(elapsed) / len(elapsed), 3) if elapsed else 0.0,
        "total_tokens": sum(tokens),
        "average_tokens": round(sum(tokens) / len(tokens), 1) if tokens else 0.0,
        "logical_api_calls": sum(logical_calls),
        "repair_count": sum(repair_counts),
        "recovered_cases": sum(
            1
            for result in results
            if result.get("status") == "pass" and result.get("repair_count", 0) > 0
        ),
    }


def model_score(model_result: dict[str, Any]) -> tuple:
    """Rank geometry correctness before retries, latency, or token cost."""
    production = model_result["production"]
    first_pass = model_result["first_pass"]
    return (
        production["status_counts"]["pass"],
        -production["status_counts"]["fail"],
        -production["status_counts"]["warn"],
        first_pass["status_counts"]["pass"],
        -production["repair_count"],
        -production["average_seconds"],
        -production["average_tokens"],
    )


def compare_model_matrix(
    models: list[str],
    *,
    prompt_file: Path,
    prompt_case_names: list[str],
    eval_case_names: list[str],
    cases_dir: Path,
    output_root: Path,
    modes: list[str],
    reasoning_effort: str,
    repetitions: int = 1,
    skip_preflight: bool = False,
) -> dict[str, Any]:
    """Run identical semantic and exact-geometry suites for every model."""
    if repetitions < 1:
        raise ValueError("repetitions must be at least 1")
    prompt_cases = filter_prompt_cases(
        load_prompt_cases(prompt_file),
        prompt_case_names,
    )
    if prompt_case_names and len(prompt_cases) != len(set(prompt_case_names)):
        found = {str(case["case"]) for case in prompt_cases}
        missing = sorted(set(prompt_case_names) - found)
        raise ValueError(f"Unknown prompt cases: {', '.join(missing)}")

    output_root.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "models": models,
        "modes": modes,
        "reasoning_effort": reasoning_effort,
        "repetitions": repetitions,
        "prompt_file": str(prompt_file),
        "prompt_cases": [case["case"] for case in prompt_cases],
        "eval_cases": eval_case_names,
        "evaluation_layers": [
            "structured_output_schema",
            "design_intent_coverage",
            "required_dimensions",
            "intent_expectations",
            "deterministic_lowering",
            "target_alignment",
            "cad_schema_validation",
            "valid_connected_geometry",
            "quality_gate",
            "per_operation_physical_effect",
            "concept_and_relationship_expectations",
            "exact_case_geometry",
        ],
        "preflight": None,
        "model_results": [],
    }

    if not skip_preflight:
        report["preflight"] = check_openai_connection()
        if not report["preflight"]["passed"]:
            write_report(report, output_root / "comparison_report.json")
            return report

    for model in models:
        model_root = output_root / safe_model_name(model)
        environment = {
            "PROMPT2CAD_OPENAI_MODEL": model,
            "PROMPT2CAD_REASONING_EFFORT": reasoning_effort,
        }
        semantic_reports = []
        exact_reports = []
        semantic_paths = []
        exact_paths = []
        with temporary_environment(environment):
            for repetition in range(1, repetitions + 1):
                repetition_root = model_root / f"run_{repetition}"
                semantic_path = repetition_root / "semantic_report.json"
                exact_path = repetition_root / "exact_geometry_report.json"
                semantic_reports.append(compare_prompt_cases(
                    prompt_cases,
                    output_path=semantic_path,
                    skip_preflight=True,
                    modes=modes,
                ))
                exact_reports.append(compare_eval_cases(
                    eval_case_names,
                    cases_dir=cases_dir,
                    output_path=exact_path,
                    skip_preflight=True,
                    modes=modes,
                ))
                semantic_paths.append(str(semantic_path))
                exact_paths.append(str(exact_path))

        model_result = {
            "model": model,
            "semantic_reports": semantic_paths,
            "exact_geometry_reports": exact_paths,
            "first_pass": result_metrics(
                semantic_reports + exact_reports,
                "intent",
            ),
            "production": result_metrics(
                semantic_reports + exact_reports,
                "intent_feedback",
            ),
        }
        report["model_results"].append(model_result)
        write_ranked_report(report, output_root / "comparison_report.json")

    return write_ranked_report(report, output_root / "comparison_report.json")


def write_ranked_report(report: dict[str, Any], path: Path) -> dict[str, Any]:
    """Attach correctness-first ranking and checkpoint the matrix report."""
    ranked = sorted(report.get("model_results", []), key=model_score, reverse=True)
    report["ranking"] = [result["model"] for result in ranked]
    return write_report(report, path)


def write_report(report: dict[str, Any], path: Path) -> dict[str, Any]:
    """Write a readable checkpoint and return the report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    report["report_path"] = str(path)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    """Parse model-matrix command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Compare models on first-pass CAD interpretation and the production "
            "geometry-feedback loop."
        )
    )
    parser.add_argument("--model", action="append", default=[])
    parser.add_argument(
        "--reasoning-effort",
        default="low",
        choices=["none", "minimal", "low", "medium", "high", "xhigh", "max"],
    )
    parser.add_argument(
        "--prompt-file",
        type=Path,
        default=Path("evals/intent_relational_cases.json"),
    )
    parser.add_argument("--prompt-case", action="append", default=[])
    parser.add_argument("--eval-case", action="append", default=[])
    parser.add_argument("--cases-dir", type=Path, default=Path("evals/cases"))
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--repetitions",
        type=int,
        default=1,
        help=(
            "Repeat every case for stability analysis. Use one run to screen "
            "models, then three or more for finalists."
        ),
    )
    parser.add_argument(
        "--mode",
        action="append",
        choices=["intent", "intent_feedback"],
    )
    parser.add_argument("--skip-preflight", action="store_true")
    return parser.parse_args()


def print_summary(report: dict[str, Any]) -> None:
    """Print the model ranking and its correctness/efficiency evidence."""
    print(f"WROTE {report['report_path']}")
    preflight = report.get("preflight")
    if preflight and not preflight.get("passed"):
        print(f"PREFLIGHT FAIL {preflight.get('reason')}")
        return
    for model_result in report.get("model_results", []):
        first_pass = model_result["first_pass"]
        production = model_result["production"]
        print(
            f"MODEL {model_result['model']} "
            f"first_pass={first_pass['status_counts']['pass']}/{first_pass['result_count']} "
            f"production={production['status_counts']['pass']}/{production['result_count']} "
            f"repairs={production['repair_count']} "
            f"avg={production['average_seconds']}s "
            f"avg_tokens={production['average_tokens']}"
        )
    if report.get("ranking"):
        print("RANKING " + " > ".join(report["ranking"]))


def main() -> None:
    """Run the controlled model matrix."""
    args = parse_args()
    report = compare_model_matrix(
        args.model or DEFAULT_MODELS,
        prompt_file=args.prompt_file,
        prompt_case_names=args.prompt_case or DEFAULT_PROMPT_CASES,
        eval_case_names=args.eval_case or DEFAULT_EVAL_CASES,
        cases_dir=args.cases_dir,
        output_root=args.output_root,
        modes=args.mode or ["intent_feedback"],
        reasoning_effort=args.reasoning_effort,
        repetitions=args.repetitions,
        skip_preflight=args.skip_preflight,
    )
    print_summary(report)


if __name__ == "__main__":
    main()
