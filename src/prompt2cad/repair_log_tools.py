"""Utilities for turning saved repair logs into reusable eval assets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any

from prompt2cad.interpreter import build_model
from prompt2cad.schema import validate_model_data


DEFAULT_FIXTURE_DIR = Path("evals/fixtures")
DEFAULT_CASE_DIR = Path("evals/cases")


def load_json(path: Path) -> dict[str, Any]:
    """Load JSON from a file."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, data: dict[str, Any], overwrite: bool = False) -> None:
    """Write JSON to a file, optionally refusing to overwrite."""
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"{path} already exists. Pass --overwrite to replace it."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )


def slugify_name(text: str, fallback: str = "repair_log_case") -> str:
    """Return a safe snake_case name for eval files."""
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")
    slug = re.sub(r"_+", "_", slug)
    return slug[:64] or fallback


def model_data_from_repair_log(
    repair_log: dict[str, Any],
    source: str = "repaired",
) -> dict[str, Any]:
    """Choose model data from a repair log."""
    repair_history = repair_log.get("repair_history", [])
    if source == "repaired" and repair_history:
        repaired_model_data = repair_history[-1].get("repaired_model_data")
        if repaired_model_data is not None:
            return repaired_model_data

    if source == "failed" and repair_history:
        failed_model_data = repair_history[0].get("failed_model_data")
        if failed_model_data is not None:
            return failed_model_data

    final_model_data = repair_log.get("final_model_data")
    if final_model_data is not None:
        return final_model_data

    raise ValueError(
        "Repair log does not contain usable model data for source "
        f"'{source}'."
    )


def base_expectation(base_operation: dict[str, Any]) -> dict[str, Any]:
    """Return stable expected fields for the base operation."""
    expected_keys = [
        "type",
        "profile",
        "width",
        "height",
        "diameter",
        "sides",
        "distance",
        "angle",
    ]
    return {
        key: base_operation[key]
        for key in expected_keys
        if key in base_operation
    }


def required_operation_expectation(operation: dict[str, Any]) -> dict[str, Any]:
    """Return stable expected fields for a non-base operation."""
    expected_keys = [
        "type",
        "profile",
        "diameter",
        "width",
        "height",
        "sides",
        "distance",
        "depth",
        "angle",
        "radius",
    ]
    expectation = {
        key: operation[key]
        for key in expected_keys
        if key in operation
    }
    if "positions" in operation:
        expectation["position_count"] = len(operation["positions"])

    return expectation


def build_eval_case(
    *,
    name: str,
    prompt: str,
    fixture_filename: str,
    model_data: dict[str, Any],
) -> dict[str, Any]:
    """Build a starter fixture-backed eval case from model data."""
    operations = model_data.get("operations", [])
    if not operations:
        raise ValueError("Model data must contain at least one operation.")

    expected: dict[str, Any] = {
        "operation_count": len(operations),
        "base": base_expectation(operations[0]),
    }

    required_operations = [
        required_operation_expectation(operation)
        for operation in operations[1:]
    ]
    if required_operations:
        expected["required_operations"] = required_operations

    return {
        "name": name,
        "prompt": prompt,
        "fixture_model": f"../fixtures/{fixture_filename}",
        "expected": expected,
    }


def promote_repair_log(
    log_path: Path,
    *,
    name: str | None = None,
    source: str = "repaired",
    fixture_dir: Path = DEFAULT_FIXTURE_DIR,
    case_dir: Path = DEFAULT_CASE_DIR,
    write_case: bool = True,
    overwrite: bool = False,
) -> dict[str, Path]:
    """Promote one repair log into an eval fixture and optional eval case."""
    repair_log = load_json(log_path)
    prompt = repair_log.get("prompt", log_path.stem)
    case_name = name or slugify_name(prompt)
    fixture_filename = f"{case_name}.json"
    fixture_path = fixture_dir / fixture_filename
    case_path = case_dir / fixture_filename
    model_data = model_data_from_repair_log(repair_log, source=source)

    validate_model_data(model_data)
    build_model(model_data)
    write_json(fixture_path, model_data, overwrite=overwrite)

    written_paths = {"fixture": fixture_path}
    if write_case:
        eval_case = build_eval_case(
            name=case_name,
            prompt=prompt,
            fixture_filename=fixture_filename,
            model_data=model_data,
        )
        write_json(case_path, eval_case, overwrite=overwrite)
        written_paths["case"] = case_path

    return written_paths


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Promote a saved repair log into eval fixture assets."
    )
    parser.add_argument("log_path", type=Path, help="Path to a repair log JSON file.")
    parser.add_argument("--name", help="Eval/fixture filename stem to use.")
    parser.add_argument(
        "--source",
        choices=["repaired", "final", "failed"],
        default="repaired",
        help="Which model data from the log to promote.",
    )
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=DEFAULT_FIXTURE_DIR,
        help="Directory for promoted fixture JSON.",
    )
    parser.add_argument(
        "--cases-dir",
        type=Path,
        default=DEFAULT_CASE_DIR,
        help="Directory for generated eval case JSON.",
    )
    parser.add_argument(
        "--fixture-only",
        action="store_true",
        help="Only write the fixture model; skip the eval case.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing promoted files.",
    )
    return parser.parse_args()


def main() -> None:
    """Promote a repair log from the command line."""
    args = parse_args()
    written_paths = promote_repair_log(
        args.log_path,
        name=args.name,
        source=args.source,
        fixture_dir=args.fixtures_dir,
        case_dir=args.cases_dir,
        write_case=not args.fixture_only,
        overwrite=args.overwrite,
    )

    print(f"WROTE fixture {written_paths['fixture']}")
    if "case" in written_paths:
        print(f"WROTE case {written_paths['case']}")


if __name__ == "__main__":
    main()
