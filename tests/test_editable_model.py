from copy import deepcopy

import pytest

from prompt2cad.editable_model import EDITABLE_MODEL_FORMAT
from prompt2cad.editable_model import EDITABLE_MODEL_VERSION
from prompt2cad.editable_model import model_data_to_editable_document
from prompt2cad.editable_model import rebuild_with_parameter_updates
from prompt2cad.interpreter import build_model


def editable_model_data() -> dict:
    return {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "distance": 8,
                "width": 80,
                "height": 50,
            },
            {
                "type": "add_extrude",
                "id": "boss",
                "target": "base.top",
                "profile": "rectangle",
                "positions": [[0, 0]],
                "distance": 10,
                "width": 20,
                "height": 12,
            },
            {
                "type": "cut",
                "id": "hole",
                "target": "boss.top",
                "profile": "circle",
                "positions": [[0, 0]],
                "depth": "through",
                "diameter": 4,
            },
        ]
    }


def test_editable_document_preserves_history_supports_and_sketches():
    document = model_data_to_editable_document(editable_model_data())

    assert document.format_name == EDITABLE_MODEL_FORMAT
    assert document.format_version == EDITABLE_MODEL_VERSION
    assert document.build_order == ("base", "boss", "hole")
    assert document.parameterization_complete is True
    assert document.warnings == ()

    base, boss, hole = document.features
    assert base.build_predecessor_id is None
    assert boss.build_predecessor_id == "base"
    assert boss.parent_feature_ids == ("base",)
    assert boss.target == "base.top"
    assert boss.canonical_target == "base.face.f001"
    assert boss.support_reference["kind"] == "reference"
    assert boss.sketch["profile"] == "rectangle"
    assert boss.sketch["constraints"] == []
    assert hole.parent_feature_ids == ("boss",)

    exported = document.to_dict()
    assert exported["format"] == EDITABLE_MODEL_FORMAT
    assert exported["units"] == {"length": "mm", "angle": "deg"}
    assert exported["native_replay"] == {
        "parameterization_complete": True,
        "exporter_implemented": False,
    }


def test_editable_document_exposes_named_driving_parameters():
    document = model_data_to_editable_document(editable_model_data())

    width = document.parameter("base.sketch.width")
    boss_distance = document.parameter("boss.feature.distance")
    hole_depth = document.parameter("hole.feature.depth")
    hole_position_x = document.parameter("hole.placement.inst001.x")

    assert width.name == "Width"
    assert width.value == 80
    assert width.unit == "mm"
    assert width.source_path == ("operations", 0, "width")
    assert boss_distance.name == "Extrusion distance"
    assert boss_distance.value == 10
    assert hole_depth.value_type == "end_condition"
    assert hole_depth.value == "through"
    assert hole_position_x.value_type == "coordinate"


def test_parameter_updates_rebuild_geometry_and_preserve_feature_identity():
    source = editable_model_data()
    original_source = deepcopy(source)
    document = model_data_to_editable_document(source)

    part, updated_document = rebuild_with_parameter_updates(
        document,
        {
            "base.sketch.width": 100,
            "boss.feature.distance": 15,
        },
    )

    bounding_box = part.val().BoundingBox()
    assert bounding_box.xlen == pytest.approx(100)
    assert bounding_box.zlen == pytest.approx(23)
    assert updated_document.build_order == document.build_order
    assert updated_document.parameter("base.sketch.width").value == 100
    assert updated_document.parameter("boss.feature.distance").value == 15
    assert document.parameter("base.sketch.width").value == 80
    assert document.source_model_data == original_source
    assert source == original_source


def test_parameter_update_changes_cut_geometry():
    model_data = editable_model_data()
    original_part = build_model(model_data)
    document = model_data_to_editable_document(model_data)

    updated_part, updated_document = rebuild_with_parameter_updates(
        document,
        {"hole.sketch.diameter": 8},
    )

    assert updated_part.val().Volume() < original_part.val().Volume()
    assert updated_document.parameter("hole.sketch.diameter").value == 8


def test_failed_parameter_update_leaves_original_document_unchanged():
    document = model_data_to_editable_document(editable_model_data())

    with pytest.raises(ValueError, match="must be greater than zero"):
        rebuild_with_parameter_updates(
            document,
            {"base.sketch.width": -1},
        )

    with pytest.raises(ValueError, match="Unknown editable parameter"):
        rebuild_with_parameter_updates(document, {"base.unknown": 10})

    assert document.parameter("base.sketch.width").value == 80
    assert document.source_model_data["operations"][0]["width"] == 80


def test_geometry_failure_does_not_replace_the_known_good_document():
    document = model_data_to_editable_document(editable_model_data())

    with pytest.raises(ValueError, match="connected solid|operation-effect validation"):
        rebuild_with_parameter_updates(
            document,
            {"boss.placement.inst001.x": 100},
        )

    assert document.parameter("boss.placement.inst001.x").value == 0
    assert document.source_model_data["operations"][1]["positions"] == [[0, 0]]


def test_through_cut_can_be_changed_to_a_blind_depth():
    document = model_data_to_editable_document(editable_model_data())

    _, updated_document = rebuild_with_parameter_updates(
        document,
        {"hole.feature.depth": 5},
    )

    updated_depth = updated_document.parameter("hole.feature.depth")
    assert updated_depth.value == 5
    assert updated_depth.value_type == "end_condition"


def test_coordinate_driven_profiles_expose_points_and_report_constraint_gap():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "polyline",
                "distance": 5,
                "points": [[0, 0], [40, 0], [0, 30]],
            }
        ]
    }
    document = model_data_to_editable_document(model_data)

    assert document.parameterization_complete is False
    assert "coordinate-driven" in document.warnings[0]
    assert document.parameter("base.sketch.point002.x").value == 40

    part, updated_document = rebuild_with_parameter_updates(
        document,
        {"base.sketch.point002.x": 50},
    )

    assert part.val().BoundingBox().xlen == pytest.approx(50)
    assert updated_document.parameter("base.sketch.point002.x").value == 50


def test_multi_instance_feature_is_flagged_for_future_pattern_node():
    model_data = editable_model_data()
    model_data["operations"][2]["positions"] = [[-5, 0], [5, 0]]
    document = model_data_to_editable_document(model_data)

    hole = document.features[2]
    assert hole.parameterization_complete is False
    assert any("seed feature" in note for note in hole.representation_notes)
    assert document.parameter("hole.placement.inst002.x").value == 5


def test_revolve_exposes_axis_angle_profile_and_placement_parameters():
    model_data = {
        "operations": [
            {
                "type": "revolve",
                "id": "shaft",
                "plane": "XY",
                "profile": "rectangle",
                "positions": [[5, 0]],
                "width": 10,
                "height": 40,
                "axis_start": [0, -1],
                "axis_end": [0, 1],
                "angle": 360,
            }
        ]
    }
    document = model_data_to_editable_document(model_data)

    assert document.parameter("shaft.sketch.width").value == 10
    assert document.parameter("shaft.feature.angle").value == 360
    assert document.parameter("shaft.placement.inst001.x").value == 5
    assert document.parameter("shaft.reference.axis_start.y").value == -1
    assert document.features[0].support_reference == {
        "kind": "datum_plane",
        "name": "XY",
    }


def test_edge_treatment_preserves_reference_group_selection_recipe():
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
            },
            {
                "type": "chamfer",
                "id": "top_chamfer",
                "target": "base.top_outer_edges",
                "distance": 1,
            },
        ]
    }
    document = model_data_to_editable_document(model_data)
    chamfer = document.features[1]

    assert chamfer.parent_feature_ids == ("base",)
    assert chamfer.canonical_target == "base.edge_group.top_outer_edges"
    assert chamfer.support_reference["kind"] == "reference_group"
    assert len(chamfer.support_reference["members"]) == 4
    assert document.parameter("top_chamfer.feature.distance").name == (
        "Chamfer distance"
    )

    part, _ = rebuild_with_parameter_updates(
        document,
        {
            "base.sketch.width": 100,
            "top_chamfer.feature.distance": 0.5,
        },
    )
    assert part.val().isValid()
    assert part.val().BoundingBox().xlen == pytest.approx(100)


def test_countersink_exposes_native_hole_controls_without_a_sketch_profile():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "distance": 8,
                "width": 80,
                "height": 40,
            },
            {
                "type": "countersink",
                "id": "countersink",
                "target": "base.top",
                "positions": [[0, 0]],
                "diameter": 5,
                "countersink_diameter": 10,
                "angle": 90,
                "depth": "through",
            },
        ]
    }
    document = model_data_to_editable_document(model_data)

    assert document.features[1].sketch is None
    assert document.parameter("countersink.feature.diameter").value == 5
    assert document.parameter("countersink.feature.countersink_diameter").value == 10
    assert document.parameter("countersink.feature.angle").value == 90
    assert document.parameter("countersink.feature.depth").value == "through"
