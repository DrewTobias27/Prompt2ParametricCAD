"""Tests for retrieved CAD example guidance."""

import json

from prompt2cad.example_library import format_examples_for_prompt
from prompt2cad.example_library import load_example_library
from prompt2cad.example_library import select_relevant_examples
from prompt2cad.example_library import select_relevant_intent_examples
from prompt2cad.interpreter import build_model
from prompt2cad.schema import validate_model_data


REQUIRED_PROVENANCE_FIELDS = [
    "source_name",
    "source_url",
    "source_license",
    "original_id",
    "derived_by",
]


def test_select_relevant_examples_prioritizes_circular_flange():
    examples = select_relevant_examples(
        "Create a circular flange with six bolt holes.",
        max_examples=2,
    )

    assert examples[0]["name"] == "circular_flange_six_bolt_holes"


def test_select_relevant_examples_prioritizes_capsule_arc_sketch():
    examples = select_relevant_examples(
        "Create a rounded capsule-shaped revolved cylinder with hemispherical ends.",
        max_examples=2,
    )

    assert examples[0]["name"] == "capsule_revolve_with_arc_sketch"


def test_format_examples_for_prompt_includes_plan_and_model_data():
    examples = select_relevant_examples(
        "Make a rectangular plate with corner holes.",
        max_examples=1,
    )

    formatted = json.loads(format_examples_for_prompt(examples))

    assert formatted[0]["construction_plan"]
    assert formatted[0]["model_data"]["operations"]
    assert "source_file" not in formatted[0]


def test_example_library_examples_include_provenance():
    for example in load_example_library():
        for field in REQUIRED_PROVENANCE_FIELDS:
            assert example[field]


def test_example_library_models_are_valid_and_buildable():
    for example in load_example_library():
        model_data = example["model_data"]

        validate_model_data(model_data)
        build_model(model_data)


def test_intent_examples_match_the_preferred_generation_format():
    examples = select_relevant_intent_examples(
        "Create a circular flange with six holes on a bolt circle.",
        max_examples=2,
    )

    assert examples[0]["name"] == "circular_flange_bolt_circle"
    assert examples[0]["prompt"]
    assert examples[0]["design_intent"]["base"]["profile"] == "circle"


def test_intent_retrieval_omits_unrelated_examples():
    examples = select_relevant_intent_examples(
        "Create an involute gear with helical teeth.",
        max_examples=2,
    )

    assert examples == []
