"""Tests for design-intent eval cases."""

from pathlib import Path

from prompt2cad.intent_evaluator import evaluate_design_intent
from prompt2cad.intent_evaluator import load_json


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INTENT_CASES_DIR = PROJECT_ROOT / "evals" / "intent_cases"


def test_intent_eval_accepts_matching_corner_hole_intent():
    eval_case = load_json(INTENT_CASES_DIR / "rectangular_plate_corner_holes.json")
    design_intent = {
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

    result = evaluate_design_intent(design_intent, eval_case)

    assert result.passed is True


def test_intent_eval_reports_wrong_relationship_choice():
    eval_case = load_json(INTENT_CASES_DIR / "rectangular_plate_corner_holes.json")
    design_intent = {
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
                    "type": "circular_pattern",
                    "count": 4,
                    "radius": 25,
                },
            }
        ],
    }

    result = evaluate_design_intent(design_intent, eval_case)

    assert result.passed is False
    assert "near_corners" in result.failures[0]


def test_intent_eval_accepts_matching_edge_treatment_intent():
    eval_case = load_json(INTENT_CASES_DIR / "chamfered_rectangular_plate.json")
    design_intent = {
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 80,
            "height": 50,
            "thickness": 6,
        },
        "features": [],
        "edge_treatments": [
            {
                "id": "top_chamfer",
                "treatment": "chamfer",
                "target_feature": "base",
                "edge_selector": "top_outer_edges",
                "distance": 1,
            }
        ],
    }

    result = evaluate_design_intent(design_intent, eval_case)

    assert result.passed is True


def test_intent_eval_ignores_strict_api_null_fillers():
    eval_case = load_json(INTENT_CASES_DIR / "rectangular_plate_corner_holes.json")
    design_intent = {
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 100,
            "height": 70,
            "diameter": None,
            "sides": None,
            "thickness": 8,
            "length": None,
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
                "radius": None,
                "orientation": None,
                "distance": None,
                "depth": "through",
            }
        ],
        "edge_treatments": [],
    }

    result = evaluate_design_intent(design_intent, eval_case)

    assert result.passed is True


def test_intent_eval_uses_same_reasonable_dimension_fill_as_lowerer():
    eval_case = {
        "name": "hex_plate",
        "expected_intent": {
            "base": {
                "profile": "polygon",
            }
        },
    }
    design_intent = {
        "base": {
            "id": "hex_plate",
            "profile": "polygon",
            "width": 80,
            "diameter": None,
            "sides": 6,
            "thickness": 6,
        },
        "features": [],
        "edge_treatments": [],
    }

    result = evaluate_design_intent(design_intent, eval_case)

    assert result.passed is True


def test_intent_eval_fails_when_required_concept_is_uncovered():
    eval_case = {
        "name": "cradle_with_mounting_plate",
        "expected_intent": {
            "base": {
                "profile": "half_cylinder",
            }
        },
    }
    design_intent = {
        "required_concepts": ["cradle", "mounting_plate", "hole"],
        "base": {
            "id": "base",
            "role": "cradle",
            "profile": "half_cylinder",
            "diameter": 60,
            "length": 100,
        },
        "features": [
            {
                "id": "mounting_holes",
                "role": "hole",
                "operation": "cut",
                "target": "base.bottom",
                "shape": "circle",
                "diameter": 6,
                "depth": "through",
                "placement": {"type": "centered"},
            }
        ],
        "edge_treatments": [],
    }

    result = evaluate_design_intent(design_intent, eval_case)

    assert result.passed is False
    assert "mounting_plate" in result.failures[0]


def test_intent_eval_case_files_have_expected_intent():
    for case_path in INTENT_CASES_DIR.glob("*.json"):
        eval_case = load_json(case_path)
        assert eval_case["name"]
        assert eval_case["prompt"]
        assert eval_case["expected_intent"]
