"""Export feature-tree debug information from CAD model JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from prompt2cad.interpreter import build_model_with_graph
from prompt2cad.schema import validate_model_data


def model_data_to_feature_tree(model_data: dict) -> dict:
    """Build model data and return a debug feature-tree export."""
    validate_model_data(model_data)
    _, feature_graph = build_model_with_graph(model_data)
    return feature_graph.to_debug_tree()


def load_json(path: Path) -> dict:
    """Load JSON data from disk."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(data: dict, path: Path) -> None:
    """Save JSON data with readable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
        file.write("\n")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Export a debug feature tree from CAD model JSON."
    )
    parser.add_argument(
        "model_path",
        type=Path,
        help="Path to a CAD model JSON file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output path for the feature-tree JSON report.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the feature-tree export CLI."""
    args = parse_args()
    model_data = load_json(args.model_path)
    feature_tree = model_data_to_feature_tree(model_data)

    if args.output:
        save_json(feature_tree, args.output)
        print(f"SAVED {args.output}")
    else:
        print(json.dumps(feature_tree, indent=2))


if __name__ == "__main__":
    main()
