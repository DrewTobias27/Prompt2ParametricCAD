import pytest

from prompt2cad.pattern_geometry import pattern_positions
from prompt2cad.pattern_geometry import synchronize_pattern_positions
from prompt2cad.pattern_geometry import validate_pattern_positions


def test_circular_pattern_positions_support_closed_and_partial_spans():
    full_pattern = {
        "type": "circular",
        "seed_position": [20, 0],
        "center": [0, 0],
        "count": 4,
        "total_angle_degrees": 360,
    }
    partial_pattern = {**full_pattern, "count": 3, "total_angle_degrees": 180}

    assert pattern_positions(full_pattern) == [
        [20.0, 0.0],
        [0.0, 20.0],
        [-20.0, 0.0],
        [0.0, -20.0],
    ]
    assert pattern_positions(partial_pattern) == [
        [20.0, 0.0],
        [0.0, 20.0],
        [-20.0, 0.0],
    ]


def test_linear_pattern_normalizes_directions_and_orders_instances_by_axis():
    assert pattern_positions(
        {
            "type": "linear",
            "seed_position": [-20, -10],
            "direction_1": [2, 0],
            "count_1": 3,
            "spacing_1": 20,
            "direction_2": [0, 4],
            "count_2": 2,
            "spacing_2": 20,
        }
    ) == [
        [-20.0, -10.0],
        [0.0, -10.0],
        [20.0, -10.0],
        [-20.0, 10.0],
        [0.0, 10.0],
        [20.0, 10.0],
    ]


def test_mirror_pattern_deduplicates_points_on_a_mirror_axis():
    assert pattern_positions(
        {
            "type": "mirror",
            "seed_position": [20, 0],
            "axes": ["x", "y"],
        }
    ) == [[20.0, 0.0], [-20.0, 0.0]]


def test_pattern_synchronization_is_the_execution_source_of_truth():
    model_data = {
        "operations": [
            {
                "id": "holes",
                "positions": [[999, 999]],
                "pattern": {
                    "type": "circular",
                    "seed_position": [10, 0],
                    "center": [0, 0],
                    "count": 3,
                    "total_angle_degrees": 180,
                },
            }
        ]
    }

    with pytest.raises(ValueError, match="position count must match"):
        validate_pattern_positions(model_data)

    synchronize_pattern_positions(model_data)
    validate_pattern_positions(model_data)
    assert model_data["operations"][0]["positions"] == [
        [10.0, 0.0],
        [0.0, 10.0],
        [-10.0, 0.0],
    ]
