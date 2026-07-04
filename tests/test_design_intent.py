"""Tests for lowering high-level design intent into CAD operations."""

import pytest

from prompt2cad.design_intent import intent_to_model_data
from prompt2cad.design_intent import validate_design_intent
from prompt2cad.diagnostics import check_model_data
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
