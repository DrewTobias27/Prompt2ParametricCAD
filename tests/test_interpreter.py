"""Tests for the structured CAD operation interpreter."""

import math
from pathlib import Path

import pytest

from prompt2cad.interpreter import build_model
from prompt2cad.loader import load_model


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
                "x": 0,
                "y": 0,
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
                "x": 0,
                "y": 0,
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
                "x": 0,
                "y": 0,
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


def test_example_model():
    project_root = Path(__file__).resolve().parents[1]
    input_path = project_root / "examples" / "example_part.json"

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


def test_revolve_rejects_partial_angle():
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

    with pytest.raises(ValueError):
        build_model(model_data)


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
