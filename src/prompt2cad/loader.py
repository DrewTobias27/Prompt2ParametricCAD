"""Load structured model descriptions from JSON files."""

import json
from pathlib import Path


def load_model(file_path: str | Path) -> dict:
    """Load and return one model description from a JSON file."""
    path = Path(file_path)

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)

