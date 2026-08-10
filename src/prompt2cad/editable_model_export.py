"""Export a versioned editable-model document from CAD operation JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from prompt2cad.editable_model import model_data_to_editable_document


def load_json(path: Path) -> dict:
    """Load model data from disk."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(data: dict, path: Path) -> None:
    """Save readable JSON to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
        file.write("\n")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Export an editable feature document from CAD model JSON."
    )
    parser.add_argument(
        "model_path",
        type=Path,
        help="Path to a validated CAD model JSON file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output path. Prints JSON when omitted.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the editable-model export CLI."""
    args = parse_args()
    model_data = load_json(args.model_path)
    editable_document = model_data_to_editable_document(model_data).to_dict()

    if args.output:
        save_json(editable_document, args.output)
        print(f"SAVED {args.output}")
    else:
        print(json.dumps(editable_document, indent=2))


if __name__ == "__main__":
    main()
