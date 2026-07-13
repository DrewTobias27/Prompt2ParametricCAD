"""Compare eval generation quality across OpenAI model choices."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
from typing import Iterator

from prompt2cad.eval_generator import generate_eval_models
from prompt2cad.eval_runner import run_batch


DEFAULT_OUTPUT_ROOT = Path("generated/model_ab")


@contextmanager
def temporary_env_var(name: str, value: str) -> Iterator[None]:
    """Temporarily set one environment variable."""
    original_value = os.environ.get(name)
    os.environ[name] = value
    try:
        yield
    finally:
        if original_value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = original_value


def safe_label(text: str) -> str:
    """Return a filesystem-friendly label."""
    return (
        text.replace("/", "-")
        .replace("\\", "-")
        .replace(":", "-")
        .replace(" ", "_")
    )


def compare_models(
    models: list[str],
    *,
    cases_dir: Path = Path("evals/cases"),
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    overwrite: bool = False,
    case_names: list[str] | None = None,
    model_env_var: str = "PROMPT2CAD_OPENAI_MODEL",
) -> dict:
    """Generate and evaluate the same cases under each requested model."""
    output_root.mkdir(parents=True, exist_ok=True)
    report = {
        "model_env_var": model_env_var,
        "cases_dir": str(cases_dir),
        "models": [],
    }

    for model in models:
        model_label = safe_label(model)
        model_output_dir = output_root / model_label
        with temporary_env_var(model_env_var, model):
            generated_paths, generation_failures = generate_eval_models(
                cases_dir=cases_dir,
                output_dir=model_output_dir,
                overwrite=overwrite,
                case_names=case_names,
            )
            eval_failures = run_batch(
                models_dir=model_output_dir,
                cases_dir=cases_dir,
                case_names=case_names,
            )

        report["models"].append(
            {
                "model": model,
                "output_dir": str(model_output_dir),
                "generated_count": len(generated_paths),
                "generation_failures": generation_failures,
                "eval_failures": eval_failures,
                "passed": not generation_failures and not eval_failures,
            }
        )

    report_path = output_root / "comparison_report.json"
    report_path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    report["report_path"] = str(report_path)
    return report


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="A/B compare Prompt2CAD eval generation across API models."
    )
    parser.add_argument(
        "--model",
        action="append",
        required=True,
        help="Model name to test. Pass more than once for A/B comparison.",
    )
    parser.add_argument(
        "--cases-dir",
        type=Path,
        default=Path("evals/cases"),
        help="Folder containing eval case JSON files.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Folder where per-model outputs and comparison report are written.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate per-model output JSON files if they already exist.",
    )
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        help=(
            "Run only the named eval case. May be passed more than once. "
            "Use the case filename without .json."
        ),
    )
    parser.add_argument(
        "--model-env-var",
        default="PROMPT2CAD_OPENAI_MODEL",
        help="Environment variable used by prompting.py for model selection.",
    )
    return parser.parse_args()


def print_report_summary(report: dict) -> None:
    """Print a compact comparison summary."""
    print(f"WROTE {report['report_path']}")
    for model_result in report["models"]:
        status = "PASS" if model_result["passed"] else "FAIL"
        print(
            f"{status} {model_result['model']} "
            f"generated={model_result['generated_count']} "
            f"generation_failures={len(model_result['generation_failures'])} "
            f"eval_failures={len(model_result['eval_failures'])}"
        )


def main() -> None:
    """Run model A/B eval comparison from the command line."""
    args = parse_args()
    report = compare_models(
        args.model,
        cases_dir=args.cases_dir,
        output_root=args.output_root,
        overwrite=args.overwrite,
        case_names=args.case,
        model_env_var=args.model_env_var,
    )
    print_report_summary(report)
    if any(not model_result["passed"] for model_result in report["models"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
