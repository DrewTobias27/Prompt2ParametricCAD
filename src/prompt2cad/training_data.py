"""Utilities for building prompt-to-design-intent training data.

The long-term model-training target should be design intent, not raw CAD
operations. Intent examples teach the model to recognize concepts such as
"near the corners", "centered boss", "bolt circle", and "slot"; deterministic
backend code then lowers those concepts into exact CAD JSON.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from prompt2cad.design_intent import intent_to_model_data
from prompt2cad.design_intent import validate_design_intent
from prompt2cad.diagnostics import check_model_data


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INTENT_EXAMPLES_DIR = REPO_ROOT / "training" / "intent_examples"

INTENT_TRAINING_SYSTEM_MESSAGE = (
    "Convert the user's CAD request into Prompt2ParametricCAD design-intent "
    "JSON. Use high-level placements like centered, near_corners, "
    "circular_pattern, mirrored, and explicit instead of calculating raw CAD "
    "operation positions yourself."
)


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_jsonl(records: list[dict[str, Any]], output_path: Path) -> None:
    """Write records as newline-delimited JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, separators=(",", ":")))
            file.write("\n")


def load_intent_examples(
    examples_dir: Path = DEFAULT_INTENT_EXAMPLES_DIR,
) -> list[dict[str, Any]]:
    """Load all prompt-to-intent examples from a directory."""
    examples = []
    for example_path in sorted(examples_dir.glob("*.json")):
        example = load_json(example_path)
        example["source_file"] = example_path.name
        examples.append(example)

    return examples


def validate_intent_example(example: dict[str, Any]) -> dict[str, Any]:
    """Validate one training example and return its lowered model data."""
    required_fields = ["name", "prompt", "design_intent"]
    missing_fields = [field for field in required_fields if field not in example]
    if missing_fields:
        raise ValueError(
            f"Intent example is missing required fields: {', '.join(missing_fields)}"
        )

    validate_design_intent(example["design_intent"])
    model_data = intent_to_model_data(example["design_intent"])
    diagnosis = check_model_data(model_data)
    if not diagnosis["passed"]:
        raise ValueError(
            "Intent example did not lower into valid buildable model data: "
            f"{diagnosis['reason']}"
        )

    return model_data


def build_generic_training_record(example: dict[str, Any]) -> dict[str, Any]:
    """Build a provider-neutral training record."""
    model_data = validate_intent_example(example)
    return {
        "name": example["name"],
        "prompt": example["prompt"],
        "design_intent": example["design_intent"],
        "lowered_model_data": model_data,
        "tags": example.get("tags", []),
        "source_name": example.get("source_name", "Prompt2ParametricCAD internal example"),
        "source_license": example.get(
            "source_license",
            "Project-authored example; not from an external dataset.",
        ),
    }


def build_openai_messages_record(example: dict[str, Any]) -> dict[str, Any]:
    """Build a chat-style supervised fine-tuning record."""
    validate_intent_example(example)
    return {
        "messages": [
            {
                "role": "system",
                "content": INTENT_TRAINING_SYSTEM_MESSAGE,
            },
            {
                "role": "user",
                "content": example["prompt"],
            },
            {
                "role": "assistant",
                "content": json.dumps(example["design_intent"], separators=(",", ":")),
            },
        ]
    }


def build_training_records(
    examples: list[dict[str, Any]],
    output_format: str = "generic",
) -> list[dict[str, Any]]:
    """Build training records from validated examples."""
    if output_format == "generic":
        return [build_generic_training_record(example) for example in examples]

    if output_format == "openai_messages":
        return [build_openai_messages_record(example) for example in examples]

    raise ValueError(
        "Unsupported training data format. Use 'generic' or 'openai_messages'."
    )


def export_training_jsonl(
    examples_dir: Path,
    output_path: Path,
    output_format: str = "generic",
) -> list[dict[str, Any]]:
    """Validate examples and export them as JSONL training data."""
    examples = load_intent_examples(examples_dir)
    records = build_training_records(examples, output_format=output_format)
    write_jsonl(records, output_path)
    return records


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Export prompt-to-design-intent examples as JSONL training data."
    )
    parser.add_argument(
        "--examples-dir",
        type=Path,
        default=DEFAULT_INTENT_EXAMPLES_DIR,
        help="Directory containing intent example JSON files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("generated/training/intent_training.jsonl"),
        help="Output JSONL path.",
    )
    parser.add_argument(
        "--format",
        choices=["generic", "openai_messages"],
        default="generic",
        help="Training record format.",
    )
    return parser.parse_args()


def main() -> None:
    """Export validated training records."""
    args = parse_args()
    records = export_training_jsonl(
        examples_dir=args.examples_dir,
        output_path=args.output,
        output_format=args.format,
    )
    print(f"Exported {len(records)} training records to {args.output}")


if __name__ == "__main__":
    main()
