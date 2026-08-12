"""Keep checked-in CAD examples compatible with native SolidWorks replay."""

import json
from pathlib import Path

import pytest

from prompt2cad.editable_model import model_data_to_editable_document
from prompt2cad.solidworks_replay import build_solidworks_replay_plan
from prompt2cad.training_data import load_intent_examples
from prompt2cad.training_data import validate_intent_example


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _direct_model_cases() -> list:
    cases = []
    for directory in (
        PROJECT_ROOT / "examples" / "models",
        PROJECT_ROOT / "evals" / "fixtures",
    ):
        for path in sorted(directory.glob("*.json")):
            model_data = json.loads(path.read_text(encoding="utf-8"))
            cases.append(
                pytest.param(
                    model_data,
                    id=str(path.relative_to(PROJECT_ROOT)),
                )
            )

    for path in sorted((PROJECT_ROOT / "examples" / "library").glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        cases.append(
            pytest.param(
                record["model_data"],
                id=str(path.relative_to(PROJECT_ROOT)),
            )
        )
    return cases


@pytest.mark.parametrize("model_data", _direct_model_cases())
def test_checked_in_operation_models_lower_to_native_replay(model_data):
    document = model_data_to_editable_document(model_data)
    plan = build_solidworks_replay_plan(document)

    assert len(plan.features) == len(model_data["operations"])
    assert tuple(plan.source_build_order) == document.build_order


@pytest.mark.parametrize(
    "example",
    [
        pytest.param(example, id=example["name"])
        for example in load_intent_examples(
            PROJECT_ROOT / "training" / "intent_examples"
        )
    ],
)
def test_checked_in_intent_examples_lower_to_native_replay(example):
    model_data = validate_intent_example(example)
    document = model_data_to_editable_document(model_data)
    plan = build_solidworks_replay_plan(document)

    assert len(plan.features) == len(model_data["operations"])
    assert tuple(plan.source_build_order) == document.build_order
