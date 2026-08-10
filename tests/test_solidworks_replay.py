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
from prompt2cad.solidworks_replay import SOLIDWORKS_PARITY_MATRIX
from prompt2cad.solidworks_replay import SolidWorksExecutionError
from prompt2cad.solidworks_replay import build_solidworks_replay_plan
from prompt2cad.solidworks_replay import export_solidworks_part


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


def replay_plan(model_data: dict | None = None):
    document = model_data_to_editable_document(model_data or native_model_data())
    return build_solidworks_replay_plan(document)


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
    assert base.publish_references == {
        "top": "P2P_base_top",
        "bottom": "P2P_base_bottom",
        "front": "P2P_base_front",
        "back": "P2P_base_back",
        "left": "P2P_base_left",
        "right": "P2P_base_right",
    }
    assert boss.support["entity_name"] == "P2P_base_top"
    assert boss.publish_references == {
        "top": "P2P_boss_top",
        "outer_surface": "P2P_boss_outer_surface",
    }
    assert hole.support["entity_name"] == "P2P_boss_top"
    assert hole.publish_references == {}


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
    assert revolved.publish_references["front"] == "P2P_shaft_front"

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
