"""Tests for CAD relationship constraints."""

from prompt2cad.diagnostics import check_model_data
from prompt2cad.relationships import check_relationships
from prompt2cad.relationships import validate_relationships

import pytest


def plate_with_boss_relationships(
    boss_position: list[float],
    boss_width: float = 20,
    boss_height: float = 10,
) -> dict:
    """Return a simple plate and boss model with relationship constraints."""
    return {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "distance": 6,
                "width": 100,
                "height": 60,
            },
            {
                "type": "add_extrude",
                "id": "boss",
                "target": "base.top",
                "profile": "rectangle",
                "positions": [boss_position],
                "distance": 6,
                "width": boss_width,
                "height": boss_height,
            },
        ],
        "relationships": [
            {
                "type": "centered_on",
                "feature": "boss",
                "reference": "base",
                "tolerance": 0.001,
            },
            {
                "type": "inside",
                "feature": "boss",
                "container": "base",
                "margin": 5,
            },
            {
                "type": "smaller_than",
                "feature": "boss",
                "reference": "base",
                "max_width_fraction": 0.6,
                "max_height_fraction": 0.6,
            },
            {
                "type": "must_connect",
                "feature": "boss",
                "to": "base",
            },
        ],
    }


def test_relationships_pass_for_centered_smaller_connected_boss():
    model_data = plate_with_boss_relationships([0, 0])

    result = check_relationships(model_data)

    assert result["passed"] is True


def test_centered_relationship_fails_for_offset_feature():
    model_data = plate_with_boss_relationships([12, 0])

    result = check_relationships(model_data)

    assert result["passed"] is False
    assert result["failures"][0]["relationship_type"] == "centered_on"
    assert "not centered" in result["failures"][0]["reason"]


def test_inside_relationship_fails_when_feature_exceeds_container_margin():
    model_data = plate_with_boss_relationships([45, 0])
    model_data["relationships"] = [
        {
            "type": "inside",
            "feature": "boss",
            "container": "base",
            "margin": 5,
        }
    ]

    result = check_relationships(model_data)

    assert result["passed"] is False
    assert result["failures"][0]["relationship_type"] == "inside"


def test_inside_relationship_supports_repeated_parent_instances():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "distance": 6,
                "width": 100,
                "height": 60,
            },
            {
                "type": "add_extrude",
                "id": "bosses",
                "target": "base.top",
                "profile": "circle",
                "positions": [[-30, 15], [30, 15], [-30, -15], [30, -15]],
                "distance": 6,
                "diameter": 16,
            },
            {
                "type": "cut",
                "id": "boss_holes",
                "target": "bosses.top",
                "profile": "circle",
                "positions": [[-30, 15], [30, 15], [-30, -15], [30, -15]],
                "depth": "through",
                "diameter": 5,
            },
        ],
        "relationships": [
            {
                "type": "inside",
                "feature": "boss_holes",
                "container": "bosses",
                "margin": 0,
            }
        ],
    }

    result = check_relationships(model_data)

    assert result["passed"] is True


def test_smaller_than_relationship_fails_when_feature_is_too_large():
    model_data = plate_with_boss_relationships(
        [0, 0],
        boss_width=80,
        boss_height=50,
    )
    model_data["relationships"] = [
        {
            "type": "smaller_than",
            "feature": "boss",
            "reference": "base",
            "max_width_fraction": 0.6,
            "max_height_fraction": 0.6,
        }
    ]

    result = check_relationships(model_data)

    assert result["passed"] is False
    assert result["failures"][0]["relationship_type"] == "smaller_than"


def test_must_connect_detects_feature_inside_prior_through_cut():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "distance": 6,
                "width": 100,
                "height": 100,
            },
            {
                "type": "cut",
                "id": "frame_opening",
                "target": "base.top",
                "profile": "rectangle",
                "positions": [[0, 0]],
                "depth": "through",
                "width": 60,
                "height": 60,
            },
            {
                "type": "add_extrude",
                "id": "center_block",
                "target": "base.top",
                "profile": "rectangle",
                "positions": [[0, 0]],
                "distance": 6,
                "width": 20,
                "height": 20,
            },
        ],
        "relationships": [
            {
                "type": "must_connect",
                "feature": "center_block",
                "to": "base",
            }
        ],
    }

    result = check_relationships(model_data)

    assert result["passed"] is False
    assert result["failures"][0]["relationship_type"] == "must_connect"
    assert "through-cut opening" in result["failures"][0]["reason"]


def test_validate_relationships_raises_on_failed_relationship():
    model_data = plate_with_boss_relationships([12, 0])

    with pytest.raises(ValueError, match="Relationship constraint failed"):
        validate_relationships(model_data)


def test_check_model_data_returns_relationship_failure_before_building():
    model_data = plate_with_boss_relationships([12, 0])

    result = check_model_data(model_data)

    assert result["passed"] is False
    assert result["failure_type"] == "relationship_constraint_failed"
