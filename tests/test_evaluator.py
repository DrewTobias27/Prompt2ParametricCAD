"""Tests for lightweight CAD generation eval checks."""

import copy
import json
from pathlib import Path

from prompt2cad.evaluator import evaluate_model_data
from prompt2cad.interpreter import build_model


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    """Load a JSON file from disk."""
    return json.loads(path.read_text(encoding="utf-8"))


def rigorous_plate_holes_boss_model_data() -> dict:
    """Return a model with repeated cuts and an added feature."""
    return {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 100,
                "height": 60,
                "distance": 8,
            },
            {
                "type": "cut",
                "target": "base.top",
                "profile": "circle",
                "positions": [
                    [-35, -20],
                    [-35, 20],
                    [35, -20],
                    [35, 20],
                ],
                "depth": "through",
                "diameter": 8,
            },
            {
                "type": "add_extrude",
                "id": "center_boss",
                "target": "base.top",
                "profile": "rectangle",
                "positions": [[0, 0]],
                "distance": 10,
                "width": 20,
                "height": 15,
            },
        ]
    }


def test_evaluator_accepts_rectangular_plate_four_holes_example():
    model_data = load_json(
        PROJECT_ROOT / "examples" / "rectangular_plate_multiple_holes.json"
    )
    eval_case = load_json(
        PROJECT_ROOT / "evals" / "cases" / "rectangular_plate_four_holes.json"
    )

    part = build_model(model_data)
    result = evaluate_model_data(model_data, eval_case, part)

    assert result.passed is True
    assert result.failures == []


def test_evaluator_accepts_circular_base_rectangular_boss_example():
    model_data = load_json(
        PROJECT_ROOT / "examples" / "circular_base_rectangular_boss.json"
    )
    eval_case = load_json(
        PROJECT_ROOT
        / "evals"
        / "cases"
        / "circular_base_rectangular_boss.json"
    )

    part = build_model(model_data)
    result = evaluate_model_data(model_data, eval_case, part)

    assert result.passed is True
    assert result.failures == []


def test_evaluator_accepts_rigorous_plate_holes_boss_case():
    model_data = rigorous_plate_holes_boss_model_data()
    eval_case = load_json(
        PROJECT_ROOT / "evals" / "cases" / "rigorous_plate_holes_boss.json"
    )

    part = build_model(model_data)
    result = evaluate_model_data(model_data, eval_case, part)

    assert result.passed is True
    assert result.failures == []


def test_evaluator_reports_wrong_volume():
    model_data = rigorous_plate_holes_boss_model_data()
    eval_case = load_json(
        PROJECT_ROOT / "evals" / "cases" / "rigorous_plate_holes_boss.json"
    )
    eval_case = copy.deepcopy(eval_case)
    eval_case["expected"]["volume"]["value"] = 100

    part = build_model(model_data)
    result = evaluate_model_data(model_data, eval_case, part)

    assert result.passed is False
    assert any(
        failure.startswith("Expected volume 100")
        for failure in result.failures
    )


def test_evaluator_reports_wrong_operation_count_pattern():
    model_data = rigorous_plate_holes_boss_model_data()
    eval_case = load_json(
        PROJECT_ROOT / "evals" / "cases" / "rigorous_plate_holes_boss.json"
    )
    eval_case = copy.deepcopy(eval_case)
    eval_case["expected"]["operation_counts"][0]["count"] = 2

    part = build_model(model_data)
    result = evaluate_model_data(model_data, eval_case, part)

    assert result.passed is False
    assert (
        "Expected 2 operations matching type=cut, profile=circle, "
        "depth=through, position_count=4, but found 1."
    ) in result.failures


def test_evaluator_reports_missing_graph_reference():
    model_data = rigorous_plate_holes_boss_model_data()
    eval_case = load_json(
        PROJECT_ROOT / "evals" / "cases" / "rigorous_plate_holes_boss.json"
    )
    eval_case = copy.deepcopy(eval_case)
    eval_case["expected"]["graph"]["required_references"].append(
        "center_boss.face.f999"
    )

    part = build_model(model_data)
    result = evaluate_model_data(model_data, eval_case, part)

    assert result.passed is False
    assert (
        "Missing required graph reference: center_boss.face.f999."
        in result.failures
    )


def test_evaluator_reports_missing_expected_operation():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 100,
                "height": 60,
                "distance": 6,
            }
        ]
    }
    eval_case = load_json(
        PROJECT_ROOT / "evals" / "cases" / "rectangular_plate_four_holes.json"
    )

    part = build_model(model_data)
    result = evaluate_model_data(model_data, eval_case, part)

    assert result.passed is False
    assert len(result.failures) == 2
    assert result.failures[0] == "Expected 2 operations, but found 1."
    assert result.failures[1].startswith("Missing expected operation")


def test_evaluator_reports_wrong_base_dimension():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 90,
                "height": 60,
                "distance": 6,
            },
            {
                "type": "cut",
                "target": "base.top",
                "profile": "circle",
                "positions": [
                    [-40, -20],
                    [-40, 20],
                    [40, -20],
                    [40, 20],
                ],
                "depth": "through",
                "diameter": 8,
            },
        ]
    }
    eval_case = load_json(
        PROJECT_ROOT / "evals" / "cases" / "rectangular_plate_four_holes.json"
    )

    part = build_model(model_data)
    result = evaluate_model_data(model_data, eval_case, part)

    assert result.passed is False
    assert result.failures == [
        "Expected base width 100, but found 90.",
        "Expected bounding box x 100, but found 90.0.",
    ]


def test_evaluator_reports_wrong_required_operation_dimension():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 100,
                "height": 60,
                "distance": 6,
            },
            {
                "type": "cut",
                "target": "base.top",
                "profile": "circle",
                "positions": [
                    [-40, -20],
                    [-40, 20],
                    [40, -20],
                    [40, 20],
                ],
                "depth": "through",
                "diameter": 6,
            },
        ]
    }
    eval_case = load_json(
        PROJECT_ROOT / "evals" / "cases" / "rectangular_plate_four_holes.json"
    )

    part = build_model(model_data)
    result = evaluate_model_data(model_data, eval_case, part)

    assert result.passed is False
    assert result.failures == [
        (
            "Missing expected operation: "
            "type=cut, profile=circle, diameter=8, depth=through, "
            "position_count=4."
        )
    ]


def test_evaluator_reports_missing_part_for_bounding_box_check():
    model_data = load_json(
        PROJECT_ROOT / "examples" / "rectangular_plate_multiple_holes.json"
    )
    eval_case = load_json(
        PROJECT_ROOT / "evals" / "cases" / "rectangular_plate_four_holes.json"
    )

    result = evaluate_model_data(model_data, eval_case)

    assert result.passed is False
    assert result.failures == ["Bounding box check requires a built CAD part."]
