"""Tests for the portfolio-facing five-model showcase."""

from prompt2cad.showcase import SHOWCASE_CASE_COUNT
from prompt2cad.showcase import export_showcase_svg
from prompt2cad.showcase import validate_showcase


def test_showcase_has_five_distinct_verified_models():
    report = validate_showcase()

    assert report["passed"], report["errors"]
    assert len(report["cases"]) == SHOWCASE_CASE_COUNT
    assert {case["id"] for case in report["cases"]} == {
        "patterned_mounting_plate",
        "sealed_circular_flange",
        "half_cylinder_cradle",
        "turned_shaft",
        "d_shaped_mounting_plate",
    }
    assert all(case["passed"] for case in report["cases"])
    assert all(case["model_data"]["operations"] for case in report["cases"])


def test_showcase_exports_readable_svg_projections(tmp_path):
    report = validate_showcase()
    paths = export_showcase_svg(tmp_path, validation_report=report)

    assert len(paths) == SHOWCASE_CASE_COUNT
    for path in paths:
        svg = path.read_text(encoding="utf-8")
        assert "<svg" in svg
        assert "<path" in svg
        assert "rgb(21,45,80)" in svg
