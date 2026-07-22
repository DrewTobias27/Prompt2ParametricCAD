"""Tests for per-operation physical-effect diagnostics."""

from prompt2cad.operation_effects import evaluate_operation_effects
from prompt2cad.operation_effects import operation_effect_failures
from prompt2cad.operation_effects import operation_pattern_warnings
from prompt2cad.operation_effects import instance_effect_failures


def test_operation_effect_failures_reports_no_op_cut():
    failures = operation_effect_failures({
        "operation_number": 2,
        "operation_id": "missing_hole",
        "operation_type": "cut",
        "volume_before": 1000,
        "volume_delta": 0,
    })

    assert len(failures) == 1
    assert "did not remove measurable material" in failures[0]
    assert "missing_hole" in failures[0]


def test_operation_effect_failures_accepts_material_changes():
    assert operation_effect_failures({
        "operation_number": 2,
        "operation_id": "boss",
        "operation_type": "add_extrude",
        "volume_before": 1000,
        "volume_delta": 200,
    }) == []
    assert operation_effect_failures({
        "operation_number": 3,
        "operation_id": "hole",
        "operation_type": "cut",
        "volume_before": 1200,
        "volume_delta": -100,
    }) == []


def test_operation_pattern_warnings_reports_duplicate_instances():
    warnings = operation_pattern_warnings(
        {
            "type": "cut",
            "positions": [[10, 0], [10, 0], [-10, 0]],
        },
        2,
    )

    assert len(warnings) == 1
    assert "duplicate instance position" in warnings[0]


def test_instance_effect_failures_reports_only_missed_pattern_instances():
    failures = instance_effect_failures({
        "operation_number": 2,
        "operation_id": "holes",
        "target": "base.top",
        "instance_count": 3,
        "instance_effects": [
            {"instance_number": 1, "position": [0, 0], "affected_model": True},
            {"instance_number": 2, "position": [20, 0], "affected_model": False},
            {"instance_number": 3, "position": [-20, 0], "affected_model": True},
        ],
    })

    assert len(failures) == 1
    assert "only affected 2 of 3" in failures[0]
    assert "#2 at [20, 0]" in failures[0]


def test_evaluate_operation_effects_traces_successful_add_and_cut():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 40,
                "height": 30,
                "distance": 6,
            },
            {
                "type": "add_extrude",
                "id": "boss",
                "target": "base.top",
                "profile": "circle",
                "positions": [[0, 0]],
                "diameter": 12,
                "distance": 5,
            },
            {
                "type": "cut",
                "id": "hole",
                "target": "boss.top",
                "profile": "circle",
                "positions": [[0, 0]],
                "diameter": 4,
                "depth": "through",
            },
        ]
    }

    result = evaluate_operation_effects(model_data)

    assert result["passed"] is True
    assert result["failures"] == []
    assert len(result["trace"]) == 3
    assert result["trace"][1]["volume_delta"] > 0
    assert result["trace"][2]["volume_delta"] < 0


def test_evaluate_operation_effects_reports_cut_that_misses_body():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 40,
                "height": 30,
                "distance": 6,
            },
            {
                "type": "cut",
                "id": "missed_hole",
                "target": "base.top",
                "profile": "circle",
                "positions": [[100, 100]],
                "diameter": 4,
                "depth": "through",
            },
        ]
    }

    result = evaluate_operation_effects(model_data)

    assert result["passed"] is False
    assert len(result["failures"]) == 1
    assert "missed_hole" in result["failures"][0]


def test_evaluate_operation_effects_reports_partially_missed_pattern():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 40,
                "height": 30,
                "distance": 6,
            },
            {
                "type": "cut",
                "id": "mixed_holes",
                "target": "base.top",
                "profile": "circle",
                "positions": [[0, 0], [100, 100]],
                "diameter": 4,
                "depth": "through",
            },
        ]
    }

    result = evaluate_operation_effects(model_data)

    assert result["passed"] is False
    assert any("only affected 1 of 2" in failure for failure in result["failures"])
    instance_effects = result["trace"][1]["instance_effects"]
    assert instance_effects[0]["affected_model"] is True
    assert instance_effects[1]["affected_model"] is False
