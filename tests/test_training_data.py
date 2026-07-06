"""Tests for prompt-to-design-intent training data utilities."""

import json
from pathlib import Path

from prompt2cad.training_data import build_openai_messages_record
from prompt2cad.training_data import build_training_records
from prompt2cad.training_data import export_training_jsonl
from prompt2cad.training_data import load_intent_examples
from prompt2cad.training_data import validate_intent_example


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INTENT_EXAMPLES_DIR = PROJECT_ROOT / "training" / "intent_examples"


def test_intent_training_examples_validate_and_lower_to_buildable_models():
    examples = load_intent_examples(INTENT_EXAMPLES_DIR)

    assert examples
    for example in examples:
        model_data = validate_intent_example(example)
        design_intent = example["design_intent"]
        assert model_data["operations"][0]["id"] == "base"
        if design_intent["features"]:
            expected_first_feature_id = design_intent["features"][0]["id"]
        else:
            expected_first_feature_id = design_intent["edge_treatments"][0]["id"]

        assert model_data["operations"][1]["id"] == expected_first_feature_id


def test_build_generic_training_records_include_lowered_model_data():
    examples = load_intent_examples(INTENT_EXAMPLES_DIR)

    records = build_training_records(examples, output_format="generic")

    assert len(records) == len(examples)
    assert records[0]["prompt"]
    assert records[0]["design_intent"]
    assert records[0]["lowered_model_data"]


def test_build_openai_messages_record_outputs_assistant_json():
    example = load_intent_examples(INTENT_EXAMPLES_DIR)[0]

    record = build_openai_messages_record(example)

    assert [message["role"] for message in record["messages"]] == [
        "system",
        "user",
        "assistant",
    ]
    assert json.loads(record["messages"][2]["content"]) == example["design_intent"]
    assert set(record) == {"messages"}


def test_export_training_jsonl_writes_one_record_per_example():
    output_path = PROJECT_ROOT / "generated" / "test_training" / "intent_training.jsonl"
    examples = load_intent_examples(INTENT_EXAMPLES_DIR)
    if output_path.exists():
        output_path.unlink()

    records = export_training_jsonl(
        examples_dir=INTENT_EXAMPLES_DIR,
        output_path=output_path,
        output_format="openai_messages",
    )

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(examples)
    assert len(records) == len(examples)
    assert json.loads(lines[0])["messages"][0]["role"] == "system"
