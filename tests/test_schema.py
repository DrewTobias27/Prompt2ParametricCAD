"""Tests for CAD model schema validation."""

import pytest

from prompt2cad.schema import validate_model_data


def test_validate_model_data_accepts_rectangular_extrude():
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

    validate_model_data(model_data)


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

    with pytest.raises(ValueError, match="width"):
        validate_model_data(model_data)