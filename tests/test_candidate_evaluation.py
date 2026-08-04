"""Tests for geometry-aware generation feedback."""

from prompt2cad.candidate_evaluation import evaluate_design_intent_candidate
from prompt2cad.candidate_evaluation import evaluate_model_candidate


def test_model_candidate_builds_and_records_geometry():
    result = evaluate_model_candidate({
        "operations": [{
            "type": "extrude",
            "id": "base",
            "plane": "XY",
            "profile": "rectangle",
            "width": 80,
            "height": 50,
            "distance": 6,
        }]
    })

    assert result["passed"] is True
    assert result["quality_report"]["geometry_summary"]["solid_count"] == 1
    assert result["operation_effects"]["passed"] is True
    assert result["feedback"]["operation_trace"][0]["operation_id"] == "base"


def test_model_candidate_rejects_cut_that_changes_nothing():
    result = evaluate_model_candidate({
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
                "type": "cut",
                "id": "missed_hole",
                "target": "base.top",
                "profile": "circle",
                "positions": [[100, 100]],
                "diameter": 6,
                "depth": "through",
            },
        ]
    })

    assert result["quality_report"]["passed"] is True
    assert result["operation_effects"]["passed"] is False
    assert result["passed"] is False
    assert "did not remove measurable material" in result["feedback"][
        "operation_effect_failures"
    ][0]


def test_design_intent_candidate_reports_lowering_failure_compactly():
    result = evaluate_design_intent_candidate({
        "required_concepts": ["hole"],
        "base": {
            "id": "base",
            "role": "plate",
            "profile": "rectangle",
            "width": 80,
            "height": 50,
            "thickness": 6,
        },
        "features": [{
            "id": "hole",
            "role": "hole",
            "operation": "drill",
            "target": "base.top",
            "shape": "circle",
            "placement": {"type": "centered"},
            "diameter": 6,
            "depth": "through",
        }],
        "edge_treatments": [],
    })

    assert result["passed"] is False
    assert result["model_data"] is None
    assert "drill" in result["feedback"]["lowering_error"]


def test_design_intent_candidate_requires_raw_shape_dimensions():
    result = evaluate_design_intent_candidate({
        "required_concepts": ["hole"],
        "base": {
            "id": "base",
            "role": "plate",
            "profile": "rectangle",
            "width": 80,
            "height": 50,
            "thickness": 6,
        },
        "features": [{
            "id": "hole",
            "role": "hole",
            "operation": "cut",
            "target": "base.top",
            "shape": "circle",
            "placement": {"type": "centered"},
        }],
        "edge_treatments": [],
    })

    assert result["passed"] is False
    assert result["model_data"] is not None
    assert result["missing_required_dimensions"] == [{
        "kind": "feature",
        "id": "hole",
        "fields": ["diameter", "depth"],
    }]
    assert result["feedback"]["missing_required_dimensions"] == result[
        "missing_required_dimensions"
    ]


def test_design_intent_candidate_rejects_collapsed_mirror_placement():
    result = evaluate_design_intent_candidate({
        "required_concepts": ["post"],
        "base": {
            "id": "base",
            "role": "plate",
            "profile": "rectangle",
            "width": 80,
            "height": 50,
            "thickness": 6,
        },
        "features": [{
            "id": "posts",
            "role": "post",
            "operation": "extrusion",
            "target": "base.top",
            "shape": "circle",
            "placement": {
                "type": "mirrored",
                "seed": [20, 0],
                "axes": ["x"],
            },
            "diameter": 8,
            "distance": 10,
        }],
        "edge_treatments": [],
    })

    assert result["passed"] is False
    assert result["intent_alignment"]["passed"] is False
    assert any(
        "expected 2 instance" in failure
        for failure in result["feedback"]["intent_alignment_failures"]
    )
