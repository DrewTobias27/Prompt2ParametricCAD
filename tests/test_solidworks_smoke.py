import json
from pathlib import Path

import pytest

from prompt2cad.interpreter import build_model
from prompt2cad.loader import load_model
from prompt2cad.solidworks_smoke import SMOKE_FIXTURE_NAMES
from prompt2cad.solidworks_smoke import compare_geometry_metrics
from prompt2cad.solidworks_smoke import geometry_metrics
from prompt2cad.solidworks_smoke import run_smoke_suite
from prompt2cad.solidworks_smoke import smoke_fixture_paths


def test_every_native_smoke_fixture_builds_and_plans(tmp_path: Path):
    fixtures = smoke_fixture_paths()

    report = run_smoke_suite(fixtures, tmp_path)

    assert tuple(path.stem for path in fixtures) == SMOKE_FIXTURE_NAMES
    assert report["passed"] == len(SMOKE_FIXTURE_NAMES)
    assert report["failed"] == 0
    assert report["mode"] == "plan_only"
    for result in report["results"]:
        assert Path(result["step_path"]).is_file()
        assert Path(result["plan_path"]).is_file()
        assert result["operation_count"] == result["native_feature_count"]


def test_native_smoke_execution_uses_the_validated_plan(tmp_path: Path):
    fixture = smoke_fixture_paths(["solidworks_smoke_patterned_plate"])
    captured = []
    expected_geometry = geometry_metrics(build_model(load_model(fixture[0])))

    def fake_native_exporter(plan, output_path, **kwargs):
        captured.append((plan, output_path, kwargs))
        output_path.write_bytes(b"native-part")
        result_path = kwargs["result_output_path"]
        result_path.write_text(
            json.dumps({"geometry": expected_geometry}),
            encoding="utf-8",
        )
        return output_path

    report = run_smoke_suite(
        fixture,
        tmp_path,
        execute_native=True,
        visible=True,
        native_exporter=fake_native_exporter,
    )

    assert report["passed"] == 1
    assert report["mode"] == "native"
    assert len(captured) == 1
    assert captured[0][2]["visible"] is True
    assert Path(report["results"][0]["native_path"]).is_file()
    assert report["results"][0]["geometry_comparison"]["passed"] is True


def test_unknown_smoke_fixture_is_rejected():
    with pytest.raises(ValueError, match="Unknown SOLIDWORKS smoke fixture"):
        smoke_fixture_paths(["not_a_fixture"])


def test_geometry_comparison_rejects_a_missing_pattern_instance():
    cadquery = {
        "solid_body_count": 1,
        "volume_mm3": 1000.0,
        "bounding_box_mm": [0, 0, 0, 20, 10, 5],
    }
    missing_instance = {
        "solid_body_count": 1,
        "volume_mm3": 800.0,
        "bounding_box_mm": [0, 0, 0, 15, 10, 5],
    }

    with pytest.raises(RuntimeError, match="volume differs"):
        compare_geometry_metrics(cadquery, missing_instance)
