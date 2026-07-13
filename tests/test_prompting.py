"""Tests for prompt generation and repair control flow."""

import json

from prompt2cad import prompting


def test_openai_model_uses_task_specific_then_general_override(monkeypatch):
    monkeypatch.delenv("PROMPT2CAD_OPENAI_MODEL", raising=False)
    monkeypatch.delenv("PROMPT2CAD_REPAIR_MODEL", raising=False)

    assert prompting.openai_model("repair") == "gpt-5-mini"

    monkeypatch.setenv("PROMPT2CAD_OPENAI_MODEL", "gpt-5.5")
    assert prompting.openai_model("repair") == "gpt-5.5"

    monkeypatch.setenv("PROMPT2CAD_REPAIR_MODEL", "gpt-5.5-pro")
    assert prompting.openai_model("repair") == "gpt-5.5-pro"


def test_prompt_to_model_data_with_repair_repairs_once(monkeypatch):
    failed_model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "distance": 6,
                "width": 80,
                "height": 50,
            }
        ]
    }
    repaired_model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "circle",
                "distance": 6,
                "diameter": 50,
            }
        ]
    }
    repair_calls = []

    def fake_prompt_to_model_data(user_prompt: str) -> dict:
        assert user_prompt == "make a part"
        return failed_model_data

    def fake_check_model_data(model_data: dict) -> dict:
        if model_data == failed_model_data:
            return {
                "passed": False,
                "failure_type": "disconnected_solids",
                "reason": "Disconnected",
                "suggested_fixes": ["Move the feature."],
            }

        return {
            "passed": True,
            "failure_type": None,
            "reason": "Model data validated and built successfully.",
            "suggested_fixes": [],
        }

    def fake_repair_model_data(
        user_prompt: str,
        model_data: dict,
        failure_analysis: dict,
    ) -> dict:
        repair_calls.append((user_prompt, model_data, failure_analysis))
        return repaired_model_data

    monkeypatch.setattr(
        prompting,
        "prompt_to_model_data",
        fake_prompt_to_model_data,
    )
    monkeypatch.setattr(
        prompting,
        "check_model_data",
        fake_check_model_data,
    )
    monkeypatch.setattr(
        prompting,
        "repair_model_data",
        fake_repair_model_data,
    )

    model_data, repair_history = prompting.prompt_to_model_data_with_repair(
        "make a part",
        max_repairs=1,
    )

    assert model_data == repaired_model_data
    assert len(repair_calls) == 1
    failure_analysis = repair_history[0]["failure_analysis"]
    assert failure_analysis["passed"] is False
    assert failure_analysis["failure_type"] == "disconnected_solids"
    assert failure_analysis["diagnostics"] == {
        "passed": False,
        "failure_type": "disconnected_solids",
        "reason": "Disconnected",
        "suggested_fixes": ["Move the feature."],
    }
    assert failure_analysis["quality_report"]["passed"] is True
    assert repair_history[0]["repaired_model_data"] == repaired_model_data


def test_prompt_to_model_data_with_repair_skips_repair_when_initial_model_passes(
    monkeypatch,
):
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "distance": 6,
                "width": 80,
                "height": 50,
            }
        ]
    }

    monkeypatch.setattr(
        prompting,
        "prompt_to_model_data",
        lambda user_prompt: model_data,
    )
    monkeypatch.setattr(
        prompting,
        "check_model_data",
        lambda model_data: {
            "passed": True,
            "failure_type": None,
            "reason": "Model data validated and built successfully.",
            "suggested_fixes": [],
        },
    )
    monkeypatch.setattr(
        prompting,
        "repair_model_data",
        lambda *args: (_ for _ in ()).throw(
            AssertionError("Repair should not be called")
        ),
    )

    result_model_data, repair_history = prompting.prompt_to_model_data_with_repair(
        "make a part",
        max_repairs=1,
    )

    assert result_model_data == model_data
    assert repair_history == []


def test_prompt_to_model_data_with_repair_uses_repairable_quality_warnings(
    monkeypatch,
):
    failed_model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "distance": 6,
                "width": 80,
                "height": 50,
            },
            {
                "type": "add_extrude",
                "id": "feature_1",
                "target": "base.top_outer_edges",
                "profile": "rectangle",
                "positions": [[0, 0]],
                "distance": 6,
                "width": 20,
                "height": 12,
            },
        ]
    }
    repaired_model_data = {
        "operations": [
            failed_model_data["operations"][0],
            {
                **failed_model_data["operations"][1],
                "target": "base.top",
            },
        ]
    }
    repair_calls = []

    monkeypatch.setattr(
        prompting,
        "prompt_to_model_data",
        lambda user_prompt: failed_model_data,
    )
    monkeypatch.setattr(
        prompting,
        "check_model_data",
        lambda model_data: {
            "passed": True,
            "failure_type": None,
            "reason": "Model data validated and built successfully.",
            "suggested_fixes": [],
        },
    )

    def fake_repair_model_data(
        user_prompt: str,
        model_data: dict,
        failure_analysis: dict,
    ) -> dict:
        repair_calls.append(failure_analysis)
        return repaired_model_data

    monkeypatch.setattr(prompting, "repair_model_data", fake_repair_model_data)

    result_model_data, repair_history = prompting.prompt_to_model_data_with_repair(
        "make a boss",
        max_repairs=1,
    )

    assert result_model_data == repaired_model_data
    assert len(repair_calls) == 1
    assert repair_calls[0]["failure_type"] == "quality_gate_failed"
    assert "face_operation_targets_edge" in repair_calls[0][
        "repairable_quality_codes"
    ]
    assert repair_history[0]["failure_analysis"]["quality_report"]["status"] == (
        "warning"
    )


def test_build_generation_input_returns_plain_prompt_without_examples(monkeypatch):
    monkeypatch.setattr(
        prompting,
        "select_relevant_examples",
        lambda user_prompt, max_examples: [],
    )

    assert prompting.build_generation_input("make a plate") == "make a plate"


def test_build_generation_input_includes_retrieved_examples(monkeypatch):
    example = {
        "name": "simple_plate",
        "description": "A simple rectangular plate.",
        "tags": ["rectangle", "plate"],
        "construction_plan": ["Create a rectangular base extrusion."],
        "model_data": {
            "operations": [
                {
                    "type": "extrude",
                    "id": "base",
                    "plane": "XY",
                    "profile": "rectangle",
                    "distance": 6,
                    "width": 80,
                    "height": 50,
                }
            ]
        },
        "notes": ["Use the base operation first."],
        "source_file": "simple_plate.json",
    }

    monkeypatch.setattr(
        prompting,
        "select_relevant_examples",
        lambda user_prompt, max_examples: [example],
    )

    generation_input = json.loads(prompting.build_generation_input("make a plate"))

    assert generation_input["user_prompt"] == "make a plate"
    assert generation_input["retrieved_examples"][0]["name"] == "simple_plate"
    assert "source_file" not in generation_input["retrieved_examples"][0]


def test_prompt_to_model_data_via_intent_lowers_generated_intent(monkeypatch):
    intent = {
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 100,
            "height": 70,
            "thickness": 8,
        },
        "features": [
            {
                "id": "corner_holes",
                "operation": "cut",
                "target": "base.top",
                "shape": "circle",
                "diameter": 6,
                "depth": "through",
                "placement": {
                    "type": "near_corners",
                    "count": 4,
                    "margin": 7,
                },
            }
        ],
    }

    monkeypatch.setattr(
        prompting,
        "prompt_to_design_intent",
        lambda user_prompt: intent,
    )

    model_data = prompting.prompt_to_model_data_via_intent(
        "make a plate with four corner holes"
    )

    assert model_data["operations"][1]["id"] == "corner_holes"
    assert model_data["operations"][1]["positions"] == [
        [-40, 25],
        [40, 25],
        [-40, -25],
        [40, -25],
    ]
