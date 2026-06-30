"""Scaffold for importing reputable Fusion 360 Gallery examples.

This module does not download the Fusion 360 Gallery dataset and does not yet
claim full automatic conversion.  It gives the project a clean boundary for
future dataset work:

- record dataset provenance consistently
- inspect whether a source sequence is in the sketch/extrude subset we can
  realistically convert first
- wrap an already-converted Prompt2ParametricCAD model in the rich example
  format used by the retrieval library
"""

import json
import re
import zipfile
from pathlib import Path
from typing import Any

from prompt2cad.schema import validate_model_data


FUSION360_SOURCE_NAME = "Autodesk Fusion 360 Gallery Reconstruction Dataset"
FUSION360_SOURCE_URL = "https://github.com/AutodeskAILab/Fusion360GalleryDataset"
FUSION360_SOURCE_LICENSE = (
    "Non-commercial research license; see "
    "https://github.com/AutodeskAILab/Fusion360GalleryDataset/blob/master/LICENSE.md"
)
FUSION360_DERIVATION_NOTE = (
    "Derived from Fusion 360 Gallery Reconstruction Dataset construction "
    "sequence after conversion to Prompt2ParametricCAD JSON."
)

SUPPORTED_OPERATION_KEYWORDS = ("sketch", "extrude")
COMMON_SEQUENCE_KEYS = (
    "operations",
    "timeline",
    "sequence",
    "features",
    "entities",
)
CM_TO_MM = 10


class UnsupportedFusion360Sequence(ValueError):
    """Raised when a Fusion 360 sequence is outside the supported subset."""


def load_fusion360_json(path: str | Path) -> dict[str, Any] | list[Any]:
    """Load one Fusion 360 Gallery JSON file."""
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def load_regraph_pair_from_zip(
    zip_path: str | Path,
    sequence_name: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load a regraph sequence JSON and its referenced graph JSON from a zip."""
    with zipfile.ZipFile(zip_path) as archive:
        sequence_data = json.load(archive.open(sequence_name))
        sequence_steps = sequence_data.get("sequence", [])
        if not sequence_steps:
            raise UnsupportedFusion360Sequence(
                "Regraph sequence does not contain any steps."
            )

        graph_name = sequence_steps[0].get("graph")
        if not graph_name:
            raise UnsupportedFusion360Sequence(
                "Regraph sequence step does not reference a graph file."
            )

        sequence_dir = str(Path(sequence_name).parent).replace("\\", "/")
        graph_path = f"{sequence_dir}/{graph_name}"
        graph_data = json.load(archive.open(graph_path))

    return sequence_data, graph_data


def extract_sequence_operations(raw_sequence: dict[str, Any] | list[Any]) -> list[Any]:
    """Extract a likely operation list from a Fusion-style sequence object."""
    if isinstance(raw_sequence, list):
        return raw_sequence

    if not isinstance(raw_sequence, dict):
        raise UnsupportedFusion360Sequence(
            "Fusion 360 sequence must be a JSON object or list."
        )

    for key in COMMON_SEQUENCE_KEYS:
        value = raw_sequence.get(key)
        if isinstance(value, list):
            return value

    raise UnsupportedFusion360Sequence(
        "Could not find an operation list. Expected one of: "
        + ", ".join(COMMON_SEQUENCE_KEYS)
    )


def operation_kind(operation: Any) -> str:
    """Return a normalized operation kind from several common JSON shapes."""
    if isinstance(operation, str):
        return operation.lower()

    if not isinstance(operation, dict):
        return "unknown"

    for key in (
        "type",
        "operation",
        "operation_type",
        "feature_type",
        "entity",
        "name",
    ):
        value = operation.get(key)
        if isinstance(value, str):
            return value.lower()

    return "unknown"


def is_supported_operation(operation: Any) -> bool:
    """Return true for the first Fusion 360 subset we plan to convert."""
    kind = operation_kind(operation)
    return any(keyword in kind for keyword in SUPPORTED_OPERATION_KEYWORDS)


def summarize_sequence_support(
    raw_sequence: dict[str, Any] | list[Any],
) -> dict[str, Any]:
    """Summarize whether a source sequence is suitable for first-pass import."""
    operations = extract_sequence_operations(raw_sequence)
    operation_kinds = [operation_kind(operation) for operation in operations]
    unsupported_kinds = [
        kind
        for operation, kind in zip(operations, operation_kinds, strict=True)
        if not is_supported_operation(operation)
    ]

    return {
        "operation_count": len(operations),
        "operation_kinds": operation_kinds,
        "supported_operation_keywords": list(SUPPORTED_OPERATION_KEYWORDS),
        "unsupported_operation_kinds": unsupported_kinds,
        "is_supported_subset": len(operations) > 0 and not unsupported_kinds,
    }


def require_supported_sequence(raw_sequence: dict[str, Any] | list[Any]) -> None:
    """Raise a clear error if a source sequence is outside our import subset."""
    summary = summarize_sequence_support(raw_sequence)
    if summary["operation_count"] == 0:
        raise UnsupportedFusion360Sequence(
            "Fusion 360 sequence does not contain any operations."
        )

    if summary["unsupported_operation_kinds"]:
        unsupported = ", ".join(summary["unsupported_operation_kinds"])
        raise UnsupportedFusion360Sequence(
            "Only sketch/extrude Fusion 360 reconstruction sequences are "
            f"supported right now. Unsupported operation kinds: {unsupported}"
        )


def point_cloud_triples(node: dict[str, Any]) -> list[tuple[float, float, float]]:
    """Return a node point cloud as xyz triples."""
    points = node.get("points", [])
    if len(points) % 3 != 0:
        raise UnsupportedFusion360Sequence(
            "Face point cloud length must be divisible by three."
        )

    return list(zip(points[0::3], points[1::3], points[2::3], strict=True))


def point_cloud_center(
    points: list[tuple[float, float, float]],
) -> tuple[float, float, float]:
    """Return the xyz centroid of a point cloud."""
    if not points:
        raise UnsupportedFusion360Sequence("Face point cloud is empty.")

    return tuple(
        sum(point[index] for point in points) / len(points)
        for index in range(3)
    )


def point_from_fusion(point_data: dict[str, Any]) -> tuple[float, float, float]:
    """Read a Fusion Point3D-like object."""
    return (
        float(point_data["x"]),
        float(point_data["y"]),
        float(point_data["z"]),
    )


def bounding_box_dimensions_cm(sequence_data: dict[str, Any]) -> list[float]:
    """Return source bounding-box dimensions in centimeters."""
    bounding_box = sequence_data.get("properties", {}).get("bounding_box")
    if not bounding_box:
        raise UnsupportedFusion360Sequence(
            "Regraph sequence is missing properties.bounding_box."
        )

    min_point = point_from_fusion(bounding_box["min_point"])
    max_point = point_from_fusion(bounding_box["max_point"])
    return [abs(max_point[index] - min_point[index]) for index in range(3)]


def find_extrude_axis(
    sequence_step: dict[str, Any],
    graph_data: dict[str, Any],
) -> int:
    """Infer the extrude axis from start/end face centroids."""
    node_by_id = {node["id"]: node for node in graph_data.get("nodes", [])}
    start_face_id = sequence_step.get("start_face")
    end_face_id = sequence_step.get("end_face")

    if start_face_id not in node_by_id or end_face_id not in node_by_id:
        raise UnsupportedFusion360Sequence(
            "Regraph sequence start/end faces were not found in the graph."
        )

    start_center = point_cloud_center(point_cloud_triples(node_by_id[start_face_id]))
    end_center = point_cloud_center(point_cloud_triples(node_by_id[end_face_id]))
    deltas = [
        abs(end_center[index] - start_center[index])
        for index in range(3)
    ]
    axis = max(range(3), key=lambda index: deltas[index])
    if deltas[axis] == 0:
        raise UnsupportedFusion360Sequence(
            "Could not infer an extrusion direction from start/end faces."
        )

    return axis


def round_mm(value_cm: float) -> float:
    """Convert centimeters to millimeters with stable example precision."""
    return round(value_cm * CM_TO_MM, 3)


def convert_single_newbody_regraph_to_model_data(
    sequence_data: dict[str, Any],
    graph_data: dict[str, Any],
) -> dict[str, Any]:
    """Convert one simple Fusion regraph NewBody extrude into model data.

    This first converter intentionally supports only a single rectangular
    bounding-box extrusion. It is useful for source-derived examples, but it is
    not a full Fusion 360 reconstruction converter yet.
    """
    sequence_steps = sequence_data.get("sequence", [])
    if len(sequence_steps) != 1:
        raise UnsupportedFusion360Sequence(
            "Only single-step regraph sequences are supported right now."
        )

    sequence_step = sequence_steps[0]
    if sequence_step.get("operation") != "NewBodyFeatureOperation":
        raise UnsupportedFusion360Sequence(
            "Only NewBodyFeatureOperation regraph sequences can become base "
            "extrusions right now."
        )

    if any(
        node.get("surface_type") != "PlaneSurfaceType"
        for node in graph_data.get("nodes", [])
    ):
        raise UnsupportedFusion360Sequence(
            "Only all-planar single-extrude regraph solids are supported right now."
        )

    dimensions_cm = bounding_box_dimensions_cm(sequence_data)
    extrude_axis = find_extrude_axis(sequence_step, graph_data)
    sketch_dimensions_cm = [
        dimension
        for index, dimension in enumerate(dimensions_cm)
        if index != extrude_axis
    ]
    distance_cm = dimensions_cm[extrude_axis]

    if min(sketch_dimensions_cm) <= 0 or distance_cm <= 0:
        raise UnsupportedFusion360Sequence(
            "Converted rectangular extrusion dimensions must be positive."
        )

    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": round_mm(sketch_dimensions_cm[0]),
                "height": round_mm(sketch_dimensions_cm[1]),
                "distance": round_mm(distance_cm),
            }
        ]
    }
    validate_model_data(model_data)
    return model_data


def build_fusion360_example_from_regraph(
    *,
    sequence_data: dict[str, Any],
    graph_data: dict[str, Any],
    original_id: str,
    name: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Convert a simple regraph pair and wrap it as a library example."""
    model_data = convert_single_newbody_regraph_to_model_data(
        sequence_data,
        graph_data,
    )
    operation = model_data["operations"][0]
    example_name = name or "Fusion 360 single rectangular extrusion"
    example_description = description or (
        "A source-derived single rectangular prism converted from a Fusion 360 "
        "Gallery regraph face-extrusion sequence."
    )

    return build_fusion360_library_example(
        name=example_name,
        description=example_description,
        tags=[
            "fusion 360",
            "source-derived",
            "rectangle",
            "single extrude",
            "new body",
            "base extrusion",
        ],
        construction_plan=[
            "Read the Fusion 360 regraph sequence and find the single NewBody extrude.",
            "Use the start and end face centroids to infer the extrusion axis.",
            "Use the source bounding box for the rectangular sketch dimensions and extrusion distance.",
            "Convert Fusion 360 Gallery centimeters to Prompt2ParametricCAD millimeters.",
        ],
        model_data=model_data,
        original_id=original_id,
        notes=[
            "This is a conservative bounding-box conversion from regraph data, not a full raw Fusion timeline conversion.",
            (
                f"Converted dimensions: {operation['width']} mm by "
                f"{operation['height']} mm by {operation['distance']} mm."
            ),
        ],
    )

    if summary["unsupported_operation_kinds"]:
        unsupported = ", ".join(summary["unsupported_operation_kinds"])
        raise UnsupportedFusion360Sequence(
            "Only sketch/extrude Fusion 360 reconstruction sequences are "
            f"supported right now. Unsupported operation kinds: {unsupported}"
        )


def slugify_example_name(name: str) -> str:
    """Create a safe file stem for a library example name."""
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug or "fusion360_example"


def build_fusion360_library_example(
    *,
    name: str,
    description: str,
    tags: list[str],
    construction_plan: list[str],
    model_data: dict[str, Any],
    original_id: str,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    """Wrap converted model data in the retrieval library example format."""
    validate_model_data(model_data)

    return {
        "name": slugify_example_name(name),
        "description": description,
        "source_name": FUSION360_SOURCE_NAME,
        "source_url": FUSION360_SOURCE_URL,
        "source_license": FUSION360_SOURCE_LICENSE,
        "original_id": original_id,
        "derived_by": FUSION360_DERIVATION_NOTE,
        "tags": tags,
        "construction_plan": construction_plan,
        "model_data": model_data,
        "notes": notes or [],
    }


def write_library_example(
    example: dict[str, Any],
    library_dir: str | Path,
) -> Path:
    """Write a rich example JSON file using the example name as the filename."""
    library_dir = Path(library_dir)
    library_dir.mkdir(parents=True, exist_ok=True)
    output_path = library_dir / f"{slugify_example_name(example['name'])}.json"

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(example, file, indent=2)
        file.write("\n")

    return output_path
