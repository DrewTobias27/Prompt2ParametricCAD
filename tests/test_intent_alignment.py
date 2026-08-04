"""Tests for design-intent-to-operation alignment diagnostics."""

from prompt2cad.intent_alignment import evaluate_intent_alignment


def circular_pattern_intent() -> dict:
    """Return a small intent object with a six-instance bolt circle."""
    return {
        "base": {"id": "base", "profile": "circle"},
        "features": [
            {
                "id": "bolt_holes",
                "operation": "cut",
                "target": "base.top",
                "shape": "circle",
                "placement": {
                    "type": "circular_pattern",
                    "count": 6,
                    "radius": 25,
                },
            }
        ],
        "edge_treatments": [],
    }


def test_intent_alignment_accepts_preserved_feature_and_pattern():
    intent = circular_pattern_intent()
    model_data = {
        "operations": [
            {"type": "extrude", "id": "base"},
            {
                "type": "cut",
                "id": "bolt_holes",
                "target": "base.top",
                "profile": "circle",
                "positions": [
                    [25, 0],
                    [12.5, 21.650635],
                    [-12.5, 21.650635],
                    [-25, 0],
                    [-12.5, -21.650635],
                    [12.5, -21.650635],
                ],
            },
        ]
    }

    result = evaluate_intent_alignment(intent, model_data)

    assert result == {"passed": True, "failures": []}


def test_intent_alignment_reports_missing_feature_operation():
    result = evaluate_intent_alignment(
        circular_pattern_intent(),
        {"operations": [{"type": "extrude", "id": "base"}]},
    )

    assert result["passed"] is False
    assert "did not produce a CAD operation" in result["failures"][0]


def test_intent_alignment_reports_collapsed_pattern():
    intent = circular_pattern_intent()
    model_data = {
        "operations": [
            {"type": "extrude", "id": "base"},
            {
                "type": "cut",
                "id": "bolt_holes",
                "target": "base.top",
                "profile": "circle",
                "positions": [[25, 0], [25, 0]],
            },
        ]
    }

    result = evaluate_intent_alignment(intent, model_data)

    assert result["passed"] is False
    assert any("expected 6 instance" in failure for failure in result["failures"])
    assert any("duplicate positions" in failure for failure in result["failures"])


def test_intent_alignment_reports_mirror_seed_on_requested_axis():
    intent = {
        "base": {"id": "base", "profile": "rectangle"},
        "features": [{
            "id": "posts",
            "operation": "extrusion",
            "target": "base.top",
            "shape": "circle",
            "placement": {
                "type": "mirrored",
                "seed": [25, 0],
                "axes": ["x"],
            },
        }],
        "edge_treatments": [],
    }
    model_data = {
        "operations": [
            {"type": "extrude", "id": "base"},
            {
                "type": "add_extrude",
                "id": "posts",
                "profile": "circle",
                "positions": [[25, 0]],
            },
        ]
    }

    result = evaluate_intent_alignment(intent, model_data)

    assert result["passed"] is False
    assert any("expected 2 instance" in failure for failure in result["failures"])


def test_intent_alignment_accepts_same_as_feature_positions():
    intent = {
        "base": {"id": "base", "profile": "rectangle"},
        "features": [
            {
                "id": "bosses",
                "operation": "extrusion",
                "target": "base.top",
                "shape": "circle",
                "placement": {"type": "near_corners", "count": 2},
            },
            {
                "id": "holes",
                "operation": "cut",
                "target": "bosses.top",
                "shape": "circle",
                "placement": {
                    "type": "same_as_feature",
                    "source_feature": "bosses",
                },
            },
        ],
        "edge_treatments": [],
    }
    positions = [[-20, 10], [20, 10]]
    model_data = {
        "operations": [
            {"type": "extrude", "id": "base"},
            {"type": "add_extrude", "id": "bosses", "profile": "circle", "positions": positions},
            {"type": "cut", "id": "holes", "profile": "circle", "positions": positions},
        ]
    }

    result = evaluate_intent_alignment(intent, model_data)

    assert result["passed"] is True
