"""Tests for concept-level generated CAD evaluation."""

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
