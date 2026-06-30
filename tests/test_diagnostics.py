"""Tests for local CAD failure diagnostics."""

from prompt2cad.diagnostics import check_model_data
from prompt2cad.diagnostics import diagnose_failure


def disconnected_frame_stair_model_data() -> dict:
    """Return a frame with a disconnected inner platform."""
    return {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "distance": 10,
                "width": 120,
                "height": 120,
            },
            {
                "type": "cut",
                "target": "base.top",
                "profile": "rectangle",
                "positions": [[0, 0]],
                "depth": "through",
                "width": 80,
                "height": 80,
            },
            {
                "type": "add_extrude",
                "target": "base.top",
                "profile": "sketch",
                "positions": [[0, 0]],
                "distance": 3,
                "start": [-22, -30],
                "segments": [
                    {"type": "line", "to": [22, -30]},
                    {"type": "arc", "through": [30, -30], "to": [30, -22]},
                    {"type": "line", "to": [30, 22]},
                    {"type": "arc", "through": [30, 30], "to": [22, 30]},
                    {"type": "line", "to": [-22, 30]},
                    {"type": "arc", "through": [-30, 30], "to": [-30, 22]},
                    {"type": "line", "to": [-30, -22]},
                    {"type": "arc", "through": [-30, -30], "to": [-22, -30]},
                ],
                "close": True,
            },
        ]
    }


def test_check_model_data_explains_feature_inside_through_cut():
    diagnosis = check_model_data(disconnected_frame_stair_model_data())

    assert diagnosis["passed"] is False
    assert diagnosis["failure_type"] == "disconnected_solids_inside_through_cut"
    assert "through cut created an opening" in diagnosis["reason"]
    assert "bridge tabs" in diagnosis["suggested_fixes"][0]
    assert diagnosis["details"]["cut_operation_number"] == 2
    assert diagnosis["details"]["added_operation_number"] == 3


def test_diagnose_failure_handles_missing_model_data():
    diagnosis = diagnose_failure(None, "API generation failed")

    assert diagnosis["passed"] is False
    assert diagnosis["failure_type"] == "generation_failed"
    assert diagnosis["reason"] == "API generation failed"


def test_check_model_data_passes_simple_plate():
    diagnosis = check_model_data(
        {
            "operations": [
                {
                    "type": "extrude",
                    "id": "base",
                    "plane": "XY",
                    "profile": "rectangle",
                    "distance": 6,
                    "width": 80,
                    "height": 50,
                }
            ]
        }
    )

    assert diagnosis == {
        "passed": True,
        "failure_type": None,
        "reason": "Model data validated and built successfully.",
        "suggested_fixes": [],
    }
