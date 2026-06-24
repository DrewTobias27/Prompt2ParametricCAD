"""Generate CAD model JSON files for eval cases."""

import argparse
import json
from pathlib import Path

from prompt2cad.interpreter import build_model
from prompt2cad.prompting import prompt_to_model_data
from prompt2cad.schema import validate_model_data


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate CAD JSON files from eval case prompts."
    )
    parser.add_argument(
        "--cases-dir",
        type=Path,
        default=Path("evals/cases"),
        help="Folder containing eval case JSON files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("generated/evals"),
        help="Folder where generated CAD model JSON files will be saved.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate files that already exist.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict:
    """Load JSON data from a file."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(data: dict, path: Path) -> None:
    """Save JSON data to a file with readable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
        file.write("\n")


def generate_eval_models(
    cases_dir: Path,
    output_dir: Path,
    overwrite: bool = False,
) -> tuple[list[Path], list[str]]:
    """Generate CAD model JSON files for all eval cases in a folder."""
    generated_paths = []
    failures = []

    for case_path in sorted(cases_dir.glob("*.json")):
        output_path = output_dir / case_path.name

        if output_path.exists() and not overwrite:
            print(f"SKIP {output_path}")
            continue

        eval_case = load_json(case_path)
        case_name = eval_case["name"]

        try:
            model_data = prompt_to_model_data(eval_case["prompt"])
            validate_model_data(model_data)
            build_model(model_data)
        except Exception as error:
            failure = f"{case_name}: {error}"
            failures.append(failure)
            print(f"FAIL {case_name}")
            print(f"  - {error}")
            continue

        save_json(model_data, output_path)
        generated_paths.append(output_path)
        print(f"SAVED {output_path}")

    return generated_paths, failures


def main() -> None:
    """Generate eval model JSON files from eval case prompts."""
    args = parse_args()

    _, failures = generate_eval_models(
        cases_dir=args.cases_dir,
        output_dir=args.output_dir,
        overwrite=args.overwrite,
    )
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
