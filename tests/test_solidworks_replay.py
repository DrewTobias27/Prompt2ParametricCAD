from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from prompt2cad.editable_model import model_data_to_editable_document
from prompt2cad.solidworks_export import model_path_to_replay_plan
from prompt2cad.solidworks_export import materialize_stable_feature_ids
from prompt2cad.solidworks_export import save_plan
from prompt2cad.solidworks_replay import SOLIDWORKS_REPLAY_FORMAT
from prompt2cad.solidworks_replay import SOLIDWORKS_REPLAY_VERSION
from prompt2cad.solidworks_replay import SOLIDWORKS_PARITY_MATRIX
from prompt2cad.solidworks_replay import SolidWorksExecutionError
from prompt2cad.solidworks_replay import build_solidworks_replay_plan
from prompt2cad.solidworks_replay import export_solidworks_part
from prompt2cad.solidworks_replay import validate_solidworks_mutations
from prompt2cad.solidworks_replay import verify_solidworks_editability


def native_model_data() -> dict:
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
                "profile": "circle",
                "positions": [[0, 0]],
                "distance": 10,
                "diameter": 20,
            },
            {
                "type": "cut",
                "id": "hole",
                "target": "boss.top",
                "profile": "circle",
                "positions": [[0, 0]],
                "depth": "through",
                "diameter": 8,
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
                "id": "left_tab",
                "target": "base.left",
                "profile": "rectangle",
                "positions": [[0, 0]],
                "distance": 10,
                "width": 18,
                "height": 8,
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
            {
                "type": "cut",
                "id": "left_hole",
                "target": "left_tab.global_top",
                "profile": "circle",
                "positions": [[0, 0]],
                "depth": "through",
                "diameter": 6,
            },
            {
                "type": "cut",
                "id": "right_hole",
                "target": "right_tab.global_top",
                "profile": "circle",
                "positions": [[0, 0]],
                "depth": "through",
                "diameter": 6,
            },
        ]
    }


def angled_face_pattern_model_data() -> dict:
    return {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "polyline",
                "distance": 20,
                "points": [
                    [-40, -30],
                    [40, -30],
                    [25, 30],
                    [-25, 30],
                ],
            },
            {
                "type": "add_extrude",
                "id": "angled_bosses",
                "target": "base.side_face.s002",
                "profile": "circle",
                "positions": [[4, 0], [0, 4], [-4, 0], [0, -4]],
                "distance": 4,
                "diameter": 3,
                "pattern": {
                    "type": "circular",
                    "seed_position": [4, 0],
                    "center": [0, 0],
                    "count": 4,
                    "total_angle_degrees": 360,
                },
            },
        ]
    }


def replay_plan(model_data: dict | None = None):
    document = model_data_to_editable_document(model_data or native_model_data())
    return build_solidworks_replay_plan(document)


def published_reference_map(feature) -> dict[str, str]:
    return {
        reference["semantic_name"]: reference["entity_name"]
        for reference in feature.publish_references
    }


def test_replay_plan_preserves_native_history_and_named_dependencies():
    plan = replay_plan()

    assert plan.source_build_order == ("base", "boss", "hole")
    assert tuple(feature.id for feature in plan.features) == plan.source_build_order

    base, boss, hole = plan.features
    assert base.feature_name == "P2P_base"
    assert base.sketch_name == "P2P_base_Sketch"
    assert base.support == {
        "kind": "datum_plane",
        "name": "Front Plane",
        "semantic_plane": "XY",
        "frame": {
            "origin_mm": [0.0, 0.0, 0.0],
            "x_axis": [1.0, 0.0, 0.0],
            "normal": [0.0, 0.0, 1.0],
        },
    }
    assert published_reference_map(base) == {
        "top": "P2P_base_top",
        "bottom": "P2P_base_bottom",
        "front": "P2P_base_front",
        "back": "P2P_base_back",
        "left": "P2P_base_left",
        "right": "P2P_base_right",
    }
    assert boss.support["entity_name"] == "P2P_base_top"
    assert published_reference_map(boss) == {
        "top": "P2P_boss_top",
        "outer_surface": "P2P_boss_outer_surface",
    }
    assert hole.support["entity_name"] == "P2P_boss_top"
    assert hole.publish_references == ()

    top_reference = next(
        reference
        for reference in base.publish_references
        if reference["semantic_name"] == "top"
    )
    assert top_reference == {
        "reference_id": "base.top",
        "semantic_name": "top",
        "entity_name": "P2P_base_top",
        "entity_type": "face",
        "selector": {
            "kind": "planar_face_direction",
            "direction": [0.0, 0.0, 1.0],
        },
    }


def test_replay_plan_maps_sketch_and_feature_dimensions():
    plan = replay_plan().to_dict()
    base, boss, hole = plan["features"]

    assert plan["format"] == SOLIDWORKS_REPLAY_FORMAT
    assert plan["units"] == {
        "source_length": "mm",
        "solidworks_system_length": "m",
    }
    assert base["sketch"]["profile"] == "rectangle"
    assert base["sketch"]["width_mm"] == 80
    assert base["sketch"]["height_mm"] == 50
    assert [
        dimension["native_name"]
        for dimension in base["sketch"]["driving_dimensions"]
    ] == ["P2P_base_sketch_width", "P2P_base_sketch_height"]
    assert base["feature"]["kind"] == "boss_extrude"
    assert base["feature"]["depth_mm"] == 8
    assert boss["sketch"]["diameter_mm"] == 20
    assert boss["feature"]["driving_dimension"]["native_name"] == (
        "P2P_boss_feature_distance"
    )
    assert hole["feature"] == {
        "kind": "cut_extrude",
        "end_condition": "through_all",
        "depth_mm": None,
        "driving_dimension": None,
    }


def test_replay_plan_has_one_canonical_binding_for_each_named_dimension():
    plan = replay_plan().to_dict()

    for step in plan["features"]:
        legacy_dimensions = list(step["sketch"]["driving_dimensions"])
        for control in step["sketch"]["placement_controls"]:
            legacy_dimensions.extend(
                dimension
                for dimension in (
                    control["x_dimension"],
                    control["y_dimension"],
                )
                if dimension is not None
            )
        if step["feature"]["driving_dimension"] is not None:
            legacy_dimensions.append(step["feature"]["driving_dimension"])

        dimension_bindings = [
            binding
            for binding in step["parameter_bindings"]
            if binding["binding_kind"] == "named_dimension"
        ]
        assert {item["parameter_id"] for item in dimension_bindings} == {
            item["parameter_id"] for item in legacy_dimensions
        }
        assert len({item["parameter_id"] for item in step["parameter_bindings"]}) == len(
            step["parameter_bindings"]
        )


def test_countersink_controls_are_bound_to_hole_wizard_feature_data():
    model_data = native_model_data()
    model_data["operations"] = [
        model_data["operations"][0],
        {
            "type": "countersink",
            "id": "mounting_holes",
            "target": "base.top",
            "positions": [[-25, 15], [25, 15]],
            "diameter": 6,
            "countersink_diameter": 12,
            "angle": 82,
            "depth": 7,
        },
    ]

    countersink = replay_plan(model_data).features[1]
    bindings = {
        binding["parameter_id"]: binding
        for binding in countersink.parameter_bindings
    }

    assert bindings["mounting_holes.feature.diameter"]["native_properties"] == [
        "Diameter",
        "HoleDiameter",
        "ThruHoleDiameter",
    ]
    assert bindings["mounting_holes.feature.countersink_diameter"][
        "native_properties"
    ] == ["CounterSinkDiameter"]
    assert bindings["mounting_holes.feature.angle"]["unit"] == "deg"
    assert bindings["mounting_holes.feature.depth"]["value"] == 7
    assert bindings["mounting_holes.placement.inst001.x"]["value"] == 25
    assert bindings["mounting_holes.placement.inst001.y"]["value"] == 15
    assert bindings["mounting_holes.placement.inst002.x"]["value"] == 25
    assert bindings["mounting_holes.placement.inst002.y"]["value"] == 15
    assert all(
        bindings[parameter_id]["binding_kind"] == "feature_property"
        for parameter_id in (
            "mounting_holes.feature.diameter",
            "mounting_holes.feature.countersink_diameter",
            "mounting_holes.feature.angle",
            "mounting_holes.feature.depth",
        )
    )


def test_patterned_countersink_seed_has_native_placement_bindings():
    model_data = native_model_data()
    model_data["operations"] = [
        model_data["operations"][0],
        {
            "type": "countersink",
            "id": "mounting_holes",
            "target": "base.top",
            "positions": [[20, 0], [0, 20], [-20, 0], [0, -20]],
            "pattern": {
                "type": "circular",
                "seed_position": [20, 0],
                "center": [0, 0],
                "count": 4,
                "total_angle_degrees": 360,
            },
            "diameter": 6,
            "countersink_diameter": 12,
            "angle": 82,
            "depth": "through",
        },
    ]

    countersink = replay_plan(model_data).features[1]
    binding_ids = {
        binding["parameter_id"] for binding in countersink.parameter_bindings
    }

    assert countersink.sketch["positions_mm"] == [[20.0, 0.0]]
    assert len(countersink.sketch["placement_controls"]) == 1
    assert "mounting_holes.placement.inst001.x" in binding_ids
    assert "mounting_holes.placement.inst001.y" not in binding_ids
    assert "mounting_holes.pattern.count" in binding_ids
    assert "mounting_holes.pattern.total_angle" in binding_ids


def test_native_hole_wizard_selects_only_source_position_points():
    runner_source = (
        Path(__file__).parents[1]
        / "src"
        / "prompt2cad"
        / "solidworks_replay_runner.cs"
    ).read_text(encoding="utf-8")

    assert "FeaturePoints = featurePoints" in runner_source
    assert "nativeSketch.FeaturePoints ?? new SketchPoint[0]" in runner_source
    countersink_section = runner_source[
        runner_source.index("private static Feature CreateNativeCountersink") :
        runner_source.index("private static void ConfigureFeatureDrivingDimension")
    ]
    assert "GetSketchPoints2" not in countersink_section


@pytest.mark.parametrize(
    ("pattern", "positions", "expected_properties"),
    [
        (
            {
                "type": "circular",
                "seed_position": [20, 0],
                "center": [0, 0],
                "count": 4,
                "total_angle_degrees": 360,
            },
            [[20, 0], [0, 20], [-20, 0], [0, -20]],
            {"TotalInstances", "Spacing"},
        ),
        (
            {
                "type": "linear",
                "seed_position": [-20, -10],
                "direction_1": [1, 0],
                "count_1": 3,
                "spacing_1": 20,
                "direction_2": [0, 1],
                "count_2": 2,
                "spacing_2": 20,
            },
            [
                [-20, -10],
                [0, -10],
                [20, -10],
                [-20, 10],
                [0, 10],
                [20, 10],
            ],
            {"D1TotalInstances", "D1Spacing", "D2TotalInstances", "D2Spacing"},
        ),
    ],
)
def test_native_pattern_controls_have_editable_feature_property_bindings(
    pattern,
    positions,
    expected_properties,
):
    model_data = native_model_data()
    model_data["operations"] = model_data["operations"][:2]
    model_data["operations"][1] = {
        "type": "cut",
        "id": "boss",
        "target": "base.top",
        "profile": "circle",
        "positions": positions,
        "pattern": pattern,
        "diameter": 6,
        "depth": "through",
    }

    step = replay_plan(model_data).features[1]
    pattern_bindings = [
        binding
        for binding in step.parameter_bindings
        if binding["owner_kind"] == "pattern"
    ]

    assert {binding["native_properties"][0] for binding in pattern_bindings} == (
        expected_properties
    )
    assert {binding["owner_name"] for binding in pattern_bindings} == {
        "P2P_boss"
    }
    assert all(
        binding["binding_kind"] == "feature_property"
        for binding in pattern_bindings
    )
    assert all("minimum_value" in binding for binding in pattern_bindings)
    assert all(
        binding["integer_only"]
        for binding in pattern_bindings
        if binding["unit"] == "count"
    )
    document = model_data_to_editable_document(model_data)
    assert {
        binding["parameter_id"] for binding in pattern_bindings
    } <= {
        parameter.id
        for feature in document.features
        for parameter in feature.parameters
    }


def test_replay_plan_maps_stable_profile_placement_controls():
    model_data = native_model_data()
    model_data["operations"][1]["positions"] = [[-12, 7]]

    boss = replay_plan(model_data).features[1]
    control = boss.sketch["placement_controls"][0]

    assert control["instance_index"] == 1
    assert control["position_mm"] == [-12.0, 7.0]
    assert control["x_dimension"] == {
        "parameter_id": "boss.placement.inst001.x",
        "native_name": "P2P_boss_placement_inst001_x",
        "value_mm": 12.0,
        "unit": "mm",
        "mutation_mode": "absolute_same_side",
        "source_value": -12.0,
    }
    assert control["y_dimension"] == {
        "parameter_id": "boss.placement.inst001.y",
        "native_name": "P2P_boss_placement_inst001_y",
        "value_mm": 7.0,
        "unit": "mm",
        "mutation_mode": "absolute_same_side",
        "source_value": 7.0,
    }

    bindings = {
        binding["parameter_id"]: binding
        for binding in boss.parameter_bindings
    }
    assert bindings["boss.placement.inst001.x"]["mutation_mode"] == (
        "absolute_same_side"
    )
    assert bindings["boss.placement.inst001.x"]["source_value"] == -12.0


def test_centered_profile_uses_relations_without_zero_dimensions():
    boss = replay_plan().features[1]

    assert boss.sketch["placement_controls"] == [
        {
            "instance_index": 1,
            "position_mm": [0.0, 0.0],
            "x_dimension": None,
            "y_dimension": None,
        }
    ]


def test_blind_cut_preserves_a_named_native_depth():
    model_data = native_model_data()
    model_data["operations"][2]["depth"] = 4

    hole = replay_plan(model_data).features[2]

    assert hole.feature["end_condition"] == "blind"
    assert hole.feature["depth_mm"] == 4
    assert hole.feature["driving_dimension"] == {
        "parameter_id": "hole.feature.depth",
        "native_name": "P2P_hole_feature_depth",
        "value_mm": 4.0,
        "unit": "mm",
    }


def test_replay_preserves_exact_curved_side_attachment_and_global_top_holes():
    plan = replay_plan(curved_side_attachment_model_data())
    _, left_tab, right_tab, left_hole, right_hole = plan.features

    assert left_tab.support == {
        "kind": "offset_plane",
        "name": "P2P_left_tab_SupportPlane",
        "datum_name": "Right Plane",
        "semantic_plane": "YZ",
        "parent_feature_id": "base",
        "reference": "left",
        "offset_mm": 50.0,
        "flip_offset": True,
        "reverse_direction": True,
        "frame": {
            "origin_mm": [-50.0, 0.0, 4.0],
            "x_axis": [0.0, 1.0, 0.0],
            "normal": [-1.0, 0.0, 0.0],
        },
    }
    assert right_tab.support["kind"] == "offset_plane"
    assert right_tab.support["name"] == "P2P_right_tab_SupportPlane"
    assert right_tab.support["datum_name"] == "Right Plane"
    assert right_tab.support["offset_mm"] == 50
    assert right_tab.support["flip_offset"] is False
    assert right_tab.support["reverse_direction"] is False
    assert right_tab.feature["depth_mm"] == 10
    reverse_depth = right_tab.feature["reverse_depth_mm"]
    assert 0 < reverse_depth <= right_tab.feature["depth_mm"]
    assert right_tab.feature["reverse_driving_dimension"] == {
        "parameter_id": "right_tab.feature.attachment_depth",
        "native_name": "P2P_right_tab_feature_attachment_depth",
        "value_mm": reverse_depth,
        "unit": "mm",
    }
    assert {
        binding["parameter_id"]
        for binding in right_tab.parameter_bindings
    } >= {
        "right_tab.feature.distance",
        "right_tab.feature.attachment_depth",
    }
    assert {
        reference["semantic_name"]
        for reference in left_tab.publish_references
    }.isdisjoint({"front", "back"})
    assert {
        reference["semantic_name"]
        for reference in right_tab.publish_references
    }.isdisjoint({"front", "back"})
    assert left_hole.support["entity_name"] == "P2P_base_top"
    assert right_hole.support["entity_name"] == "P2P_base_top"


def test_virtual_curved_side_cut_points_inward_from_offset_plane():
    model_data = curved_side_attachment_model_data()
    model_data["operations"] = [
        model_data["operations"][0],
        {
            "type": "cut",
            "id": "side_hole",
            "target": "base.right",
            "profile": "circle",
            "positions": [[0, 0]],
            "depth": "through",
            "diameter": 6,
        },
    ]

    side_hole = replay_plan(model_data).features[1]

    assert side_hole.support["kind"] == "offset_plane"
    assert side_hole.support["offset_mm"] == 50
    assert side_hole.support["reverse_direction"] is True


def test_replay_supports_revolves_and_coordinate_profiles():
    revolved = replay_plan(
        {
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
    ).features[0]
    assert revolved.feature["kind"] == "boss_revolve"
    assert revolved.feature["angle_deg"] == 360
    assert revolved.feature["axis_start_mm"] == [0.0, -1.0]
    assert revolved.feature["canonical_axis"] == {
        "kind": "canonical_line_2d",
        "anchor_mm": [0.0, 0.0],
        "direction": [0.0, 1.0],
        "normal": [-1.0, 0.0],
        "signed_offset_mm": 0.0,
        "direction_angle_deg": 90.0,
        "automated_mutation": False,
        "edit_strategy": "edit_native_construction_line_or_regenerate",
    }
    assert published_reference_map(revolved)["front"] == "P2P_shaft_front"

    polyline = replay_plan(
        {
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
    ).features[0]
    assert polyline.sketch["points_mm"] == [
        [0.0, 0.0],
        [40.0, 0.0],
        [0.0, 30.0],
    ]
    assert polyline.sketch["placement_controls"][0]["position_mm"] == [0.0, 0.0]
    assert [
        control["position_mm"]
        for control in polyline.sketch["coordinate_controls"]
    ] == [[0.0, 0.0], [40.0, 0.0], [0.0, 30.0]]
    binding_ids = {
        binding["parameter_id"] for binding in polyline.parameter_bindings
    }
    assert "base.sketch.point002.x" in binding_ids
    assert "base.sketch.point003.y" in binding_ids


def test_general_sketch_arc_control_points_use_shared_parameter_ids():
    model_data = {
        "operations": [
            {
                "type": "revolve",
                "id": "curved_base",
                "plane": "XY",
                "profile": "sketch",
                "positions": [[30, -3]],
                "start": [0, -10],
                "segments": [
                    {"type": "line", "to": [20, -10]},
                    {
                        "type": "arc",
                        "through": [28, 0],
                        "to": [20, 10],
                    },
                    {"type": "line", "to": [0, 10]},
                ],
                "close": True,
                "axis_start": [0, -20],
                "axis_end": [0, 20],
                "angle": 180,
            }
        ]
    }

    feature = replay_plan(model_data).features[0]
    controls = feature.sketch["coordinate_controls"]
    arc_control = next(
        control for control in controls if control["kind"] == "arc_through"
    )
    assert arc_control["segment_index"] == 2
    assert arc_control["position_mm"] == [28.0, 0.0]
    assert arc_control["x_dimension"]["parameter_id"] == (
        "curved_base.sketch.segment002.through.x"
    )
    binding_ids = {
        binding["parameter_id"] for binding in feature.parameter_bindings
    }
    assert "curved_base.placement.inst001.x" in binding_ids
    assert "curved_base.placement.inst001.y" in binding_ids
    assert "curved_base.sketch.start.y" in binding_ids
    assert "curved_base.sketch.segment002.through.x" in binding_ids
    assert "curved_base.sketch.segment002.to.y" in binding_ids


@pytest.mark.parametrize(
    "example_name",
    [
        "polygon_base_polygon_cut.json",
        "polyline_base_rectangular_cut.json",
        "solidworks_smoke_arc_revolve.json",
        "solidworks_smoke_patterned_plate.json",
    ],
)
def test_every_native_sketch_has_a_general_constraint_completion_plan(
    example_name,
):
    example_path = Path(__file__).parents[1] / "examples" / "models" / example_name
    plan = model_path_to_replay_plan(example_path)

    for step in plan.features:
        if step.sketch is None:
            continue
        constraint_plan = step.sketch["constraint_plan"]
        assert constraint_plan["strategy"] == (
            "complete_remaining_degrees_of_freedom"
        )
        assert constraint_plan["require_fully_defined"] is True
        assert constraint_plan["source_feature_id"] == step.id
        assert {
            "coincident",
            "horizontal",
            "vertical",
            "tangent",
        }.issubset(constraint_plan["relations"])


def test_replay_only_publishes_revolve_faces_that_exist():
    model_data = json.loads(
        (
            Path(__file__).parents[1]
            / "examples"
            / "models"
            / "solidworks_smoke_arc_revolve.json"
        ).read_text(encoding="utf-8")
    )

    capsule = replay_plan(model_data).features[0]

    assert published_reference_map(capsule) == {
        "outer_surface": "P2P_capsule_outer_surface"
    }
    assert capsule.publish_references[0]["selector"] == {
        "kind": "largest_non_planar_face"
    }


def test_replay_maps_the_source_xy_datum_plane():
    model_data = native_model_data()
    model_data["operations"] = [model_data["operations"][0]]

    base = replay_plan(model_data).features[0]

    assert base.support["name"] == "Front Plane"
    assert base.support["frame"]["normal"] == [0.0, 0.0, 1.0]


def test_replay_preserves_general_sketch_profiles_and_revolve_controls():
    model_data = {
        "operations": [
            {
                "type": "revolve",
                "id": "shaft",
                "plane": "XY",
                "profile": "sketch",
                "positions": [[12, -4]],
                "start": [0, -20],
                "segments": [
                    {"type": "line", "to": [8, -20]},
                    {"type": "arc", "through": [12, 0], "to": [8, 20]},
                    {"type": "line", "to": [0, 20]},
                ],
                "close": True,
                "axis_start": [0, -20],
                "axis_end": [0, 20],
                "angle": 225,
            }
        ]
    }

    shaft = replay_plan(model_data).features[0]

    assert shaft.support["semantic_plane"] == "XY"
    assert shaft.sketch["profile"] == "sketch"
    assert shaft.sketch["positions_mm"] == [[12.0, -4.0]]
    assert shaft.sketch["segments"][1]["type"] == "arc"
    assert shaft.feature["axis_start_mm"] == [0.0, -20.0]
    assert shaft.feature["axis_end_mm"] == [0.0, 20.0]
    assert shaft.feature["angle_deg"] == 225
    assert shaft.feature["driving_dimension"]["unit"] == "deg"


def test_canonical_revolve_axis_is_endpoint_order_and_span_independent():
    from prompt2cad.solidworks_replay import _canonical_revolve_axis

    forward = _canonical_revolve_axis([3, -2], [7, 6])
    reversed_axis = _canonical_revolve_axis([7, 6], [3, -2])
    shifted_and_extended = _canonical_revolve_axis([1, -6], [9, 10])

    assert reversed_axis == pytest.approx(forward)
    assert shifted_and_extended == pytest.approx(forward)


def test_replay_preserves_additive_and_subtractive_revolve_build_order():
    model_data = {
        "operations": [
            {
                "type": "revolve",
                "id": "shaft",
                "plane": "XY",
                "profile": "rectangle",
                "positions": [[5, 0]],
                "width": 10,
                "height": 60,
                "axis_start": [0, -1],
                "axis_end": [0, 1],
                "angle": 360,
            },
            {
                "type": "add_revolve",
                "id": "collar",
                "plane": "XY",
                "profile": "rectangle",
                "positions": [[8, 0]],
                "width": 6,
                "height": 12,
                "axis_start": [0, -1],
                "axis_end": [0, 1],
                "angle": 360,
            },
            {
                "type": "cut_revolve",
                "id": "groove",
                "plane": "XY",
                "profile": "rectangle",
                "positions": [[10, 0]],
                "width": 2,
                "height": 8,
                "axis_start": [0, -1],
                "axis_end": [0, 1],
                "angle": 180,
            },
        ]
    }

    shaft, collar, groove = replay_plan(model_data).features

    assert shaft.feature["kind"] == "boss_revolve"
    assert shaft.feature["merge_result"] is False
    assert collar.feature["kind"] == "boss_revolve"
    assert collar.feature["merge_result"] is True
    assert groove.feature["kind"] == "cut_revolve"
    assert groove.feature["angle_deg"] == 180


def test_replay_preserves_polygon_patterns_as_exact_sketch_instances():
    model_data = native_model_data()
    model_data["operations"][1] = {
        "type": "add_extrude",
        "id": "hex_posts",
        "target": "base.top",
        "profile": "polygon",
        "positions": [[-20, -10], [20, -10], [0, 15]],
        "distance": 12,
        "diameter": 10,
        "sides": 6,
    }
    model_data["operations"] = model_data["operations"][:2]

    pattern = replay_plan(model_data).features[1]

    assert pattern.sketch["profile"] == "polygon"
    assert pattern.sketch["positions_mm"] == [
        [-20.0, -10.0],
        [20.0, -10.0],
        [0.0, 15.0],
    ]
    assert pattern.sketch["diameter_mm"] == 10
    assert pattern.sketch["sides"] == 6


@pytest.mark.parametrize(
    ("pattern", "expected_kind", "expected_seed"),
    [
        (
            {
                "type": "circular",
                "seed_position": [20, 0],
                "center": [0, 0],
                "count": 4,
                "total_angle_degrees": 360,
            },
            "circular_pattern",
            [20.0, 0.0],
        ),
        (
            {
                "type": "linear",
                "seed_position": [-20, -10],
                "direction_1": [1, 0],
                "count_1": 3,
                "spacing_1": 20,
                "direction_2": [0, 1],
                "count_2": 2,
                "spacing_2": 20,
            },
            "linear_pattern",
            [-20.0, -10.0],
        ),
        (
            {
                "type": "mirror",
                "seed_position": [20, 10],
                "axes": ["x", "y"],
            },
            "mirror_pattern",
            [20.0, 10.0],
        ),
    ],
)
def test_replay_separates_native_pattern_seed_from_pattern_feature(
    pattern,
    expected_kind,
    expected_seed,
):
    positions_by_kind = {
        "circular_pattern": [[20, 0], [0, 20], [-20, 0], [0, -20]],
        "linear_pattern": [
            [-20, -10],
            [0, -10],
            [20, -10],
            [-20, 10],
            [0, 10],
            [20, 10],
        ],
        "mirror_pattern": [[20, 10], [20, -10], [-20, 10], [-20, -10]],
    }
    model_data = native_model_data()
    model_data["operations"] = model_data["operations"][:2]
    model_data["operations"][1].update(
        {
            "positions": positions_by_kind[expected_kind],
            "pattern": pattern,
            "diameter": 8,
        }
    )

    native_pattern = replay_plan(model_data).features[1]

    assert native_pattern.pattern["kind"] == expected_kind
    assert native_pattern.pattern["seed_feature_name"] == "P2P_boss_Seed"
    if expected_kind in {"circular_pattern", "linear_pattern"}:
        assert native_pattern.pattern["reference_sketch_name"] == (
            "P2P_boss_References"
        )
    if expected_kind == "circular_pattern":
        assert native_pattern.pattern["axis_name"] == "P2P_boss_Axis"
    if expected_kind == "mirror_pattern":
        assert native_pattern.pattern["placement_sketch_name"] == (
            "P2P_boss_MirrorPositions"
        )
    assert native_pattern.sketch["positions_mm"] == [expected_seed]
    assert native_pattern.pattern["positions_mm"] == [
        [float(value) for value in position]
        for position in positions_by_kind[expected_kind]
    ]


def test_replay_rejects_pattern_metadata_that_disagrees_with_positions():
    model_data = native_model_data()
    model_data["operations"] = model_data["operations"][:2]
    model_data["operations"][1]["positions"] = [[20, 0], [-20, 0]]
    model_data["operations"][1]["pattern"] = {
        "type": "circular",
        "seed_position": [20, 0],
        "center": [0, 0],
        "count": 3,
        "total_angle_degrees": 360,
    }

    with pytest.raises(ValueError, match="count must match"):
        replay_plan(model_data)


def test_replay_avoids_case_insensitive_helper_name_collisions():
    model_data = native_model_data()
    model_data["operations"] = model_data["operations"][:2]
    model_data["operations"][1]["id"] = "BASE_SKETCH"

    plan = replay_plan(model_data)
    native_names = [
        name
        for feature in plan.features
        for name in (
            feature.feature_name,
            feature.sketch_name,
            *(
                [feature.pattern["seed_feature_name"]]
                if feature.pattern is not None
                else []
            ),
        )
        if name
    ]

    assert len({name.casefold() for name in native_names}) == len(native_names)
    assert plan.features[1].feature_name.startswith("P2P_BASE_SKETCH_")


def test_replay_supports_non_centered_and_multi_instance_sketches():
    non_centered = native_model_data()
    non_centered["operations"][1]["positions"] = [[10, 0]]
    assert replay_plan(non_centered).features[1].sketch["positions_mm"] == [
        [10.0, 0.0]
    ]

    multi_instance = native_model_data()
    multi_instance["operations"][2]["positions"] = [[-4, 0], [4, 0]]
    assert replay_plan(multi_instance).features[2].sketch["positions_mm"] == [
        [-4.0, 0.0],
        [4.0, 0.0],
    ]


def test_replay_resolves_a_named_face_on_one_pattern_instance():
    model_data = native_model_data()
    model_data["operations"][1].update(
        {
            "positions": [[-15, 0], [15, 0]],
            "diameter": 10,
            "pattern": {
                "type": "linear",
                "seed_position": [-15, 0],
                "direction_1": [1, 0],
                "count_1": 2,
                "spacing_1": 30,
                "direction_2": [0, 1],
                "count_2": 1,
                "spacing_2": 0,
            },
        }
    )
    model_data["operations"][2]["target"] = "boss.inst002.top"

    hole = replay_plan(model_data).features[2]

    assert hole.support["kind"] == "resolved_feature_face"
    assert hole.support["target_feature_name"] == "P2P_boss"
    assert hole.support["entity_name"] == "P2P_boss_inst002_top"
    assert hole.support["frame"]["origin_mm"] == [15.0, 0.0, 18.0]


def test_replay_materializes_missing_stable_feature_ids():
    model_data = native_model_data()
    del model_data["operations"][2]["id"]

    generated = replay_plan(model_data).features[2]
    assert generated.id == "cut_3"
    assert generated.feature_name == "P2P_cut_3"

    normalized = materialize_stable_feature_ids(model_data)
    assert normalized["operations"][2]["id"] == "cut_3"
    assert "id" not in model_data["operations"][2]


def test_generated_feature_ids_do_not_collide_with_explicit_ids():
    model_data = native_model_data()
    model_data["operations"][1]["id"] = "cut_3"
    del model_data["operations"][2]["id"]

    normalized = materialize_stable_feature_ids(model_data)

    assert normalized["operations"][1]["id"] == "cut_3"
    assert normalized["operations"][2]["id"] == "cut_3_2"


def test_replay_supports_named_side_face_frames():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "distance": 20,
                "width": 80,
                "height": 50,
            },
            {
                "type": "cut",
                "id": "front_hole",
                "target": "base.front",
                "profile": "circle",
                "positions": [[0, 0]],
                "depth": "through",
                "diameter": 8,
            },
        ]
    }

    front_hole = replay_plan(model_data).features[1]
    assert front_hole.support == {
        "kind": "named_face",
        "parent_feature_id": "base",
        "reference": "front",
        "entity_name": "P2P_base_front",
        "frame": {
            "origin_mm": [0.0, 25.0, 10.0],
            "x_axis": [1.0, 0.0, 0.0],
            "normal": [0.0, 1.0, 0.0],
        },
    }


def test_replay_patterns_features_on_an_arbitrarily_angled_planar_face():
    document = model_data_to_editable_document(angled_face_pattern_model_data())
    plan = build_solidworks_replay_plan(document)

    base, bosses = plan.features
    actual_side = next(
        reference
        for reference in base.publish_references
        if reference["semantic_name"] == "side_face.s002"
    )
    assert actual_side["selector"]["kind"] == "planar_face_geometry"
    assert actual_side["selector"]["direction"] == pytest.approx(
        [0.970143, 0.242536, 0],
        abs=1e-6,
    )
    assert actual_side["selector"]["center_mm"] == pytest.approx(
        [32.5, 0, 10]
    )
    assert bosses.support["kind"] == "named_face"
    assert bosses.support["entity_name"] == "P2P_base_side_face_s002"
    assert bosses.pattern["kind"] == "circular_pattern"
    assert bosses.support["frame"]["normal"] == pytest.approx(
        [0.970143, 0.242536, 0],
        abs=1e-6,
    )


def test_replay_maps_countersink_to_native_hole_wizard_controls():
    model_data = native_model_data()
    model_data["operations"] = [
        model_data["operations"][0],
        {
            "type": "countersink",
            "id": "mounting_holes",
            "target": "base.top",
            "positions": [[-25, 15], [25, 15], [-25, -15], [25, -15]],
            "diameter": 6,
            "countersink_diameter": 12,
            "angle": 82,
            "depth": "through",
        },
    ]

    countersink = replay_plan(model_data).features[1]

    assert countersink.feature["kind"] == "countersink"
    assert countersink.feature["end_condition"] == "through_all"
    assert countersink.feature["hole_diameter_mm"] == 6
    assert countersink.feature["countersink_diameter_mm"] == 12
    assert countersink.feature["countersink_angle_deg"] == 82
    assert countersink.sketch["profile"] == "points"
    assert len(countersink.sketch["positions_mm"]) == 4


@pytest.mark.parametrize(
    ("operation_type", "dimension_key", "value", "native_kind"),
    [
        ("chamfer", "distance", 2, "edge_chamfer"),
        ("fillet", "radius", 3, "edge_fillet"),
    ],
)
def test_replay_maps_topology_aware_edge_treatments(
    operation_type,
    dimension_key,
    value,
    native_kind,
):
    model_data = native_model_data()
    model_data["operations"] = [
        model_data["operations"][0],
        {
            "type": operation_type,
            "id": f"base_{operation_type}",
            "target": "base.top_outer_edges",
            dimension_key: value,
        },
    ]

    treatment = replay_plan(model_data).features[1]

    assert treatment.sketch is None
    assert treatment.sketch_name is None
    assert treatment.feature["kind"] == native_kind
    assert treatment.feature[f"{dimension_key}_mm"] == value
    assert treatment.support["target_feature_name"] == "P2P_base"
    assert treatment.support["selector"] == "top_outer_edges"
    assert treatment.support["frame"]["normal"] == [0.0, 0.0, 1.0]
    members = treatment.support["members"]
    assert len(members) == 4
    assert {member["reference_id"] for member in members} == {
        "base.edge.e001",
        "base.edge.e002",
        "base.edge.e003",
        "base.edge.e004",
    }
    assert all(len(member["center_mm"]) == 3 for member in members)
    assert all(len(member["bounding_box_mm"]) == 6 for member in members)


def test_solidworks_parity_matrix_covers_every_step_operation_type():
    assert set(SOLIDWORKS_PARITY_MATRIX) == {
        "extrude",
        "add_extrude",
        "cut",
        "revolve",
        "add_revolve",
        "cut_revolve",
        "countersink",
        "chamfer",
        "fillet",
    }


def test_native_polygon_uses_the_same_positive_x_phase_as_cadquery():
    runner_source = (
        Path(__file__).parents[1]
        / "src"
        / "prompt2cad"
        / "solidworks_replay_runner.cs"
    ).read_text(encoding="utf-8")
    polygon_section = runner_source[
        runner_source.index('if (sketch.Profile == "polygon")') :
        runner_source.index('if (sketch.Profile == "polyline")')
    ]

    assert "sketchManager.CreatePolygon(" in polygon_section
    assert "seedCenter[0] + radius, seedCenter[1]" in polygon_section
    assert "matching CadQuery's polygon diameter" in polygon_section
    assert "false\n                );" in polygon_section
    assert "FindPolygonConstructionCircle(polygonSketch)" in polygon_section
    assert "(Math.PI / 2.0)" not in polygon_section


def test_polygon_diameter_has_a_native_edit_binding():
    model_data = native_model_data()
    model_data["operations"][1] = {
        "type": "add_extrude",
        "id": "hex_boss",
        "target": "base.top",
        "profile": "polygon",
        "positions": [[0, 0]],
        "distance": 12,
        "diameter": 18,
        "sides": 6,
    }
    model_data["operations"] = model_data["operations"][:2]

    polygon = replay_plan(model_data).features[1]
    binding_ids = {
        binding["parameter_id"] for binding in polygon.parameter_bindings
    }

    assert polygon.sketch["driving_dimensions"] == [
        {
            "parameter_id": "hex_boss.sketch.diameter",
            "native_name": "P2P_hex_boss_sketch_diameter",
            "value_mm": 18.0,
            "unit": "mm",
        }
    ]
    assert "hex_boss.sketch.diameter" in binding_ids
    assert "hex_boss.sketch.sides" not in binding_ids


def test_native_edge_matching_has_a_cardinality_guarded_semantic_fallback():
    runner_source = (
        Path(__file__).parents[1]
        / "src"
        / "prompt2cad"
        / "solidworks_replay_runner.cs"
    ).read_text(encoding="utf-8")

    assert "semanticEdges.Count != step.Support.Members.Length" in runner_source
    assert "Canonical curve descriptors differed across kernels" in runner_source


@pytest.mark.parametrize("profile", ["polyline", "sketch"])
def test_merged_freeform_extrusion_does_not_publish_consumed_bottom_face(
    profile,
):
    profile_fields = (
        {
            "points": [[-8, -5], [8, -5], [7, 5], [-7, 5]],
        }
        if profile == "polyline"
        else {
            "start": [-8, -5],
            "segments": [
                {"type": "line", "to": [8, -5]},
                {"type": "line", "to": [8, 5]},
                {"type": "line", "to": [-8, 5]},
            ],
            "close": True,
        }
    )
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 60,
                "height": 40,
                "distance": 8,
            },
            {
                "type": "add_extrude",
                "id": "boss",
                "target": "base.top",
                "profile": profile,
                "positions": [[0, 0]],
                "distance": 6,
                **profile_fields,
            },
        ]
    }

    plan = replay_plan(model_data)
    published = {
        item["semantic_name"] for item in plan.features[1].publish_references
    }

    assert "top" in published
    assert "bottom" not in published


def test_native_runner_accepts_the_current_replay_plan_version():
    runner_source = (
        Path(__file__).parents[1]
        / "src"
        / "prompt2cad"
        / "solidworks_replay_runner.cs"
    ).read_text(encoding="utf-8")

    assert (
        f"private const int ReplayVersion = {SOLIDWORKS_REPLAY_VERSION};"
        in runner_source
    )
    assert "plan.Version != ReplayVersion" in runner_source
    assert 'DataMember(Name = "canonical_axis")' in runner_source
    assert "ValidateCanonicalRevolveAxis(step)" in runner_source
    assert "ValidatePlanFile(string planPath)" in runner_source
    assert 'DataMember(Name = "reference_sketch_name")' in runner_source
    assert 'DataMember(Name = "axis_name")' in runner_source
    assert 'DataMember(Name = "placement_sketch_name")' in runner_source
    assert "RequireUniqueValue(nativeNames" in runner_source
    assert "step.Pattern.ReferenceSketchName" in runner_source
    assert "step.Pattern.AxisName" in runner_source
    assert "step.Pattern.PlacementSketchName" in runner_source
    assert 'DataMember(Name = "surface_area_mm2")' in runner_source
    assert 'DataMember(Name = "center_of_mass_mm")' in runner_source


def test_native_runner_replays_offset_planes_and_reverse_attachment_depths():
    runner_source = (
        Path(__file__).parents[1]
        / "src"
        / "prompt2cad"
        / "solidworks_replay_runner.cs"
    ).read_text(encoding="utf-8")

    assert 'DataMember(Name = "reverse_depth_mm")' in runner_source
    assert 'DataMember(Name = "reverse_driving_dimension")' in runner_source
    assert 'if (support.Kind == "offset_plane")' in runner_source
    assert (
        "SelectOrCreateOffsetPlane(application, model, support)"
        in runner_source
    )
    assert "ValidateOffsetPlaneTransform(" in runner_source
    assert "model.FeatureManager.InsertRefPlane(" in runner_source
    assert "swRefPlaneReferenceConstraint_Distance" in runner_source
    assert "swRefPlaneReferenceConstraint_OptionFlip" in runner_source
    assert "bool singleEnded = !step.Feature.ReverseDepthMillimeters.HasValue" in (
        runner_source
    )
    assert "depth, reverseDepth" in runner_source
    assert 'step.FeatureName,\n                "D2"' in runner_source


def test_powershell_runner_discovers_solidworks_without_one_fixed_install_path():
    script_source = (
        Path(__file__).parents[1]
        / "src"
        / "prompt2cad"
        / "solidworks_replay.ps1"
    ).read_text(encoding="utf-8")

    assert "function Resolve-SolidWorksRoot" in script_source
    assert "$env:P2P_SOLIDWORKS_ROOT" in script_source
    assert "HKLM:\\SOFTWARE\\SolidWorks" in script_source
    assert '"SolidWorks Folder"' in script_source
    assert "Could not locate a SolidWorks API installation" in script_source


def test_native_runner_reports_feature_errors_and_sketch_constraint_status():
    runner_source = (
        Path(__file__).parents[1]
        / "src"
        / "prompt2cad"
        / "solidworks_replay_runner.cs"
    ).read_text(encoding="utf-8")

    assert "InspectNativeHealth(model, plan)" in runner_source
    assert "GetErrorCode2(out isWarning)" in runner_source
    assert "GetConstrainedStatus()" in runner_source
    assert 'return "under_defined"' in runner_source
    assert "FeatureErrorCount > 0" in runner_source


def test_native_runner_completes_remaining_sketch_degrees_of_freedom():
    runner_source = (
        Path(__file__).parents[1]
        / "src"
        / "prompt2cad"
        / "solidworks_replay_runner.cs"
    ).read_text(encoding="utf-8")

    assert "CompleteRemainingSketchDefinition(" in runner_source
    assert "sketchManager.FullyDefineSketch(" in runner_source
    assert "FullyDefineRelationValue(relation)" in runner_source
    assert '"Point1@Origin"' in runner_source
    assert "horizontalDatumMark | verticalDatumMark" in runner_source
    assert "plan.RequireFullyDefined" in runner_source
    assert '" after generalized constraint completion."' in runner_source


def test_native_runner_drives_freeform_vertices_and_arc_control_points():
    runner_source = (
        Path(__file__).parents[1]
        / "src"
        / "prompt2cad"
        / "solidworks_replay_runner.cs"
    ).read_text(encoding="utf-8")

    assert 'DataMember(Name = "coordinate_controls")' in runner_source
    assert "ApplyCoordinateControls(" in runner_source
    assert '"arc_through"' in runner_source
    assert "AddPointSegmentRelation(" in runner_source
    assert "control.PositionMillimeters[0], control.XDimension" in runner_source
    assert "control.PositionMillimeters[1], control.YDimension" in runner_source


def test_native_runner_disables_sketch_snapping_during_profile_creation():
    runner_source = (
        Path(__file__).parents[1]
        / "src"
        / "prompt2cad"
        / "solidworks_replay_runner.cs"
    ).read_text(encoding="utf-8")

    assert "bool previousAddToDatabase = sketchManager.AddToDB;" in runner_source
    assert "sketchManager.AddToDB = true;" in runner_source
    assert "sketchManager.AddToDB = previousAddToDatabase;" in runner_source
    assert "finally" in runner_source


def test_native_runner_persists_and_reopens_semantic_entity_references():
    runner_source = (
        Path(__file__).parents[1]
        / "src"
        / "prompt2cad"
        / "solidworks_replay_runner.cs"
    ).read_text(encoding="utf-8")

    assert "NativeReferenceSpec[] PublishReferences" in runner_source
    assert "CapturePersistentReferenceIds(" in runner_source
    assert "GetPersistReference3(" in runner_source
    assert "GetObjectByPersistReference3(" in runner_source
    assert "Persistent reference '" in runner_source


def test_native_runner_resolves_arbitrary_planar_faces_by_geometry():
    runner_source = (
        Path(__file__).parents[1]
        / "src"
        / "prompt2cad"
        / "solidworks_replay_runner.cs"
    ).read_text(encoding="utf-8")

    assert 'DataMember(Name = "center_mm")' in runner_source
    assert 'DataMember(Name = "area_mm2")' in runner_source
    assert '"planar_face_geometry"' in runner_source
    assert "FindPlanarFaceByGeometry(" in runner_source
    assert "planeDistanceMillimeters > 0.5" in runner_source
    assert "areaError" in runner_source


def test_native_runner_resolves_edge_groups_by_canonical_member_geometry():
    runner_source = (
        Path(__file__).parents[1]
        / "src"
        / "prompt2cad"
        / "solidworks_replay_runner.cs"
    ).read_text(encoding="utf-8")

    assert "SelectFeatureEdgesByMembers(" in runner_source
    assert "SampleEdgeBoundingBoxMillimeters(" in runner_source
    assert "EdgeDescriptorError(" in runner_source
    assert "did not match native topology within 0.5 mm" in runner_source


def test_native_circular_pattern_uses_a_reference_axis_feature():
    runner_source = (
        Path(__file__).parents[1]
        / "src"
        / "prompt2cad"
        / "solidworks_replay_runner.cs"
    ).read_text(encoding="utf-8")

    assert "model.InsertAxis2(true)" in runner_source
    assert "model.IFeatureByPositionReverse(0)" in runner_source
    assert "SelectCircularPatternAxis(references.CircularAxis)" in runner_source
    assert "axis.Select2(true, 1)" in runner_source
    assert "swFeatureNameID_e.swFmCirPattern" in runner_source
    assert "definition.Axis = axisEntity" in runner_source
    assert "definition.PatternFeatureArray" not in runner_source
    assert "RequireReferenceAxisDirection(" in runner_source
    assert "FeatureCircularPattern5(" not in runner_source


def test_native_geometry_bounds_exclude_reference_geometry():
    runner_source = (
        Path(__file__).parents[1]
        / "src"
        / "prompt2cad"
        / "solidworks_replay_runner.cs"
    ).read_text(encoding="utf-8")

    assert "body.GetBodyBox()" in runner_source
    assert "part.GetPartBox(" not in runner_source


def test_native_replay_tracks_the_saved_document_title_for_cleanup():
    runner_source = (
        Path(__file__).parents[1]
        / "src"
        / "prompt2cad"
        / "solidworks_replay_runner.cs"
    ).read_text(encoding="utf-8")

    save_position = runner_source.index("int saveStatus = model.SaveAs3(")
    refresh_position = runner_source.index(
        "modelTitle = model.GetTitle();", save_position
    )
    close_position = runner_source.index(
        "application.CloseDoc(modelTitle);", refresh_position
    )
    assert save_position < refresh_position < close_position


def test_native_runner_stages_verified_outputs_before_publication():
    runner_source = (
        Path(__file__).parents[1]
        / "src"
        / "prompt2cad"
        / "solidworks_replay_runner.cs"
    ).read_text(encoding="utf-8")

    assert "PrepareNewOutputPath(outputPath)" in runner_source
    assert "CreateStagedOutputPath(resolvedOutput)" in runner_source
    assert "PublishStagedOutput(stagedOutput, resolvedOutput)" in runner_source
    assert "TryDeleteFile(stagedOutput)" in runner_source
    assert "Refusing to overwrite existing SOLIDWORKS output" in runner_source
    assert "File.Move(stagedOutput, resolvedOutput)" in runner_source


def test_native_runner_dimensions_rectangles_in_their_local_feature_frame():
    runner_source = (
        Path(__file__).parents[1]
        / "src"
        / "prompt2cad"
        / "solidworks_replay_runner.cs"
    ).read_text(encoding="utf-8")

    assert "double[] widthDirection = ToSketchDirection(" in runner_source
    assert "double[] heightDirection = ToSketchDirection(" in runner_source
    assert "private static double[] ToSketchDirection(" in runner_source
    assert "swDimensionDrivenState_e.swDimensionDriven" in runner_source
    assert "swDimensionDrivenState_e.swDimensionDriving" in runner_source
    assert "kept dimension '" in runner_source


def test_native_runner_anchors_center_rectangles_with_explicit_geometry():
    runner_source = (
        Path(__file__).parents[1]
        / "src"
        / "prompt2cad"
        / "solidworks_replay_runner.cs"
    ).read_text(encoding="utf-8")

    assert "CreateRectangleCenterPoint(" in runner_source
    assert "segment.ConstructionGeometry" in runner_source
    assert 'model.SketchAddConstraints("sgATMIDDLE")' in runner_source


def test_export_invokes_packaged_runner_with_validated_plan(tmp_path: Path):
    plan = replay_plan()
    output_path = tmp_path / "native" / "part.SLDPRT"
    captured: dict = {}

    def fake_runner(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        plan_path = Path(command[command.index("-PlanPath") + 1])
        captured["plan"] = json.loads(plan_path.read_text(encoding="utf-8"))
        actual_output = Path(command[command.index("-OutputPath") + 1])
        actual_output.write_bytes(b"native-part-placeholder")
        return subprocess.CompletedProcess(command, 0, stdout="success", stderr="")

    exported = export_solidworks_part(
        plan,
        output_path,
        visible=True,
        template_path=tmp_path / "Part.prtdot",
        runner=fake_runner,
    )

    assert exported == output_path.resolve()
    assert captured["plan"]["source_build_order"] == ["base", "boss", "hole"]
    assert captured["command"][0] == "powershell.exe"
    assert "-Visible" in captured["command"]
    assert "-TemplatePath" in captured["command"]
    assert captured["kwargs"] == {
        "check": False,
        "capture_output": True,
        "text": True,
    }


def test_export_reports_runner_failure_and_requires_sldprt(tmp_path: Path):
    plan = replay_plan()

    with pytest.raises(SolidWorksExecutionError, match=".SLDPRT suffix"):
        export_solidworks_part(plan, tmp_path / "part.step")

    existing_output = tmp_path / "existing.SLDPRT"
    existing_output.write_bytes(b"do-not-overwrite")
    with pytest.raises(SolidWorksExecutionError, match="Refusing to overwrite"):
        export_solidworks_part(plan, existing_output)
    assert existing_output.read_bytes() == b"do-not-overwrite"

    def failing_runner(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr="native feature creation failed",
        )

    with pytest.raises(
        SolidWorksExecutionError,
        match="native feature creation failed",
    ):
        export_solidworks_part(
            plan,
            tmp_path / "part.SLDPRT",
            runner=failing_runner,
        )

    def missing_runner(command, **kwargs):
        raise FileNotFoundError("powershell.exe")

    with pytest.raises(
        SolidWorksExecutionError,
        match="replay process could not start",
    ):
        export_solidworks_part(
            plan,
            tmp_path / "part.SLDPRT",
            runner=missing_runner,
        )


def test_editability_verification_reopens_and_mutates_bound_parameters(
    tmp_path: Path,
):
    plan = replay_plan()
    source_path = tmp_path / "source.SLDPRT"
    output_path = tmp_path / "mutated.SLDPRT"
    result_path = tmp_path / "editability-result.json"
    source_path.write_bytes(b"source-native-part")
    captured: dict = {}

    def fake_runner(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        mutation_path = Path(command[command.index("-MutationPath") + 1])
        captured["mutations"] = json.loads(
            mutation_path.read_text(encoding="utf-8")
        )
        actual_output = Path(command[command.index("-OutputPath") + 1])
        actual_output.write_bytes(b"mutated-native-part")
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "status": "success",
                    "mutation_count": 2,
                    "reopened": True,
                }
            ),
            stderr="",
        )

    exported = verify_solidworks_editability(
        plan,
        source_path,
        output_path,
        {
            "base.sketch.width": 90,
            "boss.feature.distance": 12,
        },
        result_output_path=result_path,
        runner=fake_runner,
    )

    assert exported == output_path.resolve()
    assert captured["mutations"] == {
        "format": "prompt2cad.solidworks-mutations",
        "version": 1,
        "mutations": [
            {
                "parameter_id": "base.sketch.width",
                "value": 90.0,
                "unit": "mm",
            },
            {
                "parameter_id": "boss.feature.distance",
                "value": 12.0,
                "unit": "mm",
            },
        ],
    }
    assert "-ExistingPartPath" in captured["command"]
    assert captured["kwargs"] == {
        "check": False,
        "capture_output": True,
        "text": True,
    }
    assert json.loads(result_path.read_text(encoding="utf-8"))["reopened"] is True


def test_editability_verification_rejects_unknown_or_destructive_inputs(
    tmp_path: Path,
):
    plan = replay_plan()
    source_path = tmp_path / "source.SLDPRT"
    source_path.write_bytes(b"source-native-part")

    with pytest.raises(SolidWorksExecutionError, match="Unknown native parameter"):
        verify_solidworks_editability(
            plan,
            source_path,
            tmp_path / "mutated.SLDPRT",
            {"not.a.parameter": 10},
        )
    with pytest.raises(SolidWorksExecutionError, match="separate output"):
        verify_solidworks_editability(
            plan,
            source_path,
            source_path,
            {"base.sketch.width": 90},
        )
    existing_output = tmp_path / "existing.SLDPRT"
    existing_output.write_bytes(b"do-not-overwrite")
    with pytest.raises(SolidWorksExecutionError, match="Refusing to overwrite"):
        verify_solidworks_editability(
            plan,
            source_path,
            existing_output,
            {"base.sketch.width": 90},
        )
    assert existing_output.read_bytes() == b"do-not-overwrite"


def test_editability_verification_preserves_signed_placement_side(
    tmp_path: Path,
):
    model_data = native_model_data()
    model_data["operations"][1]["positions"] = [[-12, 7]]
    plan = replay_plan(model_data)
    source_path = tmp_path / "source.SLDPRT"
    output_path = tmp_path / "mutated.SLDPRT"
    source_path.write_bytes(b"source-native-part")
    captured: dict = {}

    def fake_runner(command, **kwargs):
        mutation_path = Path(command[command.index("-MutationPath") + 1])
        captured["mutations"] = json.loads(
            mutation_path.read_text(encoding="utf-8")
        )
        Path(command[command.index("-OutputPath") + 1]).write_bytes(
            b"mutated-native-part"
        )
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

    verify_solidworks_editability(
        plan,
        source_path,
        output_path,
        {"boss.placement.inst001.x": -20},
        runner=fake_runner,
    )

    assert captured["mutations"]["mutations"][0]["value"] == -20.0


def test_native_mutation_preflight_needs_no_solidworks_files():
    model_data = native_model_data()
    model_data["operations"][1]["positions"] = [[-12, 7]]

    result = validate_solidworks_mutations(
        replay_plan(model_data),
        {
            "base.sketch.width": 90,
            "boss.placement.inst001.x": -20,
        },
    )

    assert result == {
        "mutation_count": 2,
        "parameter_ids": [
            "base.sketch.width",
            "boss.placement.inst001.x",
        ],
        "native_values": {
            "base.sketch.width": 90.0,
            "boss.placement.inst001.x": 20.0,
        },
    }


@pytest.mark.parametrize("unsafe_value", [0, 12])
def test_editability_verification_rejects_placement_side_crossing(
    tmp_path: Path,
    unsafe_value: float,
):
    model_data = native_model_data()
    model_data["operations"][1]["positions"] = [[-12, 7]]
    plan = replay_plan(model_data)
    source_path = tmp_path / "source.SLDPRT"
    source_path.write_bytes(b"source-native-part")

    def unexpected_runner(*args, **kwargs):
        raise AssertionError("unsafe mutation must fail before SOLIDWORKS starts")

    with pytest.raises(SolidWorksExecutionError, match="cannot cross or land"):
        verify_solidworks_editability(
            plan,
            source_path,
            tmp_path / "mutated.SLDPRT",
            {"boss.placement.inst001.x": unsafe_value},
            runner=unexpected_runner,
        )


def test_editability_verification_rejects_nonfinite_values(tmp_path: Path):
    plan = replay_plan()
    source_path = tmp_path / "source.SLDPRT"
    source_path.write_bytes(b"source-native-part")

    with pytest.raises(SolidWorksExecutionError, match="requires a finite value"):
        verify_solidworks_editability(
            plan,
            source_path,
            tmp_path / "mutated.SLDPRT",
            {"base.sketch.width": float("nan")},
        )


@pytest.mark.parametrize("unsafe_value", [0, -1])
def test_editability_verification_rejects_nonpositive_dimensions(
    tmp_path: Path,
    unsafe_value: float,
):
    source_path = tmp_path / "source.SLDPRT"
    source_path.write_bytes(b"source-native-part")

    with pytest.raises(SolidWorksExecutionError, match="greater than 0.0"):
        verify_solidworks_editability(
            replay_plan(),
            source_path,
            tmp_path / "mutated.SLDPRT",
            {"base.sketch.width": unsafe_value},
        )


def test_editability_verification_rejects_fractional_pattern_counts(
    tmp_path: Path,
):
    model_data = native_model_data()
    model_data["operations"] = model_data["operations"][:2]
    model_data["operations"][1] = {
        "type": "cut",
        "id": "holes",
        "target": "base.top",
        "profile": "circle",
        "positions": [[20, 0], [0, 20], [-20, 0], [0, -20]],
        "pattern": {
            "type": "circular",
            "seed_position": [20, 0],
            "center": [0, 0],
            "count": 4,
            "total_angle_degrees": 360,
        },
        "diameter": 6,
        "depth": "through",
    }
    source_path = tmp_path / "source.SLDPRT"
    source_path.write_bytes(b"source-native-part")

    with pytest.raises(SolidWorksExecutionError, match="whole-number value"):
        verify_solidworks_editability(
            replay_plan(model_data),
            source_path,
            tmp_path / "mutated.SLDPRT",
            {"holes.pattern.count": 3.5},
        )


def test_editability_verification_rejects_out_of_range_angles(tmp_path: Path):
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
    source_path = tmp_path / "source.SLDPRT"
    source_path.write_bytes(b"source-native-part")

    with pytest.raises(SolidWorksExecutionError, match="at most 360.0"):
        verify_solidworks_editability(
            replay_plan(model_data),
            source_path,
            tmp_path / "mutated.SLDPRT",
            {"shaft.feature.angle": 361},
        )


def test_editability_preflight_validates_countersink_dimensions_together(
    tmp_path: Path,
):
    model_data = native_model_data()
    model_data["operations"] = [
        model_data["operations"][0],
        {
            "type": "countersink",
            "id": "mounting_hole",
            "target": "base.top",
            "positions": [[20, 0]],
            "diameter": 6,
            "countersink_diameter": 12,
            "angle": 82,
            "depth": "through",
        },
    ]
    plan = replay_plan(model_data)
    source_path = tmp_path / "source.SLDPRT"
    source_path.write_bytes(b"source-native-part")

    with pytest.raises(SolidWorksExecutionError, match="remain larger"):
        verify_solidworks_editability(
            plan,
            source_path,
            tmp_path / "invalid.SLDPRT",
            {"mounting_hole.feature.diameter": 13},
        )

    def fake_runner(command, **kwargs):
        Path(command[command.index("-OutputPath") + 1]).write_bytes(
            b"mutated-native-part"
        )
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

    verify_solidworks_editability(
        plan,
        source_path,
        tmp_path / "valid.SLDPRT",
        {
            "mounting_hole.feature.diameter": 13,
            "mounting_hole.feature.countersink_diameter": 16,
        },
        runner=fake_runner,
    )


@pytest.mark.parametrize(
    ("mutations", "message"),
    [
        (
            {"holes.pattern.count_1": 1, "holes.pattern.count_2": 1},
            "retain at least two instances",
        ),
        (
            {"holes.pattern.count_1": 3, "holes.pattern.spacing_1": 0},
            "requires positive direction-1 spacing",
        ),
    ],
)
def test_editability_preflight_validates_linear_pattern_relationships(
    tmp_path: Path,
    mutations: dict[str, float],
    message: str,
):
    model_data = native_model_data()
    model_data["operations"] = model_data["operations"][:2]
    model_data["operations"][1] = {
        "type": "cut",
        "id": "holes",
        "target": "base.top",
        "profile": "circle",
        "positions": [[-20, 0], [0, 0], [20, 0]],
        "pattern": {
            "type": "linear",
            "seed_position": [-20, 0],
            "direction_1": [1, 0],
            "count_1": 3,
            "spacing_1": 20,
            "direction_2": [0, 1],
            "count_2": 1,
            "spacing_2": 0,
        },
        "diameter": 6,
        "depth": "through",
    }
    source_path = tmp_path / "source.SLDPRT"
    source_path.write_bytes(b"source-native-part")

    with pytest.raises(SolidWorksExecutionError, match=message):
        verify_solidworks_editability(
            replay_plan(model_data),
            source_path,
            tmp_path / "mutated.SLDPRT",
            mutations,
        )


def test_native_runner_reopens_and_reverifies_mutated_parts():
    runner_source = (
        Path(__file__).parents[1]
        / "src"
        / "prompt2cad"
        / "solidworks_replay_runner.cs"
    ).read_text(encoding="utf-8")

    assert "VerifyEditablePart(" in runner_source
    assert "ApplyParameterMutations(model, plan, mutations)" in runner_source
    assert "model = OpenNativePart(application, stagedOutput);" in runner_source
    assert "PublishStagedOutput(stagedOutput, resolvedOutput);" in runner_source
    assert 'Reopened = true' in runner_source
    assert "VerifyReplay(" in runner_source
    assert "RequireHealthyModel(reopenedHealth" in runner_source


def test_plan_file_helpers_are_deterministic(tmp_path: Path):
    model_path = tmp_path / "model.json"
    model_path.write_text(json.dumps(native_model_data()), encoding="utf-8")

    plan = model_path_to_replay_plan(model_path)
    plan_path = save_plan(plan, tmp_path / "replay-plan.json")
    saved = json.loads(plan_path.read_text(encoding="utf-8"))

    assert saved == plan.to_dict()
    assert saved["features"][0]["feature_name"] == "P2P_base"


@pytest.mark.parametrize(
    "example_name",
    [
        "api_rectangular_plate.json",
        "circular_base_rectangular_boss.json",
        "example_part.json",
        "polygon_base_polygon_cut.json",
        "polyline_base_rectangular_cut.json",
        "rectangular_plate_multiple_holes.json",
    ],
)
def test_supported_step_examples_have_complete_native_replay_plans(example_name):
    example_path = (
        Path(__file__).parents[1] / "examples" / "models" / example_name
    )

    plan = model_path_to_replay_plan(example_path)

    assert plan.features
    assert tuple(feature.id for feature in plan.features) == plan.source_build_order
