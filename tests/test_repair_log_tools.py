"""Tests for promoting repair logs into eval assets."""

import json

from prompt2cad.eval_runner import run_eval
from prompt2cad.repair_log_tools import build_eval_case
from prompt2cad.repair_log_tools import model_data_from_repair_log
from prompt2cad.repair_log_tools import promote_repair_log
from prompt2cad.repair_log_tools import slugify_name


def simple_repaired_model() -> dict:
    """Return a simple valid model for promotion tests."""
    return {
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
                "target": "base.top",
                "profile": "circle",
                "positions": [[-20, 0], [20, 0]],
                "diameter": 6,
                "depth": "through",
            },
        ]
    }


def test_slugify_name_returns_safe_snake_case():
    assert slugify_name("Plate: holes + boss!") == "plate_holes_boss"


def test_model_data_from_repair_log_prefers_latest_repaired_model():
    repaired_model = simple_repaired_model()
    repair_log = {
        "final_model_data": {"operations": []},
        "repair_history": [
            {
                "failed_model_data": {"operations": [{"type": "bad"}]},
                "repaired_model_data": repaired_model,
            }
        ],
    }

    assert model_data_from_repair_log(repair_log) == repaired_model


def test_build_eval_case_uses_stable_operation_expectations():
    model_data = simple_repaired_model()
    eval_case = build_eval_case(
        name="two_hole_plate",
        prompt="make a plate with two holes",
        fixture_filename="two_hole_plate.json",
        model_data=model_data,
    )

    assert eval_case["fixture_model"] == "../fixtures/two_hole_plate.json"
    assert eval_case["expected"]["operation_count"] == 2
    assert eval_case["expected"]["base"]["width"] == 80
    assert eval_case["expected"]["required_operations"] == [
        {
            "type": "cut",
            "profile": "circle",
            "diameter": 6,
            "depth": "through",
            "position_count": 2,
        }
    ]


def test_promote_repair_log_writes_fixture_and_runnable_eval_case(tmp_path):
    log_path = tmp_path / "repair-log.json"
    fixture_dir = tmp_path / "fixtures"
    case_dir = tmp_path / "cases"
    model_data = simple_repaired_model()
    log_path.write_text(
        json.dumps(
            {
                "prompt": "Make a plate with two holes",
                "status": "success",
                "final_model_data": model_data,
                "repair_history": [
                    {
                        "failure_analysis": {"passed": False},
                        "failed_model_data": {"operations": []},
                        "repaired_model_data": model_data,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    written_paths = promote_repair_log(
        log_path,
        name="two_hole_plate",
        fixture_dir=fixture_dir,
        case_dir=case_dir,
    )

    assert written_paths == {
        "fixture": fixture_dir / "two_hole_plate.json",
        "case": case_dir / "two_hole_plate.json",
    }
    case_name, failures = run_eval(
        written_paths["fixture"],
        written_paths["case"],
    )
    assert case_name == "two_hole_plate"
    assert failures == []
