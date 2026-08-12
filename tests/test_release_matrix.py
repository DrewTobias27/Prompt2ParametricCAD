from pathlib import Path

import pytest

from prompt2cad.release_matrix import RELEASE_MATRIX_CASES
from prompt2cad.release_matrix import run_release_matrix


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
    assert (tmp_path / f"{case_name}.step").is_file()
    assert (tmp_path / f"{case_name}.solidworks-plan.json").is_file()


def test_release_matrix_rejects_unknown_cases(tmp_path: Path):
    with pytest.raises(ValueError, match="Unknown release matrix cases"):
        run_release_matrix(tmp_path, case_names=("not_a_case",))
