"""Validate and export the curated five-part portfolio showcase."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import cadquery as cq

from prompt2cad.candidate_evaluation import evaluate_design_intent_candidate
from prompt2cad.exporter import export_step
from prompt2cad.interpreter import build_model
from prompt2cad.training_data import DEFAULT_INTENT_EXAMPLES_DIR
from prompt2cad.training_data import load_intent_examples


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SHOWCASE_PATH = REPO_ROOT / "docs" / "showcase.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "generated" / "showcase"
DEFAULT_SVG_DIR = REPO_ROOT / "docs" / "assets" / "showcase"
REQUIRED_CASE_FIELDS = {"id", "title", "intent_example", "prompt", "capabilities"}
CASE_ID_PATTERN = re.compile(r"[a-z][a-z0-9_]*\Z")
SHOWCASE_CASE_COUNT = 5
SHOWCASE_SVG_OPTIONS = {
    "width": 900,
    "height": 560,
    "marginLeft": 35,
    "marginTop": 35,
    "projectionDir": (-1.75, 1.1, 5),
    "showAxes": False,
    "showHidden": True,
    "strokeColor": (21, 45, 80),
    "hiddenColor": (140, 157, 178),
}


def load_showcase(path: Path = DEFAULT_SHOWCASE_PATH) -> dict[str, Any]:
    """Load the tracked portfolio showcase manifest."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def validate_showcase(
    showcase_path: Path = DEFAULT_SHOWCASE_PATH,
    examples_dir: Path = DEFAULT_INTENT_EXAMPLES_DIR,
) -> dict[str, Any]:
    """Verify showcase metadata and every referenced CAD model end to end."""
    showcase = load_showcase(showcase_path)
    cases = showcase.get("cases")
    errors: list[str] = []
    results: list[dict[str, Any]] = []

    if not isinstance(cases, list):
        return {
            "passed": False,
            "errors": ["Showcase manifest must contain a cases array."],
            "cases": results,
        }

    if len(cases) != SHOWCASE_CASE_COUNT:
        errors.append(
            f"Showcase must contain exactly {SHOWCASE_CASE_COUNT} cases, "
            f"but contains {len(cases)}."
        )

    intent_examples = {
        example["name"]: example
        for example in load_intent_examples(examples_dir)
    }
    seen_case_ids: set[str] = set()

    for number, case in enumerate(cases, start=1):
        case_errors = validate_case_metadata(case, number, seen_case_ids)
        if case_errors:
            errors.extend(case_errors)
            results.append(
                {
                    "id": case.get("id", f"case_{number}"),
                    "title": case.get("title", f"Case {number}"),
                    "passed": False,
                    "failures": case_errors,
                }
            )
            continue

        intent_example = intent_examples.get(case["intent_example"])
        if intent_example is None:
            message = (
                f"Showcase case '{case['id']}' references missing intent example "
                f"'{case['intent_example']}'."
            )
            errors.append(message)
            results.append(
                {
                    "id": case["id"],
                    "title": case["title"],
                    "passed": False,
                    "failures": [message],
                }
            )
            continue

        if case["prompt"] != intent_example["prompt"]:
            message = (
                f"Showcase case '{case['id']}' does not match the prompt in "
                f"intent example '{case['intent_example']}'."
            )
            errors.append(message)
            results.append(
                {
                    "id": case["id"],
                    "title": case["title"],
                    "passed": False,
                    "failures": [message],
                }
            )
            continue

        candidate = evaluate_design_intent_candidate(intent_example["design_intent"])
        failures = candidate_failure_messages(candidate)
        results.append(
            {
                "id": case["id"],
                "title": case["title"],
                "intent_example": case["intent_example"],
                "capabilities": case["capabilities"],
                "passed": candidate["passed"],
                "failures": failures,
                "model_data": candidate.get("model_data"),
            }
        )

    return {
        "passed": not errors and all(result["passed"] for result in results),
        "errors": errors,
        "cases": results,
    }


def validate_case_metadata(
    case: Any,
    number: int,
    seen_case_ids: set[str],
) -> list[str]:
    """Return human-readable manifest errors for one showcase case."""
    if not isinstance(case, dict):
        return [f"Showcase case {number} must be a JSON object."]

    missing = sorted(REQUIRED_CASE_FIELDS - set(case))
    if missing:
        return [
            f"Showcase case {number} is missing required fields: {', '.join(missing)}."
        ]

    case_id = case["id"]
    if not isinstance(case_id, str) or not CASE_ID_PATTERN.fullmatch(case_id):
        return [
            f"Showcase case {number} has invalid id '{case_id}'. "
            "Use lowercase letters, numbers, and underscores."
        ]
    if case_id in seen_case_ids:
        return [f"Showcase case id '{case_id}' is duplicated."]
    seen_case_ids.add(case_id)

    if not isinstance(case["capabilities"], list) or not case["capabilities"]:
        return [
            f"Showcase case '{case_id}' must include at least one capability."
        ]

    return []


def candidate_failure_messages(candidate: dict[str, Any]) -> list[str]:
    """Keep a failed showcase report concise enough for terminal use."""
    feedback = candidate.get("feedback", {})
    messages: list[str] = []
    for key in (
        "intent_coverage_failures",
        "missing_required_dimensions",
        "intent_alignment_failures",
        "operation_effect_failures",
    ):
        values = feedback.get(key, [])
        if values:
            messages.append(f"{key}: {len(values)}")

    quality_report = candidate.get("quality_report") or {}
    for issue in quality_report.get("issues", []):
        if issue.get("severity") == "error":
            messages.append(issue.get("message", "Unknown geometry error."))

    return messages


def export_showcase(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    showcase_path: Path = DEFAULT_SHOWCASE_PATH,
    examples_dir: Path = DEFAULT_INTENT_EXAMPLES_DIR,
    validation_report: dict[str, Any] | None = None,
) -> list[Path]:
    """Validate the showcase, then export one STEP file per verified case."""
    report = verified_showcase_report(
        showcase_path,
        examples_dir,
        validation_report,
    )

    exported_paths = []
    for case in report["cases"]:
        part = build_model(case["model_data"])
        path = export_step(part, output_dir / f"{case['id']}.step")
        exported_paths.append(path)
    return exported_paths


def export_showcase_svg(
    output_dir: Path = DEFAULT_SVG_DIR,
    showcase_path: Path = DEFAULT_SHOWCASE_PATH,
    examples_dir: Path = DEFAULT_INTENT_EXAMPLES_DIR,
    validation_report: dict[str, Any] | None = None,
) -> list[Path]:
    """Export clean hidden-line isometric SVGs from the verified solids."""
    report = verified_showcase_report(
        showcase_path,
        examples_dir,
        validation_report,
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    exported_paths = []
    for case in report["cases"]:
        path = output_dir / f"{case['id']}.svg"
        cq.exporters.export(
            build_model(case["model_data"]),
            str(path),
            exportType=cq.exporters.ExportTypes.SVG,
            opt=SHOWCASE_SVG_OPTIONS,
        )
        exported_paths.append(path)
    return exported_paths


def verified_showcase_report(
    showcase_path: Path,
    examples_dir: Path,
    validation_report: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return a passing report or stop before exporting unverified artifacts."""
    report = validation_report or validate_showcase(showcase_path, examples_dir)
    if not report["passed"]:
        details = "\n".join(
            [*report["errors"], *failure_lines(report["cases"])]
        )
        raise ValueError(f"Showcase validation failed:\n{details}")
    return report


def failure_lines(cases: list[dict[str, Any]]) -> list[str]:
    """Return terminal-friendly summaries for failed showcase cases."""
    return [
        f"{case['id']}: {', '.join(case['failures']) or 'validation failed'}"
        for case in cases
        if not case["passed"]
    ]


def parse_args() -> argparse.Namespace:
    """Parse showcase validation and export options."""
    parser = argparse.ArgumentParser(
        description="Validate or export the five Prompt2ParametricCAD showcase models."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for generated STEP files.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate every case without writing STEP files.",
    )
    parser.add_argument(
        "--svg-dir",
        type=Path,
        help=(
            "Optional directory for hidden-line SVG projections generated "
            "from the verified solids."
        ),
    )
    return parser.parse_args()


def main() -> None:
    """Validate the showcase and optionally create its reproducible STEP files."""
    args = parse_args()
    report = validate_showcase()
    for case in report["cases"]:
        status = "PASS" if case["passed"] else "FAIL"
        print(f"{status} {case['id']}")

    if not report["passed"]:
        for error in report["errors"]:
            print(f"ERROR {error}")
        for line in failure_lines(report["cases"]):
            print(f"ERROR {line}")
        raise SystemExit(1)

    if args.validate_only:
        print("Validated 5 showcase cases without exporting STEP files.")
        return

    for path in export_showcase(args.output_dir, validation_report=report):
        print(f"EXPORTED {path}")
    if args.svg_dir:
        for path in export_showcase_svg(
            args.svg_dir,
            validation_report=report,
        ):
            print(f"RENDERED {path}")


if __name__ == "__main__":
    main()
