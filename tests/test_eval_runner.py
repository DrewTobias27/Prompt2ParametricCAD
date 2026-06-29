"""Tests for running eval cases against generated or fixture CAD JSON."""

import json

from prompt2cad import eval_runner


def write_json(path, data: dict) -> None:
    """Write readable JSON test data to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_run_batch_uses_fixture_model_when_generated_model_is_missing(tmp_path):
    cases_dir = tmp_path / "cases"
    fixtures_dir = tmp_path / "fixtures"
    generated_dir = tmp_path / "generated"

    write_json(
        cases_dir / "simple_plate.json",
        {
            "name": "simple_plate",
            "prompt": "Create a simple plate.",
            "fixture_model": "../fixtures/simple_plate.json",
            "expected": {
                "operation_count": 1,
                "base": {
                    "type": "extrude",
                    "profile": "rectangle",
                    "width": 40,
                    "height": 20,
                    "distance": 5,
                },
                "solid": {
                    "single_solid": True,
                    "valid": True,
                    "minimum_volume": 1,
                },
            },
        },
    )
    write_json(
        fixtures_dir / "simple_plate.json",
        {
            "operations": [
                {
                    "type": "extrude",
                    "id": "base",
                    "plane": "XY",
                    "profile": "rectangle",
                    "width": 40,
                    "height": 20,
                    "distance": 5,
                }
            ]
        },
    )

    failures = eval_runner.run_batch(generated_dir, cases_dir)

    assert failures == []
