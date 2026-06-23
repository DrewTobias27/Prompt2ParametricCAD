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
