"""Export completed CadQuery models."""

from pathlib import Path

import cadquery as cq


def export_step(part: cq.Workplane, output_path: str | Path) -> Path:
    """Export a model as STEP and return the resulting path."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cq.exporters.export(part, str(path))
    return path

