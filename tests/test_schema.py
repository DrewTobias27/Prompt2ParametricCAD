"""Tests for CAD model schema validation."""

import pytest

from prompt2cad.schema import validate_model_data


@pytest.mark.parametrize(
    "operation",
    [
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
            "id": "base",
            "plane": "XY",
            "profile": "circle",
            "diameter": 30,
            "distance": 6,
        },
        {
            "type": "extrude",
            "id": "base",
            "plane": "XY",
            "profile": "polygon",
            "sides": 6,
            "diameter": 30,
            "distance": 6,
        },
        {
            "type": "extrude",
            "id": "base",
            "plane": "XY",
            "profile": "polyline",
            "points": [[-20, -10], [20, -10], [0, 15]],
            "distance": 6,
        },
        {
            "type": "revolve",
            "id": "base",
            "plane": "XY",
            "profile": "rectangle",
            "positions": [[5, 0]],
            "width": 10,
            "height": 20,
            "axis_start": [0, -1],
            "axis_end": [0, 1],
            "angle": 180,
        },
        {
            "type": "revolve",
            "id": "base",
            "plane": "XY",
            "profile": "circle",
            "positions": [[5, 0]],
            "diameter": 10,
            "axis_start": [0, -1],
            "axis_end": [0, 1],
            "angle": 360,
        },
        {
            "type": "revolve",
            "id": "base",
            "plane": "XY",
            "profile": "polygon",
            "positions": [[5, 0]],
            "sides": 6,
            "diameter": 10,
            "axis_start": [0, -1],
            "axis_end": [0, 1],
            "angle": 360,
        },
        {
            "type": "revolve",
            "id": "base",
            "plane": "XY",
            "profile": "polyline",
            "positions": [[5, 0]],
            "points": [[-2, -5], [2, -5], [2, 5], [-2, 5]],
            "axis_start": [0, -1],
            "axis_end": [0, 1],
            "angle": 360,
        },
        {
            "type": "add_extrude",
            "target": "base.top",
            "profile": "rectangle",
            "positions": [[0, 0]],
            "width": 20,
            "height": 10,
            "distance": 5,
        },
        {
            "type": "add_extrude",
            "target": "base.top",
            "profile": "circle",
            "positions": [[0, 0]],
            "diameter": 10,
            "distance": 5,
        },
        {
            "type": "add_extrude",
            "target": "base.top",
            "profile": "polygon",
            "positions": [[0, 0]],
            "sides": 5,
            "diameter": 12,
            "distance": 5,
        },
        {
            "type": "add_extrude",
            "target": "base.top",
            "profile": "polyline",
            "positions": [[0, 0]],
            "points": [[-5, -5], [5, -5], [0, 5]],
            "distance": 5,
        },
        {
            "type": "cut",
            "target": "base.top",
            "profile": "rectangle",
            "positions": [[0, 0]],
            "width": 20,
            "height": 10,
            "depth": "through",
        },
        {
            "type": "cut",
            "target": "base.top",
            "profile": "circle",
            "positions": [[0, 0]],
            "diameter": 10,
            "depth": "through",
        },
        {
            "type": "cut",
            "target": "base.top",
            "profile": "polygon",
            "positions": [[0, 0]],
            "sides": 5,
            "diameter": 12,
            "depth": 4,
        },
        {
            "type": "cut",
            "target": "base.top",
            "profile": "polyline",
            "positions": [[0, 0]],
            "points": [[-5, -5], [5, -5], [0, 5]],
            "depth": 4,
        },
        {
            "type": "add_revolve",
            "plane": "XY",
            "profile": "rectangle",
            "positions": [[11, 0]],
            "width": 2,
            "height": 6,
            "axis_start": [0, -1],
            "axis_end": [0, 1],
            "angle": 360,
        },
        {
            "type": "add_revolve",
            "plane": "XY",
            "profile": "circle",
            "positions": [[11, 0]],
            "diameter": 2,
            "axis_start": [0, -1],
            "axis_end": [0, 1],
            "angle": 360,
        },
        {
            "type": "add_revolve",
            "plane": "XY",
            "profile": "polygon",
            "positions": [[11, 0]],
            "sides": 6,
            "diameter": 2,
            "axis_start": [0, -1],
            "axis_end": [0, 1],
            "angle": 360,
        },
        {
            "type": "add_revolve",
            "plane": "XY",
            "profile": "polyline",
            "positions": [[11, 0]],
            "points": [[-1, -3], [1, -3], [1, 3], [-1, 3]],
            "axis_start": [0, -1],
            "axis_end": [0, 1],
            "angle": 360,
        },
        {
            "type": "cut_revolve",
            "plane": "XY",
            "profile": "rectangle",
            "positions": [[9, 0]],
            "width": 2,
            "height": 4,
            "axis_start": [0, -1],
            "axis_end": [0, 1],
            "angle": 360,
        },
        {
            "type": "cut_revolve",
            "plane": "XY",
            "profile": "circle",
            "positions": [[9, 0]],
            "diameter": 2,
            "axis_start": [0, -1],
            "axis_end": [0, 1],
            "angle": 360,
        },
        {
            "type": "cut_revolve",
            "plane": "XY",
            "profile": "polygon",
            "positions": [[9, 0]],
            "sides": 6,
            "diameter": 2,
            "axis_start": [0, -1],
            "axis_end": [0, 1],
            "angle": 360,
        },
        {
            "type": "cut_revolve",
            "plane": "XY",
            "profile": "polyline",
            "positions": [[9, 0]],
            "points": [[-1, -2], [1, -2], [1, 2], [-1, 2]],
            "axis_start": [0, -1],
            "axis_end": [0, 1],
            "angle": 360,
        },
    ],
)
def test_validate_model_data_accepts_supported_operation_schema(operation):
    validate_model_data({"operations": [operation]})


def test_validate_model_data_rejects_missing_width():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "height": 50,
                "distance": 6,
            }
        ]
    }

    with pytest.raises(ValueError):
        validate_model_data(model_data)


def test_validate_model_data_rejects_revolve_angle_over_360():
    model_data = {
        "operations": [
            {
                "type": "revolve",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "positions": [[5, 0]],
                "width": 10,
                "height": 20,
                "axis_start": [0, -1],
                "axis_end": [0, 1],
                "angle": 361,
            }
        ]
    }

    with pytest.raises(ValueError):
        validate_model_data(model_data)
