"""Command-line entry point for Prompt2ParametricCAD."""

import argparse
import json
from pathlib import Path

from prompt2cad.exporter import export_step
from prompt2cad.interpreter import build_model
from prompt2cad.loader import load_model
from prompt2cad.schema import validate_model_data
from prompt2cad.prompting import prompt_to_model_data
from prompt2cad.prompting import read_prompt_file


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Convert a CAD prompt or JSON model to a STEP file."
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help=(
            "JSON input and STEP output, or only STEP output when using "
            "--prompt-file."
        ),
    )
    parser.add_argument(
        "--prompt-file",
        type=Path,
        help="Path to a text file containing a natural-language CAD prompt.",
    )
    parser.add_argument(
        "--save-json",
        type=Path,
        help="Optional path for saving API-generated CAD model JSON.",
    )
    return parser.parse_args()


def main() -> None:
    """Load or generate model data, build it, and export it as STEP."""
    args = parse_args()

    if args.prompt_file:
        if len(args.paths) != 1:
            raise SystemExit(
                "Prompt mode expects one positional path: output_path."
            )

        output_path = args.paths[0]
        prompt = read_prompt_file(args.prompt_file)
        model_data = prompt_to_model_data(prompt)

        if args.save_json:
            args.save_json.parent.mkdir(parents=True, exist_ok=True)
            with args.save_json.open("w", encoding="utf-8") as file:
                json.dump(model_data, file, indent=2)
                file.write("\n")
    else:
        if args.save_json:
            raise SystemExit("--save-json can only be used with --prompt-file.")
        if len(args.paths) != 2:
            raise SystemExit(
                "JSON mode expects two positional paths: input_path output_path."
            )

        input_path = args.paths[0]
        output_path = args.paths[1]
        model_data = load_model(input_path)

    validate_model_data(model_data)
    part = build_model(model_data)
    exported_path = export_step(part, output_path)

    if args.save_json:
        print(f"Saved CAD JSON to {args.save_json}")
    print(f"Exported STEP file to {exported_path}")


if __name__ == "__main__":
    main()
