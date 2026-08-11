"""Tests for concept-level generated CAD evaluation."""

import math

from prompt2cad.concept_evaluator import evaluate_model_concepts


def test_concept_evaluator_accepts_expected_operations_and_geometry():
    model_data = {
        "operations": [
            {
                "type": "revolve",
                "id": "base",
                "profile": "rectangle",
                "angle": 360,
            },
            {
                "type": "add_revolve",
                "id": "collar",
                "profile": "rectangle",
            },
            {
                "type": "cut_revolve",
                "id": "groove",
                "profile": "rectangle",
            },
        ],
        "relationships": [
            {
                "type": "must_connect",
                "feature": "collar",
                "to": "base",
            }
        ],
    }
    geometry_summary = {
        "solid_count": 1,
        "bounding_box": {
            "xlen": 20.2,
            "ylen": 80,
        },
    }

    result = evaluate_model_concepts(
        model_data,
        {
            "base": {
                "type": "revolve",
                "angle": 360,
            },
            "operations": [
                {"type": "add_revolve", "id": {"contains": "collar"}},
                {"type": "cut_revolve", "id": {"contains": "groove"}},
            ],
            "relationships": [
                {"type": "must_connect", "feature": "collar"},
            ],
            "geometry": {
                "solid_count": 1,
                "bounding_box": {
                    "xlen": {"approx": 20, "tolerance": 1},
                    "ylen": {"approx": 80, "tolerance": 1},
                },
            },
        },
        geometry_summary=geometry_summary,
    )

    assert result.passed is True
    assert result.failures == []


def test_concept_evaluator_reports_missing_concepts():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "profile": "rectangle",
            }
        ],
        "relationships": [],
    }

    result = evaluate_model_concepts(
        model_data,
        {
            "base": {
                "type": "revolve",
            },
            "operations": [
                {"type": "add_revolve"},
            ],
        },
    )

    assert result.passed is False
    assert "Expected base operation type revolve" in result.failures[0]
    assert "Missing operation matching" in result.failures[1]


def test_concept_evaluator_accepts_any_valid_alternative():
    model_data = {
        "operations": [
            {
                "type": "revolve",
                "id": "base",
                "profile": "rectangle",
                "angle": 360,
            },
            {
                "type": "cut_revolve",
                "id": "step_cut_1",
                "profile": "rectangle",
            },
            {
                "type": "cut_revolve",
                "id": "step_cut_2",
                "profile": "rectangle",
            },
        ],
        "relationships": [],
    }

    result = evaluate_model_concepts(
        model_data,
        {
            "any_of": [
                {
                    "base": {
                        "type": "revolve",
                        "profile": "sketch",
                    }
                },
                {
                    "base": {
                        "type": "revolve",
                        "profile": "rectangle",
                    },
                    "min_operation_counts": {
                        "cut_revolve": 2,
                    },
                },
            ]
        },
    )

    assert result.passed is True


def test_concept_evaluator_checks_pattern_count_uniqueness_and_spacing():
    positions = [
        [20, 0],
        [0, 20],
        [-20, 0],
        [0, -20],
    ]
    model_data = {
        "operations": [
            {"type": "extrude", "id": "base"},
            {
                "type": "cut",
                "id": "bolt_holes",
                "profile": "circle",
                "positions": positions,
            },
        ]
    }

    result = evaluate_model_concepts(
        model_data,
        {
            "operations": [
                {
                    "id": "bolt_holes",
                    "positions": {
                        "length": 4,
                        "unique_length": 4,
                        "circular_pattern": {
                            "count": 4,
                            "radius": 20,
                            "tolerance": 0.001,
                        },
                    },
                }
            ]
        },
    )

    assert result.passed is True


def test_concept_evaluator_rejects_collapsed_circular_pattern():
    model_data = {
        "operations": [
            {"type": "extrude", "id": "base"},
            {
                "type": "cut",
                "id": "bolt_holes",
                "positions": [[20, 0], [20, 0], [-20, 0], [0, -20]],
            },
        ]
    }

    result = evaluate_model_concepts(
        model_data,
        {
            "operations": [
                {
                    "id": "bolt_holes",
                    "positions": {
                        "length": 4,
                        "unique_length": 4,
                        "circular_pattern": {"count": 4},
                    },
                }
            ]
        },
    )

    assert result.passed is False


def test_concept_evaluator_treats_incompatible_numeric_match_as_non_match():
    model_data = {
        "operations": [
            {"type": "extrude", "id": "base"},
            {
                "type": "cut",
                "id": "through_hole",
                "depth": "through",
            },
        ]
    }

    result = evaluate_model_concepts(
        model_data,
        {
            "operations": [
                {
                    "type": "cut",
                    "depth": {"approx": 4, "tolerance": 0.1},
                }
            ]
        },
    )

    assert result.passed is False
    assert "Missing operation matching" in result.failures[0]


def test_concept_evaluator_one_of_accepts_nested_numeric_matcher():
    model_data = {
        "operations": [
            {"type": "extrude", "id": "base"},
            {
                "type": "cut",
                "id": "drain",
                "profile": "circle",
                "depth": 4,
            },
        ]
    }

    result = evaluate_model_concepts(
        model_data,
        {
            "operations": [
                {
                    "type": "cut",
                    "depth": {
                        "one_of": [
                            "through",
                            {"approx": 4, "tolerance": 0.1},
                        ]
                    },
                }
            ]
        },
    )

    assert result.passed is True


def test_concept_evaluator_checks_cross_feature_positions_and_parent():
    model_data = {
        "operations": [
            {"type": "extrude", "id": "base"},
            {
                "type": "add_extrude",
                "id": "bosses",
                "target": "base.top",
                "positions": [[-20, 0], [20, 0]],
                "diameter": 12,
            },
            {
                "type": "cut",
                "id": "boss_holes",
                "target": "bosses.top",
                "positions": [[-20, 0], [20, 0]],
                "diameter": 4,
            },
        ]
    }

    result = evaluate_model_concepts(
        model_data,
        {
            "operation_relationships": [
                {
                    "type": "same_positions",
                    "features": ["bosses", "boss_holes"],
                },
                {
                    "type": "same_instance_count",
                    "features": ["bosses", "boss_holes"],
                },
                {
                    "type": "targets_parent",
                    "feature": "boss_holes",
                    "parent": "bosses",
                },
                {
                    "type": "dimension_order",
                    "smaller": "boss_holes",
                    "larger": "bosses",
                    "field": "diameter",
                },
            ]
        },
    )

    assert result.passed is True


def test_concept_evaluator_reports_cross_feature_relationship_failures():
    model_data = {
        "operations": [
            {"type": "extrude", "id": "base"},
            {
                "type": "add_extrude",
                "id": "bosses",
                "target": "base.top",
                "positions": [[-20, 0], [20, 0]],
                "diameter": 12,
            },
            {
                "type": "cut",
                "id": "boss_holes",
                "target": "base.top",
                "positions": [[-25, 0], [25, 0]],
                "diameter": 16,
            },
        ]
    }

    result = evaluate_model_concepts(
        model_data,
        {
            "operation_relationships": [
                {
                    "type": "same_positions",
                    "features": ["bosses", "boss_holes"],
                },
                {
                    "type": "targets_parent",
                    "feature": "boss_holes",
                    "parent": "bosses",
                },
                {
                    "type": "dimension_order",
                    "smaller": "boss_holes",
                    "larger": "bosses",
                    "field": "diameter",
                },
            ]
        },
    )

    assert result.passed is False
    assert any("same positions" in failure for failure in result.failures)
    assert any("targets 'base.top'" in failure for failure in result.failures)
    assert any("to be smaller" in failure for failure in result.failures)


def test_concept_evaluator_groups_patterned_and_separate_feature_instances():
    model_data = {
        "operations": [
            {"type": "extrude", "id": "base"},
            {
                "type": "add_extrude",
                "id": "walls",
                "profile": "rectangle",
                "target": "base.top",
                "positions": [[-40, 0], [40, 0]],
            },
            {
                "type": "cut",
                "id": "left_hole",
                "profile": "circle",
                "target": "walls.front",
                "positions": [[0, 0]],
            },
            {
                "type": "cut",
                "id": "right_hole",
                "profile": "circle",
                "target": "walls.back",
                "positions": [[0, 0]],
            },
        ]
    }

    result = evaluate_model_concepts(
        model_data,
        {
            "operation_groups": [
                {
                    "selector": {
                        "type": "add_extrude",
                        "profile": "rectangle",
                    },
                    "operation_count": 1,
                    "instance_count": 2,
                },
                {
                    "selector": {"type": "cut", "profile": "circle"},
                    "operation_count": 2,
                    "instance_count": 2,
                    "unique_target_count": 2,
                    "unique_target_parent_count": 1,
                },
            ]
        },
    )

    assert result.passed is True


def test_concept_evaluator_reports_missing_group_instances():
    model_data = {
        "operations": [
            {"type": "extrude", "id": "base"},
            {
                "type": "cut",
                "id": "corner_holes",
                "profile": "circle",
                "positions": [[-30, -20], [30, -20], [30, 20]],
            },
        ]
    }

    result = evaluate_model_concepts(
        model_data,
        {
            "operation_groups": [
                {
                    "selector": {"type": "cut", "profile": "circle"},
                    "operation_count": {"min": 1},
                    "instance_count": 4,
                }
            ]
        },
    )

    assert result.passed is False
    assert any("feature instances" in failure for failure in result.failures)


def test_concept_evaluator_checks_group_positions_without_order_dependency():
    model_data = {
        "operations": [
            {"type": "extrude", "id": "base"},
            {
                "type": "cut",
                "id": "corner_holes",
                "profile": "circle",
                "positions": [[40, 25], [-40, -25], [-40, 25], [40, -25]],
            },
        ]
    }

    result = evaluate_model_concepts(
        model_data,
        {
            "operation_groups": [
                {
                    "selector": {"type": "cut", "profile": "circle"},
                    "positions": {
                        "point_set": [
                            [-40, -25],
                            [-40, 25],
                            [40, -25],
                            [40, 25],
                        ],
                        "tolerance": 0.01,
                    },
                }
            ]
        },
    )

    assert result.passed is True


def test_concept_evaluator_rejects_wrong_group_positions():
    model_data = {
        "operations": [
            {"type": "extrude", "id": "base"},
            {
                "type": "cut",
                "id": "corner_holes",
                "profile": "circle",
                "positions": [[35, 20], [-35, -20], [-35, 20], [35, -20]],
            },
        ]
    }

    result = evaluate_model_concepts(
        model_data,
        {
            "operation_groups": [
                {
                    "selector": {"type": "cut", "profile": "circle"},
                    "positions": {
                        "point_set": [
                            [-40, -25],
                            [-40, 25],
                            [40, -25],
                            [40, 25],
                        ],
                        "tolerance": 0.01,
                    },
                }
            ]
        },
    )

    assert result.passed is False
    assert any("positions to match" in failure for failure in result.failures)


def test_concept_evaluator_checks_circular_pattern_angular_offset():
    def circular_positions(start_degrees):
        return [
            [
                20 * math.cos(math.radians(angle)),
                20 * math.sin(math.radians(angle)),
            ]
            for angle in range(start_degrees, start_degrees + 360, 60)
        ]

    model_data = {
        "operations": [
            {"type": "extrude", "id": "base"},
            {
                "type": "add_extrude",
                "id": "spokes",
                "positions": circular_positions(0),
            },
            {
                "type": "cut",
                "id": "holes",
                "positions": circular_positions(30),
            },
        ]
    }

    result = evaluate_model_concepts(
        model_data,
        {
            "operation_relationships": [
                {
                    "type": "circular_pattern_angular_offset",
                    "features": ["spokes", "holes"],
                    "offset_degrees": 30,
                    "tolerance_degrees": 0.01,
                }
            ]
        },
    )

    assert result.passed is True


def test_concept_evaluator_rejects_wrong_circular_pattern_offset():
    model_data = {
        "operations": [
            {"type": "extrude", "id": "base"},
            {
                "type": "add_extrude",
                "id": "spokes",
                "positions": [[20, 0], [0, 20], [-20, 0], [0, -20]],
            },
            {
                "type": "cut",
                "id": "holes",
                "positions": [[20, 0], [0, 20], [-20, 0], [0, -20]],
            },
        ]
    }

    result = evaluate_model_concepts(
        model_data,
        {
            "operation_relationships": [
                {
                    "type": "circular_pattern_angular_offset",
                    "features": ["spokes", "holes"],
                    "offset_degrees": 45,
                    "tolerance_degrees": 0.01,
                }
            ]
        },
    )

    assert result.passed is False
    assert any("angular offset" in failure for failure in result.failures)
