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


def curved_side_attachment_model_data() -> dict:
    return {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "sketch",
                "distance": 8,
                "start": [-50, -35],
                "segments": [
                    {"type": "line", "to": [15, -35]},
                    {"type": "arc", "through": [50, 0], "to": [15, 35]},
                    {"type": "line", "to": [-50, 35]},
                ],
                "close": True,
            },
            {
                "type": "add_extrude",
                "id": "right_tab",
                "target": "base.right",
                "profile": "rectangle",
                "positions": [[0, 0]],
                "distance": 10,
                "width": 18,
                "height": 8,
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
        "exporter_implemented": True,
        "adapter_status": "prototype",
        "eligibility_requires_replay_planning": True,
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


def test_curved_side_attachment_is_independently_editable_without_changing_extent():
    document = model_data_to_editable_document(
        curved_side_attachment_model_data()
    )
    attachment = document.parameter("right_tab.feature.attachment_depth")

    assert attachment is not None
    assert attachment.name == "Attachment depth"
    assert 0 < attachment.value <= 10
    assert attachment.source_path == (
        "operations",
        1,
        "attachment_depth",
    )

    updated_attachment_depth = attachment.value * 2
    part, updated_document = rebuild_with_parameter_updates(
        document,
        {
            "right_tab.feature.attachment_depth": (
                updated_attachment_depth
            )
        },
    )

    bounding_box = part.val().BoundingBox()
    assert len(part.solids().vals()) == 1
    assert bounding_box.xmin == pytest.approx(-50)
    assert bounding_box.xmax == pytest.approx(60)
    assert bounding_box.xlen == pytest.approx(110)
    assert updated_document.parameter(
        "right_tab.feature.attachment_depth"
    ).value == updated_attachment_depth


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


def test_circular_pattern_controls_regenerate_derived_positions_transactionally():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "distance": 8,
                "width": 100,
                "height": 70,
            },
            {
                "type": "cut",
                "id": "holes",
                "target": "base.top",
                "profile": "circle",
                "positions": [[25, 0], [0, 25], [-25, 0], [0, -25]],
                "pattern": {
                    "type": "circular",
                    "seed_position": [25, 0],
                    "center": [0, 0],
                    "count": 4,
                    "total_angle_degrees": 360,
                },
                "depth": "through",
                "diameter": 6,
            },
        ]
    }
    document = model_data_to_editable_document(model_data)

    assert document.parameter("holes.pattern.count").value == 4
    assert document.parameter("holes.pattern.total_angle").value == 360
    assert document.parameter("holes.placement.inst001.x").source_path[-3:] == (
        "pattern",
        "seed_position",
        0,
    )
    assert document.parameter("holes.placement.inst002.x") is None

    part, updated = rebuild_with_parameter_updates(
        document,
        {
            "holes.pattern.count": 5,
            "holes.pattern.total_angle": 180,
        },
    )

    assert len(part.solids().vals()) == 1
    assert updated.parameter("holes.pattern.count").value == 5
    assert updated.source_model_data["operations"][1]["positions"] == [
        [25.0, 0.0],
        [17.67767, 17.67767],
        [0.0, 25.0],
        [-17.67767, 17.67767],
        [-25.0, 0.0],
    ]
    assert document.source_model_data["operations"][1]["positions"] == [
        [25, 0],
        [0, 25],
        [-25, 0],
        [0, -25],
    ]


def test_linear_pattern_count_and_spacing_share_one_derived_position_graph():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "distance": 8,
                "width": 120,
                "height": 80,
            },
            {
                "type": "add_extrude",
                "id": "posts",
                "target": "base.top",
                "profile": "circle",
                "positions": [[-20, -10], [0, -10], [-20, 10], [0, 10]],
                "pattern": {
                    "type": "linear",
                    "seed_position": [-20, -10],
                    "direction_1": [1, 0],
                    "count_1": 2,
                    "spacing_1": 20,
                    "direction_2": [0, 1],
                    "count_2": 2,
                    "spacing_2": 20,
                },
                "distance": 7,
                "diameter": 6,
            },
        ]
    }
    document = model_data_to_editable_document(model_data)

    part, updated = rebuild_with_parameter_updates(
        document,
        {
            "posts.pattern.count_1": 3,
            "posts.pattern.spacing_1": 15,
            "posts.pattern.count_2": 1,
            "posts.pattern.spacing_2": 0,
        },
    )

    assert len(part.solids().vals()) == 1
    assert updated.source_model_data["operations"][1]["positions"] == [
        [-20.0, -10.0],
        [-5.0, -10.0],
        [10.0, -10.0],
    ]


def test_pattern_parameter_validation_rejects_invalid_counts_and_spacing():
    model_data = {
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
                "type": "cut",
                "id": "holes",
                "target": "base.top",
                "profile": "circle",
                "positions": [[-10, 0], [10, 0]],
                "pattern": {
                    "type": "linear",
                    "seed_position": [-10, 0],
                    "direction_1": [1, 0],
                    "count_1": 2,
                    "spacing_1": 20,
                    "direction_2": [0, 1],
                    "count_2": 1,
                    "spacing_2": 0,
                },
                "depth": "through",
                "diameter": 4,
            },
        ]
    }
    document = model_data_to_editable_document(model_data)

    with pytest.raises(ValueError, match="positive integer"):
        rebuild_with_parameter_updates(
            document, {"holes.pattern.count_1": 0}
        )
    with pytest.raises(ValueError, match="cannot be negative"):
        rebuild_with_parameter_updates(
            document, {"holes.pattern.spacing_1": -1}
        )
