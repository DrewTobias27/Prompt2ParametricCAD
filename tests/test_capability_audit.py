import json
import os
from pathlib import Path

import pytest

from prompt2cad.capability_audit import PATTERN_TYPES
from prompt2cad.capability_audit import PLANAR_FACE_TARGETS
from prompt2cad.capability_audit import PROFILE_TYPES
from prompt2cad.capability_audit import generated_capability_cases
from prompt2cad.capability_audit import run_capability_audit
from prompt2cad.editable_model import model_data_to_editable_document
from prompt2cad.editable_model import rebuild_with_parameter_updates
from prompt2cad.interpreter import build_model
from prompt2cad.solidworks_verification import geometry_metrics


REPRESENTATIVE_CASE_NAMES = (
    "base_revolve_partial__sketch",
    "top_add_extrude__polygon__rectangle",
    "top_add_extrude__rectangle__sketch",
    "nested_boss_cut__sketch__polyline",
    "face_bottom__cut__circle",
    "face_front__add_extrude__sketch",
    "pattern_circular__add_extrude__polygon",
    "pattern_linear__cut__sketch",
    "pattern_mirror__countersink",
    "revolved_feature__cut_revolve__polyline",
    "edge_fillet__sketch",
    "stacked_through_cut__sketch",
    "child_edge_chamfer__sketch",
    "pattern_child__linear__polyline",
    "side_pattern__circular__cut",
    "angled_pattern__linear__add_extrude",
    "revolve_end_face__add_extrude__sketch",
    "revolve_end_edge__fillet",
)


run_release_audits = pytest.mark.skipif(
    os.getenv("PROMPT2CAD_RUN_RELEASE_AUDITS") != "1",
    reason="set PROMPT2CAD_RUN_RELEASE_AUDITS=1 for the exhaustive matrix",
)


def test_generated_matrix_covers_every_declared_pair():
    cases = generated_capability_cases()
    facets = {case.facets for case in cases}

    assert len(cases) >= 280
    assert len({case.name for case in cases}) == len(cases)

    for base_profile in PROFILE_TYPES:
        for operation_type in ("add_extrude", "cut"):
            for feature_profile in PROFILE_TYPES:
                assert (
                    base_profile,
                    operation_type,
                    feature_profile,
                    "top",
                ) in facets

    for face_name in PLANAR_FACE_TARGETS:
        for operation_type in ("add_extrude", "cut"):
            for profile in PROFILE_TYPES:
                assert (face_name, operation_type, profile) in facets

    for pattern_type in PATTERN_TYPES:
        for operation_type in ("add_extrude", "cut"):
            for profile in PROFILE_TYPES:
                assert (pattern_type, operation_type, profile) in facets
        assert (pattern_type, "countersink", "circle") in facets

        for profile in PROFILE_TYPES:
            assert (pattern_type, profile, "instance_child", "cut") in facets
        for operation_type in ("add_extrude", "cut"):
            assert ("front", pattern_type, operation_type, "circle") in facets
            assert (
                "angled_planar",
                pattern_type,
                operation_type,
                "circle",
            ) in facets

        countersink_case = next(
            case
            for case in cases
            if case.name == f"pattern_{pattern_type}__countersink"
        )
        assert (
            "patterned_countersink.placement.inst001.x"
            in countersink_case.mutations
        )

    for boss_profile in PROFILE_TYPES:
        for child_profile in PROFILE_TYPES:
            assert (
                "add_extrude",
                boss_profile,
                "add_extrude",
                child_profile,
                "boss.top",
            ) in facets


def test_representative_high_risk_cases_build_plan_and_repair():
    report = run_capability_audit(case_names=REPRESENTATIVE_CASE_NAMES)

    assert report["failed"] == 0, [
        result for result in report["results"] if result["status"] == "fail"
    ]
    assert report["passed"] == len(REPRESENTATIVE_CASE_NAMES)
    assert all(
        result["native_mutation_preflight"]["mutation_count"]
        == len(result["mutations"])
        for result in report["results"]
    )
    coverage = report["native_parameter_coverage"]
    assert coverage["fully_controlled_cases"] >= coverage["fully_bound_cases"]
    assert coverage["restricted_parameter_count"] >= 0
    assert coverage["unsupported_parameter_count"] >= 0
    assert coverage["derived_geometry_count"] >= 0
    assert coverage["fully_represented_cases"] >= (
        coverage["fully_controlled_cases"]
    )


def test_representative_step_round_trips(tmp_path: Path):
    report = run_capability_audit(
        output_root=tmp_path,
        export_steps=True,
        case_names=REPRESENTATIVE_CASE_NAMES,
    )

    assert report["failed"] == 0
    assert len(tuple((tmp_path / "steps").glob("*.step"))) == len(
        REPRESENTATIVE_CASE_NAMES
    )


def test_native_audit_mode_verifies_replay_and_edited_reopen(
    tmp_path: Path,
    monkeypatch,
):
    case = next(
        case
        for case in generated_capability_cases()
        if case.name == "top_add_extrude__rectangle__circle"
    )
    original_geometry = geometry_metrics(build_model(case.model_data))
    document = model_data_to_editable_document(case.model_data)
    edited_part, _ = rebuild_with_parameter_updates(document, case.mutations)
    edited_geometry = geometry_metrics(edited_part)

    def reference_records(plan):
        return [
            {
                "reference_id": reference["reference_id"],
                "entity_name": reference["entity_name"],
                "entity_type": reference["entity_type"],
                "resolved": True,
                "persistent_id_base64": f"test-persistent-id-{index}",
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

    def fake_export(plan, output_path, **kwargs):
        output_path.write_bytes(b"native-part")
        kwargs["result_output_path"].write_text(
            json.dumps(
                {
                    "geometry": original_geometry,
                    "published_references": reference_records(plan),
                }
            ),
            encoding="utf-8",
        )
        return output_path

    def fake_verify(plan, source_path, output_path, mutations, **kwargs):
        assert source_path.is_file()
        output_path.write_bytes(b"edited-native-part")
        kwargs["result_output_path"].write_text(
            json.dumps(
                {
                    "reopened": True,
                    "mutation_count": len(mutations),
                    "after_geometry": edited_geometry,
                    "published_references": reference_records(plan),
                }
            ),
            encoding="utf-8",
        )
        return output_path

    monkeypatch.setattr(capability_audit, "export_solidworks_part", fake_export)
    monkeypatch.setattr(
        capability_audit,
        "verify_solidworks_editability",
        fake_verify,
    )

    result = audit_capability_case(
        case,
        native_directory=tmp_path,
        verify_native_editability=True,
    )

    assert result["status"] == "pass"
    assert result["solidworks_native"]["editability"]["reopened"] is True


@run_release_audits
def test_complete_generated_capability_matrix_builds_and_plans():
    report = run_capability_audit()

    assert report["case_count"] >= 280
    assert report["failed"] == 0, [
        result for result in report["results"] if result["status"] == "fail"
    ]
    assert report["passed"] == report["case_count"]


@run_release_audits
def test_step_round_trip_is_available_for_release_audits(tmp_path: Path):
    report = run_capability_audit(output_root=tmp_path, export_steps=True)

    assert report["failed"] == 0
    assert len(tuple((tmp_path / "steps").glob("*.step"))) == report["case_count"]
from prompt2cad import capability_audit
from prompt2cad.capability_audit import audit_capability_case
