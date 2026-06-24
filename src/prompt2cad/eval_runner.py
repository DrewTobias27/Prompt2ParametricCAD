"""Run Prompt2ParametricCAD eval cases against generated model JSON."""

import argparse
import json
from pathlib import Path

from prompt2cad.evaluator import evaluate_model_data
from prompt2cad.interpreter import build_model
from prompt2cad.schema import validate_model_data


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Evaluate generated CAD JSON against an eval case."
    )
    parser.add_argument(
        "model_path",
        nargs="?",
        type=Path,
        help="Path to generated CAD model JSON.",
    )
    parser.add_argument(
        "case_path",
        nargs="?",
        type=Path,
        help="Path to eval case JSON.",
    )
    parser.add_argument(
        "--models-dir",
        type=Path,
        help="Folder containing generated CAD model JSON files.",
    )
    parser.add_argument(
        "--cases-dir",
        type=Path,
        help="Folder containing eval case JSON files.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict:
    """Load JSON data from a file."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def run_eval(
    model_path: Path,
    case_path: Path,
) -> tuple[str, list[str]]:
    """Run one eval case against one generated CAD model JSON file."""
    model_data = load_json(model_path)
    eval_case = load_json(case_path)

    validate_model_data(model_data)
    build_model(model_data)

    result = evaluate_model_data(model_data, eval_case)
    case_name = eval_case["name"]

    return case_name, result.failures


def run_batch(
    models_dir: Path,
    cases_dir: Path,
) -> list[str]:
    """Run all eval cases against all generated CAD model JSON files."""
    all_failures = []

    for case_path in sorted(cases_dir.glob("*.json")):
        model_path = models_dir / case_path.name

        if not model_path.exists():
            failure = f"Missing generated model file: {model_path}"
            all_failures.append(failure)
            print(f"FAIL {case_path.stem}")
            print(f"  - {failure}")
            continue

        case_name, failures = run_eval(model_path, case_path)

        if not failures:
            print(f"PASS {case_name}")
        else:
            print(f"FAIL {case_name}")
            for failure in failures:
                print(f"  - {failure}")
            all_failures.extend(failures)

    return all_failures


def main() -> None:
    """Run evals in single-case mode or batch mode."""
    args = parse_args()

    batch_requested = args.models_dir is not None or args.cases_dir is not None
    single_requested = args.model_path is not None or args.case_path is not None

    if batch_requested:
        if args.models_dir is None or args.cases_dir is None:
            raise SystemExit(
                "Batch mode requires both --models-dir and --cases-dir."
            )
        if single_requested:
            raise SystemExit(
                "Use either single-case paths or batch-mode folders, not both."
            )

        failures = run_batch(args.models_dir, args.cases_dir)
        if failures:
            raise SystemExit(1)
        return

    if args.model_path is None or args.case_path is None:
        raise SystemExit(
            "Single-case mode requires both model_path and case_path."
        )

    case_name, failures = run_eval(args.model_path, args.case_path)

    if not failures:
        print(f"PASS {case_name}")
    else:
        print(f"FAIL {case_name}")
        for failure in failures:
            print(f"  - {failure}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
