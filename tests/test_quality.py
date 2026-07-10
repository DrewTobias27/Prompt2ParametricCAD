"""Tests for structured model quality reports."""

from prompt2cad.quality import check_model_quality


def simple_plate_model() -> dict:
    """Return a valid one-feature model."""
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
                "type": "add_extrude",
                "id": "feature_1",
                "target": "base.top",
                "profile": "circle",
                "positions": [[0, 0]],
                "diameter": 20,
                "distance": 8,
            },
            {
                "type": "chamfer",
                "id": "feature_2",
                "target": "feature_1.top_outer_edges",
                "distance": 1,
            },
        ]
    }


def issue_codes(report: dict) -> set[str]:
    """Return issue codes from a quality report."""
    return {issue["code"] for issue in report["issues"]}


def test_check_model_quality_passes_valid_structure():
    report = check_model_quality(simple_plate_model())

    assert report["passed"] is True
    assert report["status"] == "pass"
    assert report["summary"] == {"errors": 0, "warnings": 0, "infos": 0}
    assert report["issues"] == []


def test_check_model_quality_reports_repairable_structure_issues():
    model_data = {
        "operations": [
            {
                "type": "cut",
                "target": "base.top",
                "profile": "circle",
                "diameter": 10,
                "depth": "through",
            },
            {
                "type": "add_extrude",
                "id": "feature_1",
                "target": "feature_9.top",
                "profile": "rectangle",
                "positions": [],
                "width": 20,
                "height": -5,
                "distance": 0,
            },
            {
                "type": "fillet",
                "id": "feature_2",
                "target": "base.top",
                "radius": "large",
            },
        ]
    }

    report = check_model_quality(model_data)

    assert report["passed"] is False
    assert report["status"] == "fail"
    assert {
        "schema_validation_failed",
        "first_operation_not_base",
        "target_before_parent",
        "invalid_positive_number",
        "missing_positions",
        "edge_operation_targets_face",
    }.issubset(issue_codes(report))
    assert all("stage" in issue for issue in report["issues"])
    assert all("suggestion" in issue for issue in report["issues"])


def test_check_model_quality_warns_on_unknown_but_ordered_target():
    model_data = simple_plate_model()
    model_data["operations"][1]["target"] = "base.custom_face"

    report = check_model_quality(model_data)

    assert report["passed"] is True
    assert report["status"] == "warning"
    assert "unknown_target_reference" in issue_codes(report)


def test_check_model_quality_reports_duplicate_ids():
    model_data = simple_plate_model()
    model_data["operations"][2]["id"] = "feature_1"

    report = check_model_quality(model_data)

    assert report["passed"] is False
    assert "duplicate_feature_id" in issue_codes(report)
