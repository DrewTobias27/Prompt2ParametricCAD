import json
from pathlib import Path

import pytest

from prompt2cad.release_matrix import RELEASE_MATRIX_CASES
from prompt2cad.release_matrix import run_release_matrix
from prompt2cad.solidworks_replay import build_solidworks_replay_plan
from prompt2cad.editable_model import model_data_to_editable_document
from prompt2cad.editable_model import rebuild_with_parameter_updates
from prompt2cad.interpreter import build_model
from prompt2cad.solidworks_verification import geometry_metrics


def test_release_matrix_case_names_are_unique_and_cover_high_risk_families():
    names = [case.name for case in RELEASE_MATRIX_CASES]

    assert len(names) == len(set(names))
    assert {
        "counterbored_bolt_circle",
        "two_wall_u_bracket",
        "shaft_collars_grooves_chamfers",
        "half_cylinder_cradle_mounting_plate",
        "cross_arm_hub_plate",
    }.issubset(names)


@pytest.mark.parametrize(
    "case_name",
    [
        "rectangular_plate_corner_holes",
        "half_cylinder_cradle_mounting_plate",
    ],
)
def test_release_matrix_traverses_every_deterministic_stage(
    tmp_path: Path,
    case_name: str,
):
    report = run_release_matrix(tmp_path, case_names=(case_name,))

    assert report["passed"] == 1
    assert report["failed"] == 0
    result = report["results"][0]
    assert result["status"] == "pass"
    assert list(result["checks"]) == report["pipeline"]
    assert result["checks"]["step_round_trip"]["passed"] is True
    assert result["checks"]["editable_parameter_rebuild"]["passed"] is True
    assert result["checks"]["solidworks_replay_plan"]["passed"] is True
    assert result["checks"]["solidworks_replay_plan"][
        "native_mutation_preflight"
    ]["mutation_count"] > 0
    assert (tmp_path / f"{case_name}.step").is_file()
    assert (tmp_path / f"{case_name}.solidworks-plan.json").is_file()


def test_release_matrix_rejects_unknown_cases(tmp_path: Path):
    with pytest.raises(ValueError, match="Unknown release matrix cases"):
        run_release_matrix(tmp_path, case_names=("not_a_case",))


def test_release_matrix_native_mode_checks_create_edit_and_reopen(
    tmp_path: Path,
):
    case_name = "rectangular_plate_corner_holes"

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

    def fake_native_exporter(plan, output_path, **kwargs):
        model_data = json.loads(
            (tmp_path / f"{case_name}.model.json").read_text(encoding="utf-8")
        )
        output_path.write_bytes(b"native-part")
        kwargs["result_output_path"].write_text(
            json.dumps(
                {
                    "geometry": geometry_metrics(build_model(model_data)),
                    "published_references": reference_records(plan),
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
        model_data = json.loads(
            (tmp_path / f"{case_name}.model.json").read_text(encoding="utf-8")
        )
        document = model_data_to_editable_document(model_data)
        edited_part, edited_document = rebuild_with_parameter_updates(
            document,
            mutations,
        )
        edited_plan = build_solidworks_replay_plan(edited_document)
        assert source_path.is_file()
        output_path.write_bytes(b"edited-native-part")
        kwargs["result_output_path"].write_text(
            json.dumps(
                {
                    "reopened": True,
                    "mutation_count": len(mutations),
                    "after_geometry": geometry_metrics(edited_part),
                    "published_references": reference_records(edited_plan),
                }
            ),
            encoding="utf-8",
        )
        return output_path

    report = run_release_matrix(
        tmp_path,
        case_names=(case_name,),
        verify_native_editability=True,
        native_exporter=fake_native_exporter,
        editability_verifier=fake_editability_verifier,
    )

    assert report["mode"] == "native"
    assert report["passed"] == 1
    assert report["pipeline"][-1] == "solidworks_native"
    native = report["results"][0]["checks"]["solidworks_native"]
    assert native["geometry_comparison"]["passed"] is True
    assert native["published_references"]["passed"] is True
    assert native["editability"]["passed"] is True
    assert native["editability"]["reopened"] is True
