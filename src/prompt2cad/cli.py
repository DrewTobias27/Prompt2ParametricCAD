"""Command-line entry point for Prompt2ParametricCAD."""

import argparse
from pathlib import Path

from prompt2cad.exporter import export_step
from prompt2cad.interpreter import build_model
from prompt2cad.loader import load_model
from prompt2cad.schema import validate_model_data


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert a JSON CAD model to a STEP file."
    )
    parser.add_argument(
        "input_path",
        type=Path,
        help="Path to the input JSON file containing the CAD model.",
    )
    parser.add_argument(
        "output_path",
        type=Path,
        help="Path to the output STEP file.",
    )
    return parser.parse_args()


def main() -> None:
    """Load a model JSON file, build it, and export it as STEP."""
    args = parse_args()
    input_path = args.input_path
    output_path = args.output_path

    model_data = load_model(input_path)
    validate_model_data(model_data)
    part = build_model(model_data)
    export_step(part, output_path)


if __name__ == "__main__":
    main()
