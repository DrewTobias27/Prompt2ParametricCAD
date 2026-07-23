"""Tests for lowering high-level design intent into CAD operations."""

import pytest

from prompt2cad.design_intent import intent_to_model_data
from prompt2cad.design_intent import offset_from_edge_position
from prompt2cad.design_intent import validate_design_intent
from prompt2cad.diagnostics import check_model_data
from prompt2cad.operation_effects import evaluate_operation_effects
from prompt2cad.schema import validate_model_data


def test_near_corners_intent_computes_four_hole_positions():
    intent = {
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 100,
            "height": 70,
            "thickness": 8,
        },
        "features": [
            {
                "id": "corner_holes",
                "operation": "cut",
                "target": "base.top",
                "shape": "circle",
                "diameter": 6,
                "depth": "through",
                "placement": {
                    "type": "near_corners",
                    "count": 4,
                    "margin": 7,
                },
            }
        ],
    }

    model_data = intent_to_model_data(intent)

    hole_operation = model_data["operations"][1]
    assert hole_operation["positions"] == [
        [-40, 25],
        [40, 25],
        [-40, -25],
        [40, -25],
    ]
    validate_model_data(model_data)


def test_near_corners_uses_regular_polygon_vertices():
    intent = {
        "base": {
            "id": "base",
            "profile": "polygon",
            "diameter": 110,
            "sides": 3,
            "thickness": 7,
        },
        "features": [
            {
                "id": "vertex_bosses",
                "operation": "extrusion",
                "target": "base.top",
                "shape": "circle",
                "diameter": 14,
                "distance": 5,
                "placement": {
                    "type": "near_corners",
                    "count": 3,
                    "margin": 5,
                },
            }
        ],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][1]["positions"] == [
        [31, 0],
        [-15.5, 26.846788],
        [-15.5, -26.846788],
    ]
    assert check_model_data(model_data)["passed"] is True


def test_circular_pattern_intent_computes_evenly_spaced_positions():
    intent = {
        "base": {
            "id": "base",
            "profile": "circle",
            "diameter": 80,
            "thickness": 8,
        },
        "features": [
            {
                "id": "bolt_holes",
                "operation": "cut",
                "target": "base.top",
                "shape": "circle",
                "diameter": 6,
                "depth": "through",
                "placement": {
                    "type": "circular_pattern",
                    "count": 4,
                    "radius": 30,
                },
            }
        ],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][1]["positions"] == [
        [30, 0],
        [0, 30],
        [-30, 0],
        [0, -30],
    ]
    validate_model_data(model_data)


def test_centered_extrusion_intent_adds_relationships():
    intent = {
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 80,
            "height": 50,
            "thickness": 8,
        },
        "features": [
            {
                "id": "center_boss",
                "operation": "extrusion",
                "target": "base.top",
                "shape": "rectangle",
                "width": 20,
                "height": 12,
                "distance": 6,
                "placement": {
                    "type": "centered",
                },
            }
        ],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][1]["positions"] == [[0, 0]]
    assert {
        "type": "centered_on",
        "feature": "center_boss",
        "reference": "base",
        "tolerance": 0.001,
    } in model_data["relationships"]
    assert {
        "type": "must_connect",
        "feature": "center_boss",
        "to": "base",
    } in model_data["relationships"]
    assert check_model_data(model_data)["passed"] is True


def test_slot_intent_lowers_to_arc_sketch_and_builds():
    intent = {
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 90,
            "height": 50,
            "thickness": 8,
        },
        "features": [
            {
                "id": "center_slot",
                "operation": "cut",
                "target": "base.top",
                "shape": "slot",
                "length": 36,
                "width": 10,
                "orientation": "horizontal",
                "depth": "through",
                "placement": {
                    "type": "centered",
                },
            }
        ],
    }

    model_data = intent_to_model_data(intent)
    slot_operation = model_data["operations"][1]

    assert slot_operation["profile"] == "sketch"
    assert any(segment["type"] == "arc" for segment in slot_operation["segments"])
    assert check_model_data(model_data)["passed"] is True


def test_mirrored_intent_removes_duplicate_centered_instances():
    intent = {
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 100,
            "height": 70,
            "thickness": 8,
        },
        "features": [
            {
                "id": "mirrored_tabs",
                "operation": "extrusion",
                "target": "base.top",
                "shape": "rectangle",
                "width": 10,
                "height": 8,
                "distance": 5,
                "placement": {
                    "type": "mirrored",
                    "seed": [30, 0],
                    "axes": ["x", "y"],
                },
            }
        ],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][1]["positions"] == [[30, 0], [-30, 0]]


def test_rectangular_pattern_intent_computes_grid_positions():
    intent = {
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 100,
            "height": 70,
            "thickness": 8,
        },
        "features": [
            {
                "id": "grid_holes",
                "operation": "cut",
                "target": "base.top",
                "shape": "circle",
                "diameter": 5,
                "depth": "through",
                "placement": {
                    "type": "rectangular_pattern",
                    "rows": 2,
                    "columns": 3,
                    "row_spacing": 20,
                    "column_spacing": 30,
                    "center": [0, 0],
                },
            }
        ],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][1]["positions"] == [
        [-30, -10],
        [0, -10],
        [30, -10],
        [-30, 10],
        [0, 10],
        [30, 10],
    ]


def test_offset_from_edge_intent_places_feature_inward_from_named_edge():
    intent = {
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 100,
            "height": 70,
            "thickness": 8,
        },
        "features": [
            {
                "id": "front_slot",
                "operation": "cut",
                "target": "base.top",
                "shape": "slot",
                "length": 30,
                "width": 8,
                "orientation": "horizontal",
                "depth": "through",
                "placement": {
                    "type": "offset_from_edge",
                    "edge": "front",
                    "offset": 6,
                    "along": 0,
                },
            }
        ],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][1]["positions"] == [[0, 25]]


def test_offset_from_edge_clamps_along_coordinate_inside_target_face():
    base = {
        "profile": "rectangle",
        "width": 90,
        "height": 55,
    }
    wall = {
        "shape": "rectangle",
        "width": 90,
        "height": 8,
    }

    positions = offset_from_edge_position(
        base,
        wall,
        {
            "edge": "front",
            "offset": 0,
            "along": 90,
        },
    )

    assert positions == [[0, 23.5]]


def test_aligned_through_holes_in_opposing_walls_lower_to_one_bore():
    wall_template = {
        "role": "wall",
        "operation": "extrusion",
        "target": "base.top",
        "shape": "rectangle",
        "width": 90,
        "height": 8,
        "distance": 45,
    }
    hole_template = {
        "role": "hole",
        "operation": "cut",
        "shape": "circle",
        "diameter": 8,
        "depth": "through",
        "placement": {"type": "centered"},
    }
    intent = {
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 90,
            "height": 55,
            "thickness": 8,
        },
        "features": [
            {
                **wall_template,
                "id": "front_wall",
                "placement": {
                    "type": "offset_from_edge",
                    "edge": "front",
                    "offset": 0,
                    "along": 0,
                },
            },
            {
                **wall_template,
                "id": "back_wall",
                "placement": {
                    "type": "offset_from_edge",
                    "edge": "back",
                    "offset": 0,
                    "along": 0,
                },
            },
            {
                **hole_template,
                "id": "front_wall_hole",
                "target": "front_wall.side",
            },
            {
                **hole_template,
                "id": "back_wall_hole",
                "target": "back_wall.side",
            },
        ],
    }

    model_data = intent_to_model_data(intent)

    assert [
        operation["id"]
        for operation in model_data["operations"]
    ] == ["base", "front_wall", "back_wall", "front_wall_hole"]
    assert evaluate_operation_effects(model_data)["passed"] is True


def test_rounded_rectangle_intent_lowers_to_arc_sketch_and_builds():
    intent = {
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 90,
            "height": 60,
            "thickness": 8,
        },
        "features": [
            {
                "id": "rounded_boss",
                "operation": "extrusion",
                "target": "base.top",
                "shape": "rounded_rectangle",
                "width": 30,
                "height": 18,
                "radius": 4,
                "distance": 6,
                "placement": {
                    "type": "centered",
                },
            }
        ],
    }

    model_data = intent_to_model_data(intent)
    rounded_operation = model_data["operations"][1]

    assert rounded_operation["profile"] == "sketch"
    arc_segments = [
        segment for segment in rounded_operation["segments"]
        if segment["type"] == "arc"
    ]
    assert len(arc_segments) == 4
    assert check_model_data(model_data)["passed"] is True


def test_semicircular_rounded_rectangle_lowers_to_slot_profile():
    intent = {
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 100,
            "height": 80,
            "thickness": 8,
        },
        "features": [
            {
                "id": "groove",
                "operation": "cut",
                "target": "base.top",
                "shape": "rounded_rectangle",
                "width": 8,
                "height": 70,
                "radius": 4,
                "depth": 3,
                "placement": {"type": "centered"},
            }
        ],
    }

    model_data = intent_to_model_data(intent)
    groove = model_data["operations"][1]

    assert groove["profile"] == "sketch"
    assert len([s for s in groove["segments"] if s["type"] == "arc"]) == 2
    assert check_model_data(model_data)["passed"] is True


def test_same_as_feature_reuses_parent_positions():
    intent = {
        "base": {
            "id": "base_plate",
            "profile": "rectangle",
            "width": 100,
            "height": 70,
            "thickness": 8,
        },
        "features": [
            {
                "id": "corner_bosses",
                "operation": "extrusion",
                "target": "base.top",
                "shape": "circle",
                "diameter": 16,
                "distance": 6,
                "placement": {
                    "type": "near_corners",
                    "count": 4,
                    "margin": 10,
                },
            },
            {
                "id": "boss_holes",
                "operation": "cut",
                "target": "corner_bosses.top",
                "shape": "circle",
                "diameter": 5,
                "depth": "through",
                "placement": {
                    "type": "same_as_feature",
                    "source_feature": "corner_bosses",
                },
            },
        ],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][2]["positions"] == model_data["operations"][1]["positions"]
    assert model_data["operations"][2]["target"] == "corner_bosses.top"
    assert check_model_data(model_data)["passed"] is True


def test_near_corner_placement_uses_target_feature_dimensions():
    intent = {
        "base": {
            "id": "base",
            "profile": "half_cylinder",
            "diameter": 80,
            "length": 120,
        },
        "features": [
            {
                "id": "mounting_plate",
                "operation": "extrusion",
                "target": "base.flat",
                "shape": "rectangle",
                "width": 120,
                "height": 80,
                "distance": 6,
                "placement": {"type": "centered"},
            },
            {
                "id": "plate_holes",
                "operation": "cut",
                "target": "mounting_plate.top",
                "shape": "circle",
                "diameter": 7,
                "depth": "through",
                "placement": {
                    "type": "near_corners",
                    "count": 2,
                    "margin": 5,
                },
            },
        ],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][2]["positions"] == [
        [-51.5, 31.5],
        [51.5, 31.5],
    ]
    assert check_model_data(model_data)["passed"] is True


def test_half_cylinder_descriptive_face_aliases_are_normalized():
    intent = {
        "base": {
            "id": "cradle",
            "profile": "half_cylinder",
            "diameter": 80,
            "length": 120,
        },
        "features": [
            {
                "id": "flat_pad",
                "operation": "extrusion",
                "target": "base.flat_face",
                "shape": "rectangle",
                "width": 40,
                "height": 20,
                "distance": 4,
                "placement": {"type": "centered"},
            },
            {
                "id": "curved_cut",
                "operation": "cut",
                "target": "base.curved_surface",
                "shape": "circle",
                "diameter": 5,
                "depth": 2,
                "placement": {"type": "centered"},
            },
        ],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][1]["target"] == "base.top"
    assert model_data["operations"][2]["target"] == "base.outer_surface"


def test_validate_design_intent_reports_missing_shape_dimensions():
    intent = {
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 100,
            "height": 70,
            "thickness": 8,
        },
        "features": [
            {
                "id": "bad_hole",
                "operation": "cut",
                "target": "base.top",
                "shape": "circle",
                "depth": "through",
                "placement": {"type": "centered"},
            }
        ],
    }

    with pytest.raises(ValueError, match="diameter"):
        validate_design_intent(intent)


def test_intent_to_model_data_accepts_nulls_from_strict_api_schema():
    intent = {
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 80,
            "height": 50,
            "diameter": None,
            "sides": None,
            "thickness": 8,
        },
        "features": [
            {
                "id": "corner_holes",
                "operation": "cut",
                "target": "base.top",
                "shape": "circle",
                "placement": {
                    "type": "near_corners",
                    "count": 4,
                    "margin": None,
                },
                "width": None,
                "height": None,
                "diameter": 6,
                "sides": None,
                "length": None,
                "orientation": None,
                "distance": None,
                "depth": "through",
            }
        ],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][1]["profile"] == "circle"
    assert len(model_data["operations"][1]["positions"]) == 4


def test_polygon_base_can_infer_diameter_from_width():
    intent = {
        "base": {
            "id": "hex_plate",
            "profile": "polygon",
            "width": 80,
            "sides": 6,
            "thickness": 6,
        },
        "features": [],
        "edge_treatments": [],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][0]["profile"] == "polygon"
    assert model_data["operations"][0]["diameter"] == 80.0
    assert model_data["operations"][0]["sides"] == 6
    assert check_model_data(model_data)["passed"] is True


def test_intent_lowering_normalizes_vague_side_and_feature_targets():
    intent = {
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 100,
            "height": 60,
            "thickness": 6,
        },
        "features": [
            {
                "id": "back_wall",
                "operation": "extrusion",
                "target": "base.side",
                "shape": "rectangle",
                "width": 80,
                "height": 6,
                "distance": 30,
                "placement": {
                    "type": "offset_from_edge",
                    "edge": "back",
                    "offset": 0,
                    "along": 0,
                },
            },
            {
                "id": "wall_hole",
                "operation": "cut",
                "target": "back_wall",
                "shape": "circle",
                "diameter": 8,
                "depth": "through",
                "placement": {"type": "centered"},
            },
        ],
        "edge_treatments": [],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][1]["target"] == "base.top"
    assert model_data["operations"][2]["target"] == "back_wall.front"


def test_intent_lowering_normalizes_named_feature_side_targets():
    intent = {
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 80,
            "height": 50,
            "thickness": 6,
        },
        "features": [
            {
                "id": "rect_boss",
                "operation": "extrusion",
                "target": "base.top",
                "shape": "rectangle",
                "width": 30,
                "height": 20,
                "distance": 8,
                "placement": {"type": "centered"},
            },
            {
                "id": "cross_hole",
                "operation": "cut",
                "target": "rect_boss.side",
                "shape": "circle",
                "diameter": 6,
                "depth": "through",
                "placement": {"type": "centered"},
            },
        ],
        "edge_treatments": [],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][2]["target"] == "rect_boss.front"
    assert check_model_data(model_data)["passed"] is True


def test_capsule_with_thickness_lowers_to_flat_obround_plate():
    intent = {
        "base": {
            "id": "obround_flange",
            "profile": "capsule",
            "diameter": 40,
            "length": 120,
            "thickness": 6,
        },
        "features": [
            {
                "id": "mount_holes",
                "operation": "cut",
                "target": "base.top",
                "shape": "circle",
                "diameter": 6,
                "depth": "through",
                "placement": {
                    "type": "explicit",
                    "positions": [[-30, 0], [30, 0]],
                },
            }
        ],
        "edge_treatments": [],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][0]["type"] == "extrude"
    assert model_data["operations"][0]["profile"] == "sketch"
    assert model_data["operations"][0]["distance"] == 6.0
    assert check_model_data(model_data)["passed"] is True


def test_d_shape_base_lowers_to_flat_arc_sketch_plate():
    intent = {
        "base": {
            "id": "d_plate",
            "role": "plate",
            "profile": "d_shape",
            "width": 100,
            "height": 60,
            "thickness": 6,
        },
        "features": [
            {
                "id": "centerline_holes",
                "role": "hole",
                "operation": "cut",
                "target": "d_plate.top",
                "shape": "circle",
                "diameter": 6,
                "depth": "through",
                "placement": {
                    "type": "rectangular_pattern",
                    "rows": 1,
                    "columns": 3,
                    "row_spacing": 0,
                    "column_spacing": 25,
                    "center": [0, 0],
                },
            }
        ],
        "edge_treatments": [],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][0]["profile"] == "sketch"
    assert any(
        segment["type"] == "arc"
        for segment in model_data["operations"][0]["segments"]
    )
    assert check_model_data(model_data)["passed"] is True


def test_edge_treatment_intent_lowers_to_real_chamfer_operation_and_builds():
    intent = {
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 80,
            "height": 50,
            "thickness": 6,
        },
        "features": [],
        "edge_treatments": [
            {
                "id": "top_chamfer",
                "treatment": "chamfer",
                "target_feature": "base",
                "edge_selector": "top_outer_edges",
                "distance": 1,
            }
        ],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][1] == {
        "type": "chamfer",
        "id": "top_chamfer",
        "target": "base.top_outer_edges",
        "distance": 1.0,
    }
    assert check_model_data(model_data)["passed"] is True


def test_flat_flange_o_ring_groove_uses_circle_base_and_revolved_cut():
    intent = {
        "required_concepts": [
            "plate",
            "hole",
            "bolt_hole",
            "o_ring_groove",
        ],
        "base": {
            "id": "flange",
            "role": "plate",
            "profile": "circle",
            "diameter": 100,
            "thickness": 8,
        },
        "features": [
            {
                "id": "center_hole",
                "role": "hole",
                "operation": "cut",
                "target": "flange.top",
                "shape": "circle",
                "diameter": 35,
                "depth": "through",
                "placement": {"type": "centered"},
            },
            {
                "id": "bolt_holes",
                "role": "bolt_hole",
                "operation": "cut",
                "target": "flange.top",
                "shape": "circle",
                "diameter": 6,
                "depth": "through",
                "placement": {
                    "type": "circular_pattern",
                    "count": 8,
                    "radius": 38,
                },
            },
            {
                "id": "o_ring_groove",
                "role": "o_ring_groove",
                "operation": "revolved_cut",
                "target": "flange.top",
                "shape": "rectangle",
                "width": 1.5,
                "height": 2,
                "radius": 32,
                "placement": {
                    "type": "explicit",
                    "positions": [[0, 0]],
                },
            },
        ],
        "edge_treatments": [],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][0]["profile"] == "circle"
    assert model_data["operations"][3]["type"] == "cut_revolve"
    assert model_data["operations"][3]["positions"] == [[32, 0]]
    assert check_model_data(model_data)["passed"] is True


def test_edge_treatment_intent_accepts_nulls_from_strict_api_schema():
    intent = {
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 80,
            "height": 50,
            "diameter": None,
            "sides": None,
            "thickness": 6,
        },
        "features": [],
        "edge_treatments": [
            {
                "id": "corner_rounds",
                "treatment": "fillet",
                "target_feature": "base",
                "edge_selector": "vertical_edges",
                "distance": None,
                "radius": 1,
            }
        ],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][1] == {
        "type": "fillet",
        "id": "corner_rounds",
        "target": "base.vertical_edges",
        "radius": 1.0,
    }


def test_rectangular_base_all_edges_fillets_normalize_to_outside_corners():
    intent = {
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 80,
            "height": 50,
            "thickness": 6,
        },
        "features": [
            {
                "id": "center_cutout",
                "operation": "cut",
                "target": "base.top",
                "shape": "rectangle",
                "width": 20,
                "height": 12,
                "depth": "through",
                "placement": {"type": "centered"},
            }
        ],
        "edge_treatments": [
            {
                "id": "outside_corner_rounds",
                "treatment": "fillet",
                "target_feature": "base",
                "edge_selector": "all_edges",
                "radius": 2,
            }
        ],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][1]["target"] == "base.vertical_edges"
    assert model_data["operations"][2]["target"] == "base.top"
    assert check_model_data(model_data)["passed"] is True


def test_multi_instance_rounded_feature_edges_can_be_targeted_as_one_feature():
    intent = {
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 100,
            "height": 100,
            "thickness": 6,
        },
        "features": [
            {
                "id": "corner_pads",
                "operation": "extrusion",
                "target": "base.top",
                "shape": "rounded_rectangle",
                "width": 12,
                "height": 12,
                "radius": 2,
                "distance": 2,
                "placement": {
                    "type": "near_corners",
                    "count": 4,
                    "margin": 10,
                },
            }
        ],
        "edge_treatments": [
            {
                "id": "pad_edge_fillets",
                "treatment": "fillet",
                "target_feature": "corner_pads",
                "edge_selector": "top_outer_edges",
                "radius": 1,
            }
        ],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][2]["target"] == "corner_pads.top_outer_edges"
    assert check_model_data(model_data)["passed"] is True


def test_edge_treatment_intent_maps_circle_vertical_edges_to_top_edges():
    intent = {
        "base": {
            "id": "base",
            "profile": "circle",
            "diameter": 80,
            "thickness": 8,
        },
        "features": [
            {
                "id": "round_boss",
                "operation": "extrusion",
                "target": "base.top",
                "shape": "circle",
                "diameter": 30,
                "distance": 8,
                "placement": {"type": "centered"},
            }
        ],
        "edge_treatments": [
            {
                "id": "boss_fillet",
                "treatment": "fillet",
                "target_feature": "round_boss",
                "edge_selector": "vertical_edges",
                "radius": 1,
            }
        ],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][2]["target"] == "round_boss.top_outer_edges"


def test_edge_treatment_intent_maps_shaft_end_edge_aliases():
    intent = {
        "base": {
            "id": "shaft",
            "profile": "cylinder",
            "diameter": 20,
            "length": 80,
        },
        "features": [],
        "edge_treatments": [
            {
                "id": "front_chamfer",
                "treatment": "chamfer",
                "target_feature": "shaft",
                "edge_selector": "top_outer_edges",
                "distance": 1,
            },
            {
                "id": "back_chamfer",
                "treatment": "chamfer",
                "target_feature": "shaft",
                "edge_selector": "bottom_outer_edges",
                "distance": 1,
            },
        ],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][1]["target"] == "base.front_outer_edges"
    assert model_data["operations"][2]["target"] == "base.back_outer_edges"
    assert check_model_data(model_data)["passed"] is True


def test_intent_lowering_normalizes_semantic_base_ids():
    intent = {
        "base": {
            "id": "shaft",
            "profile": "circle",
            "diameter": 20,
            "thickness": 80,
        },
        "features": [
            {
                "id": "center_boss",
                "operation": "extrusion",
                "target": "shaft.top",
                "shape": "circle",
                "diameter": 28,
                "distance": 5,
                "placement": {"type": "centered"},
            },
            {
                "id": "vague_cut",
                "operation": "cut",
                "target": "shaft",
                "shape": "circle",
                "diameter": 6,
                "depth": "through",
                "placement": {"type": "centered"},
            },
        ],
        "edge_treatments": [
            {
                "id": "outer_chamfer",
                "treatment": "chamfer",
                "target_feature": "shaft",
                "edge_selector": "top_outer_edges",
                "distance": 1,
            }
        ],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][0]["id"] == "base"
    assert model_data["operations"][1]["target"] == "base.top_outer_edges"
    assert model_data["operations"][2]["target"] == "base.top"
    assert model_data["operations"][3]["target"] == "base.top"


def test_cylinder_intent_lowers_to_revolved_base():
    intent = {
        "base": {
            "id": "shaft",
            "profile": "cylinder",
            "diameter": 20,
            "length": 80,
        },
        "features": [],
        "edge_treatments": [],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][0] == {
        "type": "revolve",
        "id": "base",
        "plane": "XY",
        "profile": "rectangle",
        "positions": [[5, 0]],
        "axis_start": [0, -1],
        "axis_end": [0, 1],
        "angle": 360,
        "width": 10,
        "height": 80.0,
    }
    assert check_model_data(model_data)["passed"] is True


def test_capsule_intent_lowers_to_arc_revolved_base():
    intent = {
        "base": {
            "id": "capsule_body",
            "profile": "capsule",
            "diameter": 20,
            "length": 80,
        },
        "features": [],
        "edge_treatments": [],
    }

    model_data = intent_to_model_data(intent)
    base_operation = model_data["operations"][0]

    assert base_operation["type"] == "revolve"
    assert base_operation["profile"] == "sketch"
    assert any(segment["type"] == "arc" for segment in base_operation["segments"])
    assert check_model_data(model_data)["passed"] is True


def test_revolved_collar_and_groove_intent_builds_on_cylinder():
    intent = {
        "base": {
            "id": "shaft",
            "profile": "cylinder",
            "diameter": 20,
            "length": 80,
        },
        "features": [
            {
                "id": "center_collar",
                "operation": "revolved_extrusion",
                "target": "shaft",
                "shape": "rectangle",
                "width": 4,
                "height": 10,
                "placement": {"type": "centered"},
            },
            {
                "id": "end_groove",
                "operation": "revolved_cut",
                "target": "shaft",
                "shape": "rectangle",
                "width": 2,
                "height": 4,
                "placement": {
                    "type": "offset_from_edge",
                    "edge": "front",
                    "offset": 8,
                    "along": 0,
                },
            },
        ],
        "edge_treatments": [],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][1]["type"] == "add_revolve"
    assert model_data["operations"][1]["positions"] == [[12, 0]]
    assert model_data["operations"][2]["type"] == "cut_revolve"
    assert model_data["operations"][2]["positions"] == [[9, 30]]
    assert check_model_data(model_data)["passed"] is True


def test_polyline_feature_intent_lowers_to_custom_profile_and_builds():
    intent = {
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 120,
            "height": 80,
            "thickness": 6,
        },
        "features": [
            {
                "id": "center_boss",
                "operation": "extrusion",
                "target": "base.top",
                "shape": "circle",
                "diameter": 20,
                "distance": 8,
                "placement": {"type": "centered"},
            },
            {
                "id": "gusset_rib",
                "operation": "extrusion",
                "target": "base.top",
                "shape": "polyline",
                "points": [[-15, 40], [15, 40], [0, 0]],
                "distance": 6,
                "placement": {
                    "type": "explicit",
                    "positions": [[0, 0]],
                },
            },
        ],
        "edge_treatments": [],
    }

    model_data = intent_to_model_data(intent)

    rib_operation = model_data["operations"][2]
    assert rib_operation["profile"] == "polyline"
    assert rib_operation["points"] == [[-15, 40], [15, 40], [0, 0]]
    assert check_model_data(model_data)["passed"] is True


def test_intent_normalizes_half_cylinder_flat_face_alias():
    intent = {
        "base": {
            "id": "half_round",
            "profile": "half_cylinder",
            "diameter": 30,
            "length": 80,
        },
        "features": [
            {
                "id": "mounting_tab",
                "operation": "extrusion",
                "target": "half_round.flat",
                "shape": "rectangle",
                "width": 30,
                "height": 10,
                "distance": 4,
                "placement": {"type": "centered"},
            }
        ],
        "edge_treatments": [],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][1]["target"] == "base.top"


def test_intent_normalizes_half_cylinder_curved_face_alias():
    intent = {
        "base": {
            "id": "half_round",
            "profile": "half_cylinder",
            "diameter": 30,
            "length": 80,
        },
        "features": [
            {
                "id": "top_groove",
                "operation": "cut",
                "target": "half_round.curved",
                "shape": "slot",
                "width": 4,
                "length": 50,
                "depth": 2,
                "placement": {"type": "centered"},
            }
        ],
        "edge_treatments": [],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][1]["target"] == "base.outer_surface"
    assert check_model_data(model_data)["passed"] is True


def test_revolved_polyline_cut_intent_lowers_for_countersink_style_feature():
    intent = {
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 80,
            "height": 40,
            "thickness": 6,
        },
        "features": [
            {
                "id": "countersink",
                "operation": "revolved_cut",
                "target": "base.top",
                "shape": "polyline",
                "points": [[2.5, 0], [7.5, 0], [0, -2.5]],
                "placement": {"type": "centered"},
            }
        ],
        "edge_treatments": [],
    }

    model_data = intent_to_model_data(intent)
    countersink = model_data["operations"][1]

    assert countersink["type"] == "cut_revolve"
    assert countersink["profile"] == "polyline"
    assert countersink["points"] == [[2.5, 0], [7.5, 0], [0, -2.5]]


def test_side_face_offset_uses_side_face_dimensions():
    intent = {
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 120,
            "height": 80,
            "thickness": 20,
        },
        "features": [
            {
                "id": "side_hole",
                "operation": "cut",
                "target": "base.right",
                "shape": "circle",
                "diameter": 10,
                "depth": "through",
                "placement": {
                    "type": "offset_from_edge",
                    "edge": "front",
                    "offset": 0,
                    "along": 0,
                },
            }
        ],
        "edge_treatments": [],
    }

    model_data = intent_to_model_data(intent)

    assert model_data["operations"][1]["positions"] == [[0, 5]]
    assert check_model_data(model_data)["passed"] is True


def test_counterbore_inherits_support_face_and_pattern_from_source_cut():
    intent = {
        "base": {
            "id": "plate",
            "profile": "rectangle",
            "width": 100,
            "height": 70,
            "thickness": 8,
        },
        "features": [
            {
                "id": "holes",
                "role": "hole",
                "operation": "cut",
                "target": "plate.top",
                "shape": "circle",
                "diameter": 6,
                "depth": "through",
                "placement": {
                    "type": "near_corners",
                    "count": 4,
                    "margin": 8,
                },
            },
            {
                "id": "counterbores",
                "role": "counterbore",
                "operation": "cut",
                "target": "holes.top",
                "shape": "circle",
                "diameter": 10,
                "depth": 2,
                "placement": {
                    "type": "same_as_feature",
                    "source_feature": "holes",
                },
            },
            {
                "id": "nested_recess",
                "role": "counterbore",
                "operation": "cut",
                "target": "counterbores.top",
                "shape": "circle",
                "diameter": 12,
                "depth": 1,
                "placement": {
                    "type": "same_as_feature",
                    "source_feature": "counterbores",
                },
            },
        ],
        "edge_treatments": [],
    }

    model_data = intent_to_model_data(intent)
    holes, counterbores, nested_recess = model_data["operations"][1:4]

    assert counterbores["target"] == "base.top"
    assert counterbores["positions"] == holes["positions"]
    assert nested_recess["target"] == "base.top"
    assert nested_recess["positions"] == counterbores["positions"]
    assert check_model_data(model_data)["passed"] is True


def test_planar_countersink_lowers_to_native_tapered_hole_feature():
    intent = {
        "base": {
            "id": "plate",
            "profile": "rectangle",
            "width": 100,
            "height": 40,
            "thickness": 8,
        },
        "features": [
            {
                "id": "holes",
                "role": "hole",
                "operation": "cut",
                "target": "plate.top",
                "shape": "circle",
                "diameter": 5,
                "depth": "through",
                "placement": {
                    "type": "rectangular_pattern",
                    "rows": 1,
                    "columns": 3,
                    "row_spacing": 0,
                    "column_spacing": 30,
                    "center": [0, 0],
                },
            },
            {
                "id": "countersinks",
                "role": "countersink",
                "operation": "revolved_cut",
                "target": "holes.top",
                "shape": "rectangle",
                "width": 2.5,
                "height": 2.5,
                "placement": {
                    "type": "same_as_feature",
                    "source_feature": "holes",
                },
            },
        ],
        "edge_treatments": [],
    }

    model_data = intent_to_model_data(intent)
    countersinks = model_data["operations"][2]

    assert countersinks["type"] == "countersink"
    assert countersinks["target"] == "base.top"
    assert countersinks["diameter"] == 5
    assert countersinks["countersink_diameter"] == 10
    assert countersinks["angle"] == 90
    assert countersinks["positions"] == model_data["operations"][1]["positions"]
    assert check_model_data(model_data)["passed"] is True
