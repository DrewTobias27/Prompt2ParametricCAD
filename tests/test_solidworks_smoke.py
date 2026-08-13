import json
from pathlib import Path

import pytest

from prompt2cad.editable_model import model_data_to_editable_document
from prompt2cad.editable_model import rebuild_with_parameter_updates
from prompt2cad.interpreter import build_model
from prompt2cad.loader import load_model
from prompt2cad.solidworks_editability import native_parameter_coverage
from prompt2cad.solidworks_smoke import SMOKE_FIXTURE_NAMES
from prompt2cad.solidworks_smoke import EDITABILITY_SCENARIOS
from prompt2cad.solidworks_smoke import run_smoke_suite
from prompt2cad.solidworks_smoke import smoke_fixture_paths
from prompt2cad.solidworks_verification import compare_geometry_metrics
from prompt2cad.solidworks_verification import geometry_metrics
from prompt2cad.solidworks_verification import validate_published_references


def persistent_reference_records(plan) -> list[dict]:
    return [
        {
            "reference_id": reference["reference_id"],
            "entity_name": reference["entity_name"],
            "entity_type": reference["entity_type"],
            "persistent_id_base64": "AQ==",
            "resolved": True,
            "resolution_error_code": 0,
        }
        for feature in plan.features
        for reference in feature.publish_references
    ]


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
        assert result["native_mutation_preflight"]["mutation_count"] == len(
            EDITABILITY_SCENARIOS[result["name"]]
        )


def test_every_native_fixture_has_a_valid_bound_editability_scenario():
    from prompt2cad.solidworks_export import model_path_to_replay_plan

    fixtures = smoke_fixture_paths()
    assert set(EDITABILITY_SCENARIOS) == set(SMOKE_FIXTURE_NAMES)

    for fixture in fixtures:
        model_data = load_model(fixture)
        document = model_data_to_editable_document(model_data)
        mutations = EDITABILITY_SCENARIOS[fixture.stem]
        rebuilt_part, _ = rebuild_with_parameter_updates(document, mutations)
        assert len(rebuilt_part.solids().vals()) == 1

        plan = model_path_to_replay_plan(fixture)
        binding_ids = {
            binding["parameter_id"]
            for feature in plan.features
            for binding in feature.parameter_bindings
        }
        assert set(mutations) <= binding_ids


def test_parameter_coverage_binds_nonzero_freeform_coordinates():
    from prompt2cad.solidworks_export import model_path_to_replay_plan

    fixture = smoke_fixture_paths(["solidworks_smoke_coordinate_profiles"])[0]
    model_data = load_model(fixture)
    coverage = native_parameter_coverage(
        model_data,
        model_path_to_replay_plan(fixture),
    )

    assert coverage["bound_count"] > 0
    assert coverage["coverage_ratio"] < 1
    assert "base.sketch.point003.x" not in coverage["unbound_parameter_ids"]
    assert (
        "rounded_slot.sketch.segment002.through.x"
        not in coverage["unbound_parameter_ids"]
    )
    # Zero-valued coordinates are held by native horizontal/vertical
    # relations, while polygon topology remains the next parameter gap.
    assert "hex_boss.sketch.diameter" not in coverage["unbound_parameter_ids"]
    assert "hex_boss.sketch.sides" in coverage["unbound_parameter_ids"]
    assert "hex_boss.sketch.sides" in coverage["unsupported_parameter_ids"]
    assert coverage["unsupported_parameters"] == [
        {
            "parameter_id": "hex_boss.sketch.sides",
            "reason": (
                "SolidWorks fixes regular-polygon topology when the sketch "
                "is created. Change the side count by editing or recreating "
                "that native polygon sketch."
            ),
        }
    ]
    assert "hex_boss.placement.inst001.y" in (
        coverage["relation_controlled_parameter_ids"]
    )
    assert "hex_boss.placement.inst001.y" not in (
        coverage["unsupported_parameter_ids"]
    )
    assert "base.sketch.point002.x" in coverage["restricted_parameter_ids"]
    assert coverage["restricted_parameters"]
    assert coverage["control_coverage_ratio"] > coverage["coverage_ratio"]


def test_revolve_axis_endpoints_are_retained_derived_geometry():
    from prompt2cad.solidworks_replay import build_solidworks_replay_plan

    model_data = {
        "operations": [
            {
                "type": "revolve",
                "id": "shaft",
                "plane": "XY",
                "profile": "rectangle",
                "positions": [[5, 0]],
                "axis_start": [0, -20],
                "axis_end": [0, 20],
                "angle": 360,
                "width": 10,
                "height": 40,
            }
        ]
    }
    document = model_data_to_editable_document(model_data)
    coverage = native_parameter_coverage(
        model_data,
        build_solidworks_replay_plan(document),
        document=document,
    )

    expected_axis_parameters = {
        "shaft.reference.axis_start.x",
        "shaft.reference.axis_start.y",
        "shaft.reference.axis_end.x",
        "shaft.reference.axis_end.y",
    }
    assert set(coverage["derived_geometry_parameter_ids"]) == (
        expected_axis_parameters
    )
    assert expected_axis_parameters.isdisjoint(
        coverage["unsupported_parameter_ids"]
    )
    assert coverage["derived_geometry_count"] == 4
    assert coverage["representation_coverage_ratio"] == 1.0
    assert coverage["control_coverage_ratio"] < 1.0
    assert all(
        "redundantly encode one line" in parameter["reason"]
        for parameter in coverage["derived_geometry_parameters"]
    )


def test_native_smoke_execution_uses_the_validated_plan(tmp_path: Path):
    fixture = smoke_fixture_paths(["solidworks_smoke_patterned_plate"])
    captured = []
    expected_geometry = geometry_metrics(build_model(load_model(fixture[0])))

    def fake_native_exporter(plan, output_path, **kwargs):
        captured.append((plan, output_path, kwargs))
        output_path.write_bytes(b"native-part")
        result_path = kwargs["result_output_path"]
        result_path.write_text(
            json.dumps(
                {
                    "geometry": expected_geometry,
                    "published_references": persistent_reference_records(plan),
                }
            ),
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


def test_native_smoke_editability_rebuilds_and_compares_mutated_geometry(
    tmp_path: Path,
):
    fixture = smoke_fixture_paths(["solidworks_smoke_patterned_plate"])
    captured = {"exports": 0, "edits": 0}

    def fake_native_exporter(plan, output_path, **kwargs):
        captured["exports"] += 1
        output_path.write_bytes(b"native-part")
        result_path = kwargs["result_output_path"]
        model_data = load_model(fixture[0])
        result_path.write_text(
            json.dumps(
                {
                    "geometry": geometry_metrics(build_model(model_data)),
                    "published_references": persistent_reference_records(plan),
                }
            ),
            encoding="utf-8",
        )
        return output_path

    def fake_editability_verifier(
        plan,
        source_path,
        output_path,
        mutations,
        **kwargs,
    ):
        captured["edits"] += 1
        assert source_path.is_file()
        assert mutations == {
            "base.sketch.width": 120,
            "bosses.feature.distance": 10,
            "mounting_holes.feature.diameter": 6,
        }
        model_data = load_model(fixture[0])
        model_data["operations"][0]["width"] = 120
        model_data["operations"][1]["distance"] = 10
        model_data["operations"][2]["diameter"] = 6
        output_path.write_bytes(b"mutated-native-part")
        kwargs["result_output_path"].write_text(
            json.dumps(
                {
                    "status": "success",
                    "mutation_count": 3,
                    "reopened": True,
                    "after_geometry": geometry_metrics(build_model(model_data)),
                    "health": {"feature_error_count": 0},
                    "published_references": persistent_reference_records(plan),
                }
            ),
            encoding="utf-8",
        )
        return output_path

    report = run_smoke_suite(
        fixture,
        tmp_path,
        execute_native=True,
        verify_editability=True,
        native_exporter=fake_native_exporter,
        editability_verifier=fake_editability_verifier,
    )

    assert report["passed"] == 1
    assert captured == {"exports": 1, "edits": 1}
    editability = report["results"][0]["editability"]
    assert editability["reopened"] is True
    assert editability["geometry_comparison"]["passed"] is True
    assert editability["health"] == {"feature_error_count": 0}
    assert editability["published_references"]["passed"] is True


def test_persistent_reference_check_rejects_a_missing_semantic_entity():
    fixture = smoke_fixture_paths(["solidworks_smoke_patterned_plate"])[0]
    from prompt2cad.solidworks_export import model_path_to_replay_plan

    plan = model_path_to_replay_plan(fixture)
    incomplete = persistent_reference_records(plan)[1:]

    with pytest.raises(RuntimeError, match="persistent-reference mismatch"):
        validate_published_references(
            plan,
            {"published_references": incomplete},
            context="test",
        )


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


def test_geometry_metrics_include_position_and_shape_invariants():
    import cadquery as cq

    metrics = geometry_metrics(
        cq.Workplane("XY").box(20, 10, 5).translate((7, -3, 2))
    )

    assert metrics["surface_area_mm2"] == pytest.approx(700)
    assert metrics["center_of_mass_mm"] == pytest.approx([7, -3, 2])
    assert metrics["bounding_box_mm"] == pytest.approx(
        [-3, -8, -0.5, 17, 2, 4.5]
    )


def test_geometry_comparison_rejects_a_translated_equal_size_part():
    expected = {
        "solid_body_count": 1,
        "volume_mm3": 1000.0,
        "surface_area_mm2": 700.0,
        "center_of_mass_mm": [0, 0, 0],
        "bounding_box_mm": [-10, -5, -2.5, 10, 5, 2.5],
    }
    translated = {
        **expected,
        "center_of_mass_mm": [5, 0, 0],
        "bounding_box_mm": [-5, -5, -2.5, 15, 5, 2.5],
    }

    with pytest.raises(RuntimeError, match="bounding-box position"):
        compare_geometry_metrics(expected, translated)


def test_geometry_comparison_rejects_wrong_surface_or_mass_distribution():
    expected = {
        "solid_body_count": 1,
        "volume_mm3": 1000.0,
        "surface_area_mm2": 700.0,
        "center_of_mass_mm": [0, 0, 0],
        "bounding_box_mm": [-10, -5, -2.5, 10, 5, 2.5],
    }

    with pytest.raises(RuntimeError, match="surface area differs"):
        compare_geometry_metrics(
            expected,
            {**expected, "surface_area_mm2": 760.0},
        )
    with pytest.raises(RuntimeError, match="center of mass"):
        compare_geometry_metrics(
            expected,
            {**expected, "center_of_mass_mm": [2, 0, 0]},
        )
