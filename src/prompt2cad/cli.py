"""Command-line entry point for Prompt2ParametricCAD."""

from pathlib import Path

from prompt2cad.exporter import export_step
from prompt2cad.interpreter import build_model
from prompt2cad.loader import load_model


def main() -> None:
    """Load one example model, build it, and export it."""
    project_root = Path(__file__).resolve().parents[2]
    input_path = project_root / "examples" / "example_part.json"
    output_path = project_root / "generated" / "example_part.step"

    model_data = load_model(input_path)
    part = build_model(model_data)
    export_step(part, output_path)


if __name__ == "__main__":
    main()

