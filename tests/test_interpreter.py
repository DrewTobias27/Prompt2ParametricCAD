"""Tests for the structured CAD operation interpreter."""

import math
from pathlib import Path

import pytest

from prompt2cad.interpreter import build_model
from prompt2cad.loader import load_model
from prompt2cad.schema import validate_model_data


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PATHS = sorted((PROJECT_ROOT / "examples").glob("*.json"))


def test_rectangular_base_dimensions():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 80,
                "height": 50,
                "distance": 6,
            }
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()
    bounding_box = solid.BoundingBox()

    assert bounding_box.xlen == 80
    assert bounding_box.ylen == 50
    assert bounding_box.zlen == 6


@pytest.mark.parametrize(
    "dimension, invalid_value",
    [
        ("width", 0),
        ("width", -1),
        ("height", 0),
        ("height", -1),
        ("distance", 0),
        ("distance", -1),
        ("width", True),
        ("height", True),
        ("distance", True),
    ],
)
def test_invalid_base_dimension(dimension, invalid_value):
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 80,
                "height": 50,
                "distance": 6,
            }
        ]
    }

    operation = model_data["operations"][0]
    operation[dimension] = invalid_value

    with pytest.raises(ValueError):
        build_model(model_data)


def test_rejects_boolean_profile_position():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 80,
                "height": 50,
                "distance": 6,
            },
            {
                "type": "cut",
                "target": "base.top",
                "profile": "circle",
                "positions": [[True, 0]],
                "diameter": 10,
                "depth": "through",
            },
        ]
    }

    with pytest.raises(ValueError):
        build_model(model_data)


def test_add_extrusion():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 80,
                "height": 50,
                "distance": 6,
            },
            {
                "type": "add_extrude",
                "target": "base.top",
                "profile": "rectangle",
                "positions": [[0, 0]],
                "width": 20,
                "height": 15,
                "distance": 8,
            },
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()
    bounding_box = solid.BoundingBox()
    assert bounding_box.zlen == 14


@pytest.mark.parametrize(
    "cut_operation, expected_removed_volume",
    [
        (
            {
                "type": "cut",
                "target": "base.top",
                "profile": "rectangle",
                "width": 20,
                "height": 10,
                "positions": [[0, 0]],
                "depth": "through",
            },
            20 * 10 * 6,
        ),
        (
            {
                "type": "cut",
                "target": "base.top",
                "profile": "rectangle",
                "width": 20,
                "height": 10,
                "positions": [[0, 0]],
                "depth": 3,
            },
            20 * 10 * 3,
        ),
        (
            {
                "type": "cut",
                "target": "base.top",
                "profile": "circle",
                "diameter": 10,
                "positions": [[0, 0]],
                "depth": "through",
            },
            math.pi * 5**2 * 6,
        ),
        (
            {
                "type": "cut",
                "target": "base.top",
                "profile": "circle",
                "diameter": 10,
                "positions": [[0, 0]],
                "depth": 3,
            },
            math.pi * 5**2 * 3,
        ),
    ],
)
def test_cut_volumes(cut_operation, expected_removed_volume):
    base_operation = {
        "type": "extrude",
        "id": "base",
        "plane": "XY",
        "profile": "rectangle",
        "width": 80,
        "height": 50,
        "distance": 6,
    }
    model_data = {"operations": [base_operation, cut_operation]}

    part = build_model(model_data)
    solid = part.solids().val()
    base_volume = 80 * 50 * 6
    actual_removed_volume = base_volume - solid.Volume()

    assert actual_removed_volume == pytest.approx(expected_removed_volume)


@pytest.mark.parametrize("input_path", EXAMPLE_PATHS)
def test_example_files_validate_and_build(input_path):
    model_data = load_model(input_path)

    validate_model_data(model_data)
    build_model(model_data)


def test_example_model():
    input_path = PROJECT_ROOT / "examples" / "example_part.json"

    model_data = load_model(input_path)
    part = build_model(model_data)
    solids = part.solids().vals()

    assert len(solids) == 1

    solid = solids[0]
    bounding_box = solid.BoundingBox()

    assert bounding_box.xlen == 80
    assert bounding_box.ylen == 50
    assert bounding_box.zlen == 14
    assert solid.Volume() == pytest.approx(24180.531085492374)


def test_multiple_rectangle_cuts():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 80,
                "height": 50,
                "distance": 6,
            },
            {
                "type": "cut",
                "target": "base.top",
                "profile": "rectangle",
                "width": 10,
                "height": 5,
                "positions": [[-20, 0], [20, 0]],
                "depth": "through",
            },
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()
    base_volume = 80 * 50 * 6
    actual_removed_volume = base_volume - solid.Volume()

    assert actual_removed_volume == pytest.approx(10 * 5 * 6 * 2)


def test_multiple_circle_extrusions():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 80,
                "height": 50,
                "distance": 6,
            },
            {
                "type": "add_extrude",
                "target": "base.top",
                "profile": "circle",
                "diameter": 10,
                "positions": [[-20, 0], [20, 0]],
                "distance": 8,
            },
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()
    base_volume = 80 * 50 * 6
    actual_added_volume = solid.Volume() - base_volume
    expected_added_volume = 2 * math.pi * 5**2 * 8

    assert actual_added_volume == pytest.approx(expected_added_volume)


def test_polygon_extrusion():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 80,
                "height": 50,
                "distance": 6,
            },
            {
                "type": "add_extrude",
                "target": "base.top",
                "profile": "polygon",
                "sides": 6,
                "diameter": 20,
                "positions": [[0, 0]],
                "distance": 8,
            },
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()

    base_volume = 80 * 50 * 6
    actual_added_volume = solid.Volume() - base_volume

    radius = 20 / 2
    expected_area = (3 * math.sqrt(3) / 2) * radius**2
    expected_added_volume = expected_area * 8

    assert actual_added_volume == pytest.approx(expected_added_volume)


def test_polyline_extrusion():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 80,
                "height": 50,
                "distance": 6,
            },
            {
                "type": "add_extrude",
                "target": "base.top",
                "profile": "polyline",
                "points": [
                    [-10, -10],
                    [10, -10],
                    [10, 0],
                    [0, 0],
                    [0, 10],
                    [-10, 10],
                ],
                "positions": [[0, 0]],
                "distance": 8,
            },
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()

    base_volume = 80 * 50 * 6
    actual_added_volume = solid.Volume() - base_volume

    # 20 by 20 square minus the missing 10 by 10 corner.
    expected_area = 20 * 20 - 10 * 10
    expected_added_volume = expected_area * 8

    assert actual_added_volume == pytest.approx(expected_added_volume)


def test_line_arc_sketch():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 80,
                "height": 50,
                "distance": 6,
            },
            {
                "type": "add_extrude",
                "target": "base.top",
                "profile": "sketch",
                "start": [-10, -10],
                "segments": [
                    {
                        "type": "line",
                        "to": [10, -10],
                    },
                    {
                        "type": "arc",
                        "through": [20, 0],
                        "to": [10, 10],
                    },
                    {
                        "type": "line",
                        "to": [-10, 10],
                    },
                ],
                "close": True,
                "positions": [[0, 0]],
                "distance": 8,
            },
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()

    base_volume = 80 * 50 * 6
    actual_added_volume = solid.Volume() - base_volume

    rectangle_area = 20 * 20
    semicircle_area = 0.5 * math.pi * 10**2
    expected_added_volume = (rectangle_area + semicircle_area) * 8

    assert actual_added_volume == pytest.approx(expected_added_volume)


def test_sketch_ignores_zero_length_line_segment():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "sketch",
                "distance": 5,
                "start": [0, 0],
                "segments": [
                    {
                        "type": "line",
                        "to": [0, 0],
                    },
                    {
                        "type": "line",
                        "to": [20, 0],
                    },
                    {
                        "type": "line",
                        "to": [20, 10],
                    },
                    {
                        "type": "line",
                        "to": [0, 10],
                    },
                ],
                "close": True,
            }
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()

    assert solid.Volume() == pytest.approx(20 * 10 * 5)


def test_sketch_degrades_collinear_arc_to_line():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "sketch",
                "distance": 5,
                "start": [0, 0],
                "segments": [
                    {
                        "type": "arc",
                        "through": [10, 0],
                        "to": [20, 0],
                    },
                    {
                        "type": "line",
                        "to": [20, 10],
                    },
                    {
                        "type": "line",
                        "to": [0, 10],
                    },
                ],
                "close": True,
            }
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()

    assert solid.Volume() == pytest.approx(20 * 10 * 5)


def test_circle_base():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "circle",
                "diameter": 20,
                "distance": 6,
            }
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()

    expected_volume = math.pi * 10**2 * 6

    assert solid.Volume() == pytest.approx(expected_volume)


def test_revolved_cylinder_base():
    model_data = {
        "operations": [
            {
                "type": "revolve",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 10,
                "height": 20,
                "positions": [[5, 0]],
                "angle": 360,
                "axis_start": [0, -1],
                "axis_end": [0, 1],
                "face_tags": {
                    "front": ">Y",
                    "back": "<Y",
                },
            }
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()
    expected_volume = math.pi * 10**2 * 20

    assert solid.Volume() == pytest.approx(expected_volume)


def test_revolved_half_cylinder_base():
    model_data = {
        "operations": [
            {
                "type": "revolve",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 10,
                "height": 20,
                "positions": [[5, 0]],
                "angle": 180,
                "axis_start": [0, -1],
                "axis_end": [0, 1],
                "face_tags": {
                    "front": ">Y",
                    "back": "<Y",
                },
            }
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()
    expected_volume = math.pi * 10**2 * 20 / 2

    assert solid.Volume() == pytest.approx(expected_volume)


def test_revolved_axis_touching_polyline_base():
    model_data = {
        "operations": [
            {
                "type": "revolve",
                "id": "base",
                "plane": "XY",
                "profile": "polyline",
                "positions": [[0, 0]],
                "angle": 360,
                "axis_start": [0, -1],
                "axis_end": [0, 1],
                "points": [
                    [0, -30],
                    [3.827, -29.239],
                    [7.071, -27.071],
                    [9.239, -23.827],
                    [10, -20],
                    [10, 20],
                    [9.239, 23.827],
                    [7.071, 27.071],
                    [3.827, 29.239],
                    [0, 30],
                ],
            }
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()
    bounding_box = solid.BoundingBox()

    assert bounding_box.xlen == pytest.approx(20)
    assert bounding_box.ylen == pytest.approx(60)
    assert bounding_box.zlen == pytest.approx(20)


def test_revolved_axis_touching_arc_sketch_base():
    model_data = {
        "operations": [
            {
                "type": "revolve",
                "id": "base",
                "plane": "XY",
                "profile": "sketch",
                "positions": [[0, 0]],
                "angle": 360,
                "axis_start": [0, -1],
                "axis_end": [0, 1],
                "start": [0, -30],
                "segments": [
                    {
                        "type": "arc",
                        "through": [5, -28.660254],
                        "to": [10, -20],
                    },
                    {
                        "type": "line",
                        "to": [10, 20],
                    },
                    {
                        "type": "arc",
                        "through": [5, 28.660254],
                        "to": [0, 30],
                    },
                    {
                        "type": "line",
                        "to": [0, -30],
                    },
                ],
                "close": True,
            }
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()
    bounding_box = solid.BoundingBox()

    assert bounding_box.xlen == pytest.approx(20)
    assert bounding_box.ylen == pytest.approx(60)
    assert bounding_box.zlen == pytest.approx(20)


def test_add_revolved_collar_to_cylinder():
    model_data = {
        "operations": [
            {
                "type": "revolve",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 10,
                "height": 40,
                "positions": [[5, 0]],
                "angle": 360,
                "axis_start": [0, -1],
                "axis_end": [0, 1],
            },
            {
                "type": "add_revolve",
                "plane": "XY",
                "profile": "rectangle",
                "width": 2,
                "height": 6,
                "positions": [[11, 0]],
                "angle": 360,
                "axis_start": [0, -1],
                "axis_end": [0, 1],
            },
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()

    base_volume = math.pi * 10**2 * 40
    collar_volume = math.pi * (12**2 - 10**2) * 6

    assert solid.Volume() == pytest.approx(base_volume + collar_volume)


def test_add_revolve_projects_tangent_feature_until_connected():
    model_data = {
        "operations": [
            {
                "type": "revolve",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 10,
                "height": 40,
                "positions": [[5, 0]],
                "angle": 360,
                "axis_start": [0, -1],
                "axis_end": [0, 1],
            },
            {
                "type": "add_revolve",
                "plane": "XY",
                "profile": "rectangle",
                "width": 2,
                "height": 12,
                "positions": [[12, 0]],
                "angle": 360,
                "axis_start": [0, -1],
                "axis_end": [0, 1],
            },
        ]
    }

    part = build_model(model_data)
    solids = part.solids().vals()

    assert len(solids) == 1


def test_add_revolve_projects_far_feature_until_connected():
    model_data = {
        "operations": [
            {
                "type": "revolve",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 10,
                "height": 40,
                "positions": [[5, 0]],
                "angle": 360,
                "axis_start": [0, -1],
                "axis_end": [0, 1],
            },
            {
                "type": "add_revolve",
                "plane": "XY",
                "profile": "rectangle",
                "width": 2,
                "height": 12,
                "positions": [[18, 0]],
                "angle": 360,
                "axis_start": [0, -1],
                "axis_end": [0, 1],
            },
        ]
    }

    part = build_model(model_data)
    solids = part.solids().vals()

    assert len(solids) == 1


def test_cut_revolved_groove_from_cylinder():
    model_data = {
        "operations": [
            {
                "type": "revolve",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 10,
                "height": 40,
                "positions": [[5, 0]],
                "angle": 360,
                "axis_start": [0, -1],
                "axis_end": [0, 1],
            },
            {
                "type": "cut_revolve",
                "plane": "XY",
                "profile": "rectangle",
                "width": 2,
                "height": 4,
                "positions": [[9, 0]],
                "angle": 360,
                "axis_start": [0, -1],
                "axis_end": [0, 1],
            },
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()

    base_volume = math.pi * 10**2 * 40
    groove_volume = math.pi * (10**2 - 8**2) * 4

    assert solid.Volume() == pytest.approx(base_volume - groove_volume)


def test_revolve_rejects_angle_greater_than_360():
    model_data = {
        "operations": [
            {
                "type": "revolve",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 10,
                "height": 20,
                "positions": [[5, 0]],
                "angle": 361,
                "axis_start": [0, -1],
                "axis_end": [0, 1],
            }
        ]
    }

    with pytest.raises(ValueError, match="greater than 360"):
        build_model(model_data)


def test_rejects_legacy_xy_positions():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 80,
                "height": 50,
                "distance": 6,
            },
            {
                "type": "cut",
                "target": "base.top",
                "profile": "circle",
                "x": 0,
                "y": 0,
                "diameter": 10,
                "depth": "through",
            },
        ]
    }

    with pytest.raises(ValueError, match="positions is required"):
        build_model(model_data)


def test_rejects_cut_before_base():
    model_data = {
        "operations": [
            {
                "type": "cut",
                "target": "base.top",
                "profile": "circle",
                "positions": [[0, 0]],
                "diameter": 10,
                "depth": "through",
            }
        ]
    }

    with pytest.raises(ValueError, match="Operation 1 must create"):
        build_model(model_data)


def test_rejects_second_base_operation():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 80,
                "height": 50,
                "distance": 6,
            },
            {
                "type": "extrude",
                "id": "second_base",
                "plane": "XY",
                "profile": "circle",
                "diameter": 20,
                "distance": 5,
            },
        ]
    }

    with pytest.raises(ValueError, match="only one base operation"):
        build_model(model_data)


def test_invalid_target_tag_has_clear_error():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 80,
                "height": 50,
                "distance": 6,
            },
            {
                "type": "cut",
                "target": "base.Top",
                "profile": "circle",
                "positions": [[0, 0]],
                "diameter": 10,
                "depth": "through",
            },
        ]
    }

    with pytest.raises(ValueError, match="target 'base.Top' was not found"):
        build_model(model_data)


def test_cut_extruded_front_face_with_default_tag():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 80,
                "height": 50,
                "distance": 20,
            },
            {
                "type": "cut",
                "target": "base.front",
                "profile": "circle",
                "diameter": 10,
                "positions": [[0, 0]],
                "depth": "through",
            },
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()

    original_volume = 80 * 50 * 20
    expected_removed_volume = math.pi * 5**2 * 50

    assert solid.Volume() == pytest.approx(
        original_volume - expected_removed_volume
    )


def test_through_cut_from_feature_face_continues_into_base():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 80,
                "height": 50,
                "distance": 6,
            },
            {
                "type": "add_extrude",
                "id": "feature_1",
                "target": "base.top",
                "profile": "rectangle",
                "positions": [[0, 0]],
                "distance": 6,
                "width": 20,
                "height": 12,
            },
            {
                "type": "cut",
                "target": "feature_1.top",
                "profile": "circle",
                "positions": [[0, 0]],
                "depth": "through",
                "diameter": 5,
            },
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()

    original_volume = 80 * 50 * 6 + 20 * 12 * 6
    expected_removed_volume = math.pi * 2.5**2 * 12

    assert solid.Volume() == pytest.approx(
        original_volume - expected_removed_volume
    )


def test_add_extrude_uses_virtual_side_target_for_polyline_base():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "polyline",
                "distance": 6,
                "points": [
                    [0, 0],
                    [60, 0],
                    [75, 30],
                    [15, 30],
                ],
            },
            {
                "type": "add_extrude",
                "target": "base.back",
                "profile": "rectangle",
                "positions": [[0, 0]],
                "distance": 5,
                "width": 10,
                "height": 4,
            },
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()
    bounding_box = solid.BoundingBox()

    base_volume = 60 * 30 * 6
    added_volume = 10 * 4 * 5

    assert solid.Volume() == pytest.approx(base_volume + added_volume)
    assert bounding_box.ymin == pytest.approx(-5)


def test_cut_uses_virtual_side_target_for_polyline_base():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "polyline",
                "distance": 6,
                "points": [
                    [0, 0],
                    [60, 0],
                    [75, 30],
                    [15, 30],
                ],
            },
            {
                "type": "cut",
                "target": "base.back",
                "profile": "rectangle",
                "positions": [[0, 0]],
                "depth": 5,
                "width": 10,
                "height": 4,
            },
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()

    base_volume = 60 * 30 * 6
    removed_volume = 10 * 4 * 5

    assert solid.Volume() == pytest.approx(base_volume - removed_volume)


def test_side_extrude_normalizes_misplaced_vertical_position():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "distance": 10,
                "width": 100,
                "height": 100,
            },
            {
                "type": "cut",
                "target": "base.top",
                "profile": "circle",
                "positions": [
                    [40, 40],
                    [-40, 40],
                    [40, -40],
                ],
                "depth": "through",
                "diameter": 8,
            },
            {
                "type": "add_extrude",
                "target": "base.front",
                "profile": "rectangle",
                "positions": [[30, 0]],
                "distance": 12,
                "width": 12,
                "height": 12,
            },
            {
                "type": "add_extrude",
                "target": "base.right",
                "profile": "rectangle",
                "positions": [[0, 30]],
                "distance": 12,
                "width": 12,
                "height": 12,
            },
        ]
    }

    part = build_model(model_data)
    solids = part.solids().vals()

    assert len(solids) == 1


def test_added_extrusion_side_face_can_be_targeted():
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
                "type": "add_extrude",
                "id": "feature_1",
                "target": "base.top",
                "profile": "rectangle",
                "positions": [[20, 0]],
                "distance": 10,
                "width": 20,
                "height": 12,
            },
            {
                "type": "add_extrude",
                "target": "feature_1.right",
                "profile": "rectangle",
                "positions": [[0, 0]],
                "distance": 8,
                "width": 8,
                "height": 6,
            },
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()
    bounding_box = solid.BoundingBox()

    assert len(part.solids().vals()) == 1
    assert bounding_box.xmax > 37


def test_side_extrude_overlaps_rounded_virtual_target_until_connected():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "sketch",
                "distance": 8,
                "start": [-42, -35],
                "segments": [
                    {
                        "type": "arc",
                        "through": [-50, -35],
                        "to": [-50, -27],
                    },
                    {
                        "type": "line",
                        "to": [-50, 27],
                    },
                    {
                        "type": "arc",
                        "through": [-50, 35],
                        "to": [-42, 35],
                    },
                    {
                        "type": "line",
                        "to": [42, 35],
                    },
                    {
                        "type": "arc",
                        "through": [50, 35],
                        "to": [50, 27],
                    },
                    {
                        "type": "line",
                        "to": [50, -27],
                    },
                    {
                        "type": "arc",
                        "through": [50, -35],
                        "to": [42, -35],
                    },
                    {
                        "type": "line",
                        "to": [-42, -35],
                    },
                ],
                "close": True,
            },
            {
                "type": "cut",
                "target": "base.top",
                "profile": "circle",
                "positions": [
                    [38, 23],
                    [38, -23],
                    [-38, 23],
                    [-38, -23],
                ],
                "depth": "through",
                "diameter": 6,
            },
            {
                "type": "add_extrude",
                "target": "base.top",
                "profile": "rectangle",
                "positions": [[0, 0]],
                "distance": 4,
                "width": 40,
                "height": 20,
            },
            {
                "type": "cut",
                "target": "base.top",
                "profile": "circle",
                "positions": [[0, 0]],
                "depth": "through",
                "diameter": 10,
            },
            {
                "type": "add_extrude",
                "target": "base.front",
                "profile": "rectangle",
                "positions": [[0, 0]],
                "distance": 6,
                "width": 20,
                "height": 10,
            },
            {
                "type": "cut",
                "target": "base.right",
                "profile": "rectangle",
                "positions": [[0, 0]],
                "depth": 3,
                "width": 30,
                "height": 6,
            },
        ]
    }

    part = build_model(model_data)
    solids = part.solids().vals()

    assert len(solids) == 1


def test_side_extrude_projects_extreme_position_toward_side_center():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "polyline",
                "distance": 8,
                "points": [
                    [-40, -25],
                    [40, -25],
                    [30, 25],
                    [-30, 25],
                ],
            },
            {
                "type": "add_extrude",
                "target": "base.front",
                "profile": "rectangle",
                "positions": [[40, 0]],
                "distance": 5,
                "width": 10,
                "height": 6,
            },
        ]
    }

    part = build_model(model_data)
    solids = part.solids().vals()

    assert len(solids) == 1


def test_cut_revolved_front_face():
    model_data = {
        "operations": [
            {
                "type": "revolve",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 10,
                "height": 20,
                "positions": [[5, 0]],
                "angle": 360,
                "axis_start": [0, -1],
                "axis_end": [0, 1],
                "face_tags": {
                    "front": ">Y",
                    "back": "<Y",
                },
            },
            {
                "type": "cut",
                "target": "base.front",
                "profile": "circle",
                "diameter": 4,
                "positions": [[0, 0]],
                "depth": "through",
            },
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()

    original_volume = math.pi * 10**2 * 20
    expected_removed_volume = math.pi * 2**2 * 20

    assert solid.Volume() == pytest.approx(
        original_volume - expected_removed_volume
    )


def test_cut_revolve_discards_disconnected_scrap():
    model_data = {
        "operations": [
            {
                "type": "revolve",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "positions": [[5, 0]],
                "axis_start": [0, -1],
                "axis_end": [0, 1],
                "angle": 360,
                "width": 10,
                "height": 120,
            },
            {
                "type": "add_revolve",
                "plane": "XY",
                "profile": "rectangle",
                "positions": [[12, 0]],
                "axis_start": [0, -1],
                "axis_end": [0, 1],
                "angle": 360,
                "width": 4,
                "height": 12,
            },
            {
                "type": "cut_revolve",
                "plane": "XY",
                "profile": "rectangle",
                "positions": [[13, 0]],
                "axis_start": [0, -1],
                "axis_end": [0, 1],
                "angle": 360,
                "width": 1,
                "height": 12,
            },
            {
                "type": "cut",
                "target": "base.front",
                "profile": "circle",
                "positions": [[6, 0]],
                "depth": "through",
                "diameter": 6,
            },
        ]
    }

    part = build_model(model_data)
    solids = part.solids().vals()

    assert len(solids) == 1
    assert solids[0].isValid()


def test_polyline_cut():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 80,
                "height": 50,
                "distance": 6,
            },
            {
                "type": "cut",
                "target": "base.top",
                "profile": "polyline",
                "points": [
                    [-10, -10],
                    [10, -10],
                    [10, 0],
                    [0, 0],
                    [0, 10],
                    [-10, 10],
                ],
                "positions": [[0, 0]],
                "depth": "through",
            },
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()

    base_volume = 80 * 50 * 6
    actual_removed_volume = base_volume - solid.Volume()

    expected_area = 20 * 20 - 10 * 10
    expected_removed_volume = expected_area * 6

    assert actual_removed_volume == pytest.approx(expected_removed_volume)


def test_line_arc_cut():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 80,
                "height": 50,
                "distance": 6,
            },
            {
                "type": "cut",
                "target": "base.top",
                "profile": "sketch",
                "start": [-10, -10],
                "segments": [
                    {
                        "type": "line",
                        "to": [10, -10],
                    },
                    {
                        "type": "arc",
                        "through": [20, 0],
                        "to": [10, 10],
                    },
                    {
                        "type": "line",
                        "to": [-10, 10],
                    },
                ],
                "close": True,
                "positions": [[0, 0]],
                "depth": "through",
            },
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()

    base_volume = 80 * 50 * 6
    actual_removed_volume = base_volume - solid.Volume()

    rectangle_area = 20 * 20
    semicircle_area = 0.5 * math.pi * 10**2
    expected_removed_volume = (rectangle_area + semicircle_area) * 6

    assert actual_removed_volume == pytest.approx(expected_removed_volume)


def test_api_rectangular_plate_example():
    input_path = PROJECT_ROOT / "examples" / "api_rectangular_plate.json"

    model_data = load_model(input_path)
    part = build_model(model_data)
    solid = part.solids().val()

    assert solid.Volume() == pytest.approx(80 * 50 * 6)


def test_named_multi_position_add_extrude_builds_one_valid_model():
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
                "type": "add_extrude",
                "target": "base.top",
                "profile": "rectangle",
                "positions": [
                    [30, 19],
                    [-30, 19],
                    [30, -19],
                    [-30, -19],
                ],
                "id": "feature_1",
                "distance": 6,
                "width": 20,
                "height": 12,
            },
        ]
    }

    validate_model_data(model_data)
    part = build_model(model_data)
    solid = part.solids().val()

    base_volume = 80 * 50 * 6
    added_volume = 4 * 20 * 12 * 6

    assert len(part.solids().vals()) == 1
    assert solid.isValid()
    assert solid.Volume() == pytest.approx(base_volume + added_volume)


def test_chamfer_top_outer_edges_builds_valid_modified_solid():
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

    part = build_model(model_data)
    solid = part.solids().val()

    assert len(part.solids().vals()) == 1
    assert solid.isValid()
    assert solid.Volume() < 80 * 50 * 6


def test_chamfer_added_feature_top_outer_edges_uses_registered_edge_group():
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
                "type": "add_extrude",
                "id": "feature_1",
                "target": "base.top",
                "profile": "rectangle",
                "positions": [[0, 0]],
                "distance": 8,
                "width": 20,
                "height": 12,
            },
            {
                "type": "chamfer",
                "id": "boss_top_chamfer",
                "target": "feature_1.top_outer_edges",
                "distance": 1,
            },
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()

    base_volume = 80 * 50 * 6
    boss_volume = 20 * 12 * 8

    assert len(part.solids().vals()) == 1
    assert solid.isValid()
    assert solid.Volume() < base_volume + boss_volume
    assert solid.Volume() > base_volume


def test_chamfer_circular_boss_uses_generalized_edge_group():
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
                "type": "add_extrude",
                "id": "feature_1",
                "target": "base.top",
                "profile": "circle",
                "positions": [[0, 0]],
                "distance": 8,
                "diameter": 24,
            },
            {
                "type": "chamfer",
                "id": "boss_top_chamfer",
                "target": "feature_1.top_outer_edges",
                "distance": 1,
            },
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()

    base_volume = 80 * 50 * 6
    boss_volume = math.pi * 12**2 * 8

    assert len(part.solids().vals()) == 1
    assert solid.isValid()
    assert solid.Volume() < base_volume + boss_volume
    assert solid.Volume() > base_volume


def test_fillet_vertical_edges_builds_valid_modified_solid():
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
                "type": "fillet",
                "id": "vertical_fillet",
                "target": "base.vertical_edges",
                "radius": 1,
            },
        ]
    }

    part = build_model(model_data)
    solid = part.solids().val()

    assert len(part.solids().vals()) == 1
    assert solid.isValid()
    assert solid.Volume() < 80 * 50 * 8


def test_edge_treatment_rejects_unknown_edge_selector():
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
                "id": "bad_chamfer",
                "target": "base.random_edges",
                "distance": 1,
            },
        ]
    }

    with pytest.raises(ValueError, match="unsupported edge selector"):
        build_model(model_data)
