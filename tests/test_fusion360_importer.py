"""Tests for the Fusion 360 Gallery importer scaffold."""

import json
import zipfile

import pytest

from prompt2cad.fusion360_importer import build_fusion360_example_from_regraph
from prompt2cad.fusion360_importer import FUSION360_SOURCE_LICENSE
from prompt2cad.fusion360_importer import FUSION360_SOURCE_NAME
from prompt2cad.fusion360_importer import UnsupportedFusion360Sequence
from prompt2cad.fusion360_importer import build_fusion360_library_example
from prompt2cad.fusion360_importer import convert_single_newbody_regraph_to_model_data
from prompt2cad.fusion360_importer import load_fusion360_json
from prompt2cad.fusion360_importer import load_regraph_pair_from_zip
from prompt2cad.fusion360_importer import require_supported_sequence
from prompt2cad.fusion360_importer import slugify_example_name
from prompt2cad.fusion360_importer import summarize_sequence_support
from prompt2cad.fusion360_importer import write_library_example


def test_summarize_sequence_support_accepts_sketch_extrude_subset():
    raw_sequence = {
        "timeline": [
            {"type": "Sketch"},
            {"type": "ExtrudeFeature"},
            {"operation_type": "extrude_cut"},
        ]
    }

    summary = summarize_sequence_support(raw_sequence)

    assert summary["operation_count"] == 3
    assert summary["unsupported_operation_kinds"] == []
    assert summary["is_supported_subset"] is True


def test_require_supported_sequence_rejects_other_feature_types():
    raw_sequence = {
        "operations": [
            {"type": "Sketch"},
            {"type": "FilletFeature"},
        ]
    }

    with pytest.raises(UnsupportedFusion360Sequence, match="filletfeature"):
        require_supported_sequence(raw_sequence)


def test_build_fusion360_library_example_adds_provenance():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "distance": 6,
                "width": 80,
                "height": 50,
            }
        ]
    }

    example = build_fusion360_library_example(
        name="Fusion 360 Simple Plate",
        description="A simple rectangular plate.",
        tags=["rectangle", "plate"],
        construction_plan=["Create a rectangular base extrusion."],
        model_data=model_data,
        original_id="project_file_component_id",
        notes=["First-pass manual conversion."],
    )

    assert example["name"] == "fusion_360_simple_plate"
    assert example["source_name"] == FUSION360_SOURCE_NAME
    assert example["source_license"] == FUSION360_SOURCE_LICENSE
    assert example["original_id"] == "project_file_component_id"
    assert example["model_data"] == model_data


def test_slugify_example_name_has_safe_fallback():
    assert slugify_example_name("Circular Flange!") == "circular_flange"
    assert slugify_example_name("!!!") == "fusion360_example"


def test_load_and_write_fusion360_example_json(tmp_path):
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "circle",
                "distance": 8,
                "diameter": 60,
            }
        ]
    }
    example = build_fusion360_library_example(
        name="Round Fusion Example",
        description="A simple round plate.",
        tags=["circle", "plate"],
        construction_plan=["Create a circular base extrusion."],
        model_data=model_data,
        original_id="round_source_id",
    )

    output_path = write_library_example(example, tmp_path)
    loaded = load_fusion360_json(output_path)

    assert output_path.name == "round_fusion_example.json"
    assert loaded == json.loads(output_path.read_text(encoding="utf-8"))
    assert loaded["source_name"] == FUSION360_SOURCE_NAME


def simple_regraph_sequence_and_graph():
    sequence_data = {
        "sequence": [
            {
                "start_face": "start",
                "end_face": "end",
                "operation": "NewBodyFeatureOperation",
                "graph": "simple_0000.json",
            }
        ],
        "properties": {
            "bounding_box": {
                "type": "BoundingBox3D",
                "min_point": {
                    "type": "Point3D",
                    "x": 0,
                    "y": 0,
                    "z": 0,
                },
                "max_point": {
                    "type": "Point3D",
                    "x": 3.9,
                    "y": 6.8,
                    "z": 1.0,
                },
            }
        },
    }
    graph_data = {
        "nodes": [
            {
                "id": "start",
                "surface_type": "PlaneSurfaceType",
                "points": [
                    0,
                    0,
                    0,
                    3.9,
                    0,
                    0,
                    3.9,
                    6.8,
                    0,
                    0,
                    6.8,
                    0,
                ],
            },
            {
                "id": "end",
                "surface_type": "PlaneSurfaceType",
                "points": [
                    0,
                    0,
                    1.0,
                    3.9,
                    0,
                    1.0,
                    3.9,
                    6.8,
                    1.0,
                    0,
                    6.8,
                    1.0,
                ],
            },
            {
                "id": "side_1",
                "surface_type": "PlaneSurfaceType",
                "points": [
                    0,
                    0,
                    0,
                    0,
                    0,
                    1.0,
                    0,
                    6.8,
                    1.0,
                ],
            },
        ],
        "links": [],
    }
    return sequence_data, graph_data


def test_convert_single_newbody_regraph_to_rectangle_model_data():
    sequence_data, graph_data = simple_regraph_sequence_and_graph()

    model_data = convert_single_newbody_regraph_to_model_data(
        sequence_data,
        graph_data,
    )

    assert model_data == {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 39.0,
                "height": 68.0,
                "distance": 10.0,
            }
        ]
    }


def test_convert_single_newbody_regraph_rejects_non_planar_graph():
    sequence_data, graph_data = simple_regraph_sequence_and_graph()
    graph_data["nodes"][1]["surface_type"] = "CylinderSurfaceType"

    with pytest.raises(UnsupportedFusion360Sequence, match="all-planar"):
        convert_single_newbody_regraph_to_model_data(sequence_data, graph_data)


def test_build_fusion360_example_from_regraph_wraps_conversion():
    sequence_data, graph_data = simple_regraph_sequence_and_graph()

    example = build_fusion360_example_from_regraph(
        sequence_data=sequence_data,
        graph_data=graph_data,
        original_id="fixture/simple_sequence.json",
        name="Fixture Regraph Block",
    )

    assert example["name"] == "fixture_regraph_block"
    assert example["source_name"] == FUSION360_SOURCE_NAME
    assert example["original_id"] == "fixture/simple_sequence.json"
    assert example["model_data"]["operations"][0]["distance"] == 10.0


def test_load_regraph_pair_from_zip(tmp_path):
    sequence_data, graph_data = simple_regraph_sequence_and_graph()
    zip_path = tmp_path / "regraph.zip"

    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "sample/regraph/simple_sequence.json",
            json.dumps(sequence_data),
        )
        archive.writestr(
            "sample/regraph/simple_0000.json",
            json.dumps(graph_data),
        )

    loaded_sequence, loaded_graph = load_regraph_pair_from_zip(
        zip_path,
        "sample/regraph/simple_sequence.json",
    )

    assert loaded_sequence == sequence_data
    assert loaded_graph == graph_data
