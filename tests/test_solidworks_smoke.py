import base64
import json
from pathlib import Path

import pytest

from prompt2cad.editable_model import model_data_to_editable_document
from prompt2cad.editable_model import rebuild_with_parameter_updates
from prompt2cad.interpreter import build_model
from prompt2cad.loader import load_model
from prompt2cad.solidworks_editability import native_parameter_coverage
from prompt2cad.solidworks_replay import build_solidworks_replay_plan
from prompt2cad.solidworks_smoke import SMOKE_FIXTURE_NAMES
from prompt2cad.solidworks_smoke import EDITABILITY_SCENARIOS
from prompt2cad.solidworks_smoke import NATIVE_EDIT_REQUIRED_COVERAGE
from prompt2cad.solidworks_smoke import NATIVE_GATE_REQUIRED_COVERAGE
from prompt2cad.solidworks_smoke import run_smoke_suite
from prompt2cad.solidworks_smoke import smoke_fixture_paths
from prompt2cad.solidworks_verification import compare_geometry_metrics
from prompt2cad.solidworks_verification import geometry_metrics
from prompt2cad.solidworks_verification import validate_native_build_result
from prompt2cad.solidworks_verification import validate_native_editability_result
from prompt2cad.solidworks_verification import validate_published_references


def persistent_reference_records(plan) -> list[dict]:
    return [
        {
            "reference_id": reference["reference_id"],
            "entity_name": reference["entity_name"],
            "entity_type": reference["entity_type"],
            "persistent_id_base64": base64.b64encode(
                index.to_bytes(4, byteorder="little")
            ).decode("ascii"),
            "resolved": True,
            "resolution_error_code": 0,
        }
        for index, reference in enumerate(
            (
                reference
                for feature in plan.features
                for reference in feature.publish_references
            ),
            start=1,
        )
    ]


def test_every_native_smoke_fixture_builds_and_plans(tmp_path: Path):
    fixtures = smoke_fixture_paths()

    report = run_smoke_suite(fixtures, tmp_path)

    assert tuple(path.stem for path in fixtures) == SMOKE_FIXTURE_NAMES
    assert report["passed"] == len(SMOKE_FIXTURE_NAMES)
    assert report["failed"] == 0
    assert report["mode"] == "plan_only"
    assert report["release_gate_passed"] is True
    assert report["native_gate_coverage"]["complete_fixture_suite"] is True
    assert report["native_gate_coverage"]["passed"] is True
    assert report["native_gate_coverage"]["missing"] == {}
    assert report["native_gate_coverage"]["required"] == {
        category: sorted(values)
        for category, values in NATIVE_GATE_REQUIRED_COVERAGE.items()
    }
    assert report["native_edit_coverage"]["complete_fixture_suite"] is True
    assert report["native_edit_coverage"]["passed"] is True
    assert report["native_edit_coverage"]["missing"] == {}
    assert report["native_edit_coverage"]["required"] == {
        category: sorted(values)
        for category, values in NATIVE_EDIT_REQUIRED_COVERAGE.items()
    }
    for result in report["results"]:
        assert Path(result["step_path"]).is_file()
        assert Path(result["plan_path"]).is_file()
        assert result["operation_count"] == result["native_feature_count"]
        assert result["native_mutation_preflight"]["mutation_count"] == len(
            EDITABILITY_SCENARIOS[result["name"]]
        )


def test_partial_native_smoke_selection_reports_but_does_not_claim_coverage(
    tmp_path: Path,
):
    report = run_smoke_suite(
        smoke_fixture_paths(["solidworks_smoke_patterned_plate"]),
        tmp_path,
    )

    assert report["failed"] == 0
    assert report["release_gate_passed"] is True
    assert report["native_gate_coverage"]["complete_fixture_suite"] is False
    assert report["native_gate_coverage"]["passed"] is None
    assert report["native_gate_coverage"]["missing"]
    assert report["native_edit_coverage"]["passed"] is None
    assert report["native_edit_coverage"]["missing"]


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


def test_native_smoke_execution_uses_the_validated_plan(
    tmp_path: Path,
    native_result_factory,
):
    fixture = smoke_fixture_paths(["solidworks_smoke_patterned_plate"])
    captured = []
    expected_geometry = geometry_metrics(build_model(load_model(fixture[0])))

    def fake_native_exporter(plan, output_path, **kwargs):
        captured.append((plan, output_path, kwargs))
        output_path.write_bytes(b"native-part")
        result_path = kwargs["result_output_path"]
        result_path.write_text(
            json.dumps(
                native_result_factory(
                    plan,
                    geometry=expected_geometry,
                    published_references=persistent_reference_records(plan),
                )
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
    native_result_factory,
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
                native_result_factory(
                    plan,
                    geometry=geometry_metrics(build_model(model_data)),
                    published_references=persistent_reference_records(plan),
                )
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
            "bosses.placement.inst001.x": 34,
            "bosses.placement.inst001.y": 22,
            "bosses.feature.distance": 10,
            "mounting_holes.feature.diameter": 6,
        }
        source_document = model_data_to_editable_document(load_model(fixture[0]))
        expected_part, _ = rebuild_with_parameter_updates(
            source_document,
            mutations,
        )
        output_path.write_bytes(b"mutated-native-part")
        kwargs["result_output_path"].write_text(
            json.dumps(
                native_result_factory(
                    plan,
                    editability=True,
                    mutated_parameter_ids=mutations,
                    after_geometry=geometry_metrics(expected_part),
                    published_references=persistent_reference_records(plan),
                )
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
    assert editability["health"]["feature_error_count"] == 0
    assert editability["native_contract"]["health_passed"] is True
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


def test_native_contract_rejects_missing_helpers_and_unhealthy_sketches(
    native_result_factory,
):
    from prompt2cad.solidworks_export import model_path_to_replay_plan

    fixture = smoke_fixture_paths(["solidworks_smoke_circular_pattern"])[0]
    plan = model_path_to_replay_plan(fixture)
    missing_helper = native_result_factory(plan)
    missing_helper["verified_helper_count"] -= 1

    with pytest.raises(RuntimeError, match="verified_helper_count"):
        validate_native_build_result(plan, missing_helper, context="test")

    wrong_helper_identity = native_result_factory(plan)
    wrong_helper_identity["verified_helper_names"][0] = "wrong_helper"
    with pytest.raises(RuntimeError, match="helper identities"):
        validate_native_build_result(plan, wrong_helper_identity, context="test")

    wrong_parameter_identity = native_result_factory(plan)
    wrong_parameter_identity["verified_parameter_ids"][0] = "wrong.parameter"
    with pytest.raises(RuntimeError, match="parameter identities"):
        validate_native_build_result(plan, wrong_parameter_identity, context="test")

    not_reopened = native_result_factory(plan)
    not_reopened["reopened"] = False
    with pytest.raises(RuntimeError, match="did not reopen"):
        validate_native_build_result(plan, not_reopened, context="test")

    mutation_id = plan.features[0].parameter_bindings[0]["parameter_id"]
    unhealthy = native_result_factory(
        plan,
        editability=True,
        mutated_parameter_ids=[mutation_id],
    )
    unhealthy["health"]["sketches"][0]["is_valid"] = False
    with pytest.raises(RuntimeError, match="invalid native sketches"):
        validate_native_editability_result(
            plan,
            unhealthy,
            expected_mutation_ids=[mutation_id],
            context="test edit",
        )

    wrong_mutation_identity = native_result_factory(
        plan,
        editability=True,
        mutated_parameter_ids=["wrong.parameter"],
    )
    with pytest.raises(RuntimeError, match="mutated parameter identities"):
        validate_native_editability_result(
            plan,
            wrong_mutation_identity,
            expected_mutation_ids=[mutation_id],
            context="test edit",
        )


def test_native_contract_requires_embedded_geometry_oracle_evidence(
    native_result_factory,
):
    fixture = smoke_fixture_paths(["solidworks_smoke_patterned_plate"])[0]
    model_data = load_model(fixture)
    plan = build_solidworks_replay_plan(
        model_data_to_editable_document(model_data),
        expected_geometry=geometry_metrics(build_model(model_data)),
    )

    build_result = native_result_factory(plan)
    build_result["geometry_verification_passed"] = False
    with pytest.raises(RuntimeError, match="geometry against CadQuery"):
        validate_native_build_result(plan, build_result, context="test")

    mutation_id = plan.features[0].parameter_bindings[0]["parameter_id"]
    edit_result = native_result_factory(
        plan,
        editability=True,
        mutated_parameter_ids=[mutation_id],
    )
    edit_result["source_geometry_verification_passed"] = False
    with pytest.raises(RuntimeError, match="source geometry against CadQuery"):
        validate_native_editability_result(
            plan,
            edit_result,
            expected_mutation_ids=[mutation_id],
            context="test edit",
        )


def test_persistent_reference_check_rejects_duplicate_or_wrong_identity():
    fixture = smoke_fixture_paths(["solidworks_smoke_patterned_plate"])[0]
    from prompt2cad.solidworks_export import model_path_to_replay_plan

    plan = model_path_to_replay_plan(fixture)
    records = persistent_reference_records(plan)

    with pytest.raises(RuntimeError, match="repeats a native reference ID"):
        validate_published_references(
            plan,
            {"published_references": [*records, records[0]]},
            context="test",
        )

    duplicate_entity = [dict(record) for record in records]
    duplicate_entity[1]["persistent_id_base64"] = duplicate_entity[0][
        "persistent_id_base64"
    ]
    with pytest.raises(RuntimeError, match="one native entity"):
        validate_published_references(
            plan,
            {"published_references": duplicate_entity},
            context="test",
        )

    wrong_metadata = [dict(record) for record in records]
    wrong_metadata[0]["entity_name"] = "wrong-face"
    with pytest.raises(RuntimeError, match="metadata does not match"):
        validate_published_references(
            plan,
            {"published_references": wrong_metadata},
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
