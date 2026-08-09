"""Tests for the portfolio-facing eight-model showcase."""

import json

from prompt2cad.showcase import SHOWCASE_CASE_COUNT
from prompt2cad.showcase import export_showcase_svg
from prompt2cad.showcase import load_showcase
from prompt2cad.showcase import validate_showcase


def test_showcase_has_eleven_distinct_verified_models():
    report = validate_showcase()

    assert report["passed"], report["errors"]
    assert len(report["cases"]) == SHOWCASE_CASE_COUNT
    assert {case["id"] for case in report["cases"]} == {
        "patterned_mounting_plate",
        "sealed_circular_flange",
        "hexagonal_hub_plate",
        "turned_shaft",
        "d_shaped_mounting_plate",
        "counterbored_bolt_circle",
        "nested_boss_cross_hole",
        "two_wall_u_bracket",
        "cross_arm_hub_plate",
        "open_top_drainage_tray",
        "ribbed_support_bracket",
    }
    assert all(case["passed"] for case in report["cases"])
    assert all(case["model_data"]["operations"] for case in report["cases"])
    cases_by_id = {case["id"]: case for case in report["cases"]}
    assert cases_by_id["turned_shaft"]["svg_projection"] == [1, -3, 4]
    assert cases_by_id["turned_shaft"]["svg_show_hidden"] is False
    assert cases_by_id["two_wall_u_bracket"]["svg_projection"] == [4, -1, 4]
    assert cases_by_id["two_wall_u_bracket"]["svg_show_hidden"] is False
    assert cases_by_id["ribbed_support_bracket"]["svg_projection"] == [4, -1, 4]
    assert cases_by_id["cross_arm_hub_plate"]["svg_show_hidden"] is False
    assert cases_by_id["open_top_drainage_tray"]["svg_show_hidden"] is False


def test_showcase_exports_readable_svg_projections(tmp_path):
    report = validate_showcase()
    paths = export_showcase_svg(tmp_path, validation_report=report)

    assert len(paths) == SHOWCASE_CASE_COUNT
    for path in paths:
        svg = path.read_text(encoding="utf-8")
        assert "<svg" in svg
        assert "<path" in svg
        assert "rgb(21,45,80)" in svg
        assert all(line == line.rstrip(" \t") for line in svg.splitlines())


def test_showcase_rejects_invalid_case_specific_projection(tmp_path):
    showcase = load_showcase()
    showcase["cases"][0]["svg_projection"] = [1, 2]
    showcase_path = tmp_path / "showcase.json"
    showcase_path.write_text(json.dumps(showcase), encoding="utf-8")

    report = validate_showcase(showcase_path=showcase_path)

    assert not report["passed"]
    assert "invalid svg_projection" in report["errors"][0]
