"""Tests for prompt generation and repair control flow."""

import json
from types import SimpleNamespace

import httpx
from openai import APIStatusError

from prompt2cad import prompting
from prompt2cad.design_intent import missing_required_intent_dimensions


def test_create_json_response_retries_any_http_400_without_schema():
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    response = httpx.Response(400, request=request)
    bad_request = APIStatusError(
        "Error code: 400",
        response=response,
        body={"error": {"message": "Invalid schema"}},
    )

    class Responses:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                raise bad_request
            return type("Response", (), {"output_text": '{"operations": []}'})()

    responses = Responses()
    client = type("Client", (), {"responses": responses})()

    result = prompting.create_json_response(
        client,
        model="test-model",
        instructions="Return CAD JSON.",
        input_text="make a plate",
        schema={"type": "object"},
        schema_name="cad_model",
    )

    assert result == {"operations": []}
    assert "text" in responses.calls[0]
    assert "text" not in responses.calls[1]


def test_create_json_response_collects_non_secret_usage_telemetry():
    response = SimpleNamespace(
        output_text='{"operations": []}',
        model="gpt-test-snapshot",
        usage=SimpleNamespace(
            input_tokens=120,
            output_tokens=45,
            total_tokens=165,
            input_tokens_details=SimpleNamespace(cached_tokens=80),
            output_tokens_details=SimpleNamespace(reasoning_tokens=30),
        ),
    )

    class Responses:
        def create(self, **kwargs):
            return response

    client = SimpleNamespace(responses=Responses())
    telemetry = {}

    result = prompting.create_json_response(
        client,
        model="gpt-test",
        instructions="Return CAD JSON.",
        input_text="make a plate",
        schema={"type": "object"},
        schema_name="cad_model",
        telemetry=telemetry,
    )

    assert result == {"operations": []}
    assert telemetry == {
        "requested_model": "gpt-test",
        "response_model": "gpt-test-snapshot",
        "api_attempts": 1,
        "structured_outputs": True,
        "input_tokens": 120,
        "output_tokens": 45,
        "total_tokens": 165,
        "cached_input_tokens": 80,
        "reasoning_tokens": 30,
        "api_seconds": 0.0,
    }


def test_create_json_response_passes_optional_reasoning_effort():
    calls = []

    class Responses:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(output_text='{"operations": []}')

    prompting.create_json_response(
        SimpleNamespace(responses=Responses()),
        model="gpt-test",
        instructions="Return CAD JSON.",
        input_text="make a plate",
        schema={"type": "object"},
        schema_name="cad_model",
        reasoning_effort="low",
    )

    assert calls[0]["reasoning"] == {"effort": "low"}


def test_openai_model_uses_task_specific_then_general_override(monkeypatch):
    monkeypatch.delenv("PROMPT2CAD_OPENAI_MODEL", raising=False)
    monkeypatch.delenv("PROMPT2CAD_REPAIR_MODEL", raising=False)

    assert prompting.openai_model("repair") == "gpt-5.5"

    monkeypatch.setenv("PROMPT2CAD_OPENAI_MODEL", "gpt-5.5")
    assert prompting.openai_model("repair") == "gpt-5.5"

    monkeypatch.setenv("PROMPT2CAD_REPAIR_MODEL", "gpt-5.5-pro")
    assert prompting.openai_model("repair") == "gpt-5.5-pro"


def test_openai_reasoning_effort_uses_task_specific_then_general_override(
    monkeypatch,
):
    monkeypatch.delenv("PROMPT2CAD_REASONING_EFFORT", raising=False)
    monkeypatch.delenv("PROMPT2CAD_INTENT_REASONING_EFFORT", raising=False)

    assert prompting.openai_reasoning_effort("intent") == "low"

    monkeypatch.setenv("PROMPT2CAD_REASONING_EFFORT", "medium")
    assert prompting.openai_reasoning_effort("intent") == "medium"

    monkeypatch.setenv("PROMPT2CAD_INTENT_REASONING_EFFORT", "LOW")
    assert prompting.openai_reasoning_effort("intent") == "low"


def test_max_repair_attempts_defaults_to_three_and_is_bounded(monkeypatch):
    monkeypatch.delenv("PROMPT2CAD_MAX_REPAIRS", raising=False)
    monkeypatch.delenv("PROMPT2CAD_INTENT_MAX_REPAIRS", raising=False)
    assert prompting.max_repair_attempts("intent") == 3

    monkeypatch.setenv("PROMPT2CAD_INTENT_MAX_REPAIRS", "2")
    assert prompting.max_repair_attempts("intent") == 2

    monkeypatch.setenv("PROMPT2CAD_INTENT_MAX_REPAIRS", "4")
    try:
        prompting.max_repair_attempts("intent")
    except ValueError as error:
        assert "between 0 and 3" in str(error)
    else:
        raise AssertionError("Expected repair cap validation")


def test_design_intent_feedback_loop_repairs_failed_candidate(monkeypatch):
    failed_intent = {"candidate": "failed"}
    repaired_intent = {"candidate": "repaired"}
    evaluations = {
        "failed": {
            "passed": False,
            "model_data": None,
            "feedback": {"lowering_error": "missing diameter"},
        },
        "repaired": {
            "passed": True,
            "model_data": {"operations": [{"id": "base"}]},
            "feedback": {},
        },
    }
    repair_calls = []

    monkeypatch.setattr(
        prompting,
        "prompt_to_design_intent",
        lambda prompt: failed_intent,
    )
    monkeypatch.setattr(
        prompting,
        "evaluate_design_intent_candidate",
        lambda intent: evaluations[intent["candidate"]],
    )

    def fake_repair(prompt, intent, feedback):
        repair_calls.append((prompt, intent, feedback))
        return repaired_intent

    monkeypatch.setattr(prompting, "repair_design_intent", fake_repair)

    intent, model_data, history, evaluation = (
        prompting.prompt_to_design_intent_with_feedback(
            "make a plate with a hole",
            max_repairs=3,
        )
    )

    assert intent == repaired_intent
    assert model_data == {"operations": [{"id": "base"}]}
    assert evaluation["passed"] is True
    assert len(history) == 1
    assert repair_calls[0][2] == {"lowering_error": "missing diameter"}


def test_refine_design_intent_sends_saved_intent_and_focused_correction(
    monkeypatch,
):
    previous_intent = {
        "required_concepts": ["plate", "boss"],
        "base": {
            "id": "base",
            "role": "plate",
            "profile": "rectangle",
            "width": 80,
            "height": 50,
            "thickness": 6,
        },
        "features": [
            {
                "id": "center_boss",
                "role": "boss",
                "operation": "extrusion",
                "target": "base.top",
                "shape": "circle",
                "placement": {"type": "centered"},
                "diameter": 20,
                "distance": 8,
            }
        ],
        "edge_treatments": [],
    }
    captured = {}

    monkeypatch.setattr(prompting, "create_openai_client", lambda: object())

    def fake_create_json_response(client, **kwargs):
        captured.update(kwargs)
        return {
            "required_concepts": ["plate", "boss"],
            "base": {
                "id": "base",
                "role": "plate",
                "profile": "rectangle",
                "width": 80,
                "height": 50,
                "thickness": 6,
            },
            "features": [
                {
                    "id": "center_boss",
                    "role": "boss",
                    "target": "base.top",
                    "placement": {"type": "centered"},
                    "operation": {"type": "extrusion", "distance": 12},
                    "shape": {"type": "circle", "diameter": 20},
                }
            ],
            "edge_treatments": [],
        }

    monkeypatch.setattr(prompting, "create_json_response", fake_create_json_response)

    refined = prompting.refine_design_intent(
        "Create a plate with a centered circular boss.",
        previous_intent,
        "Make the boss 12 mm tall.",
    )

    request = json.loads(captured["input_text"])
    assert request["original_user_prompt"].startswith("Create a plate")
    assert request["user_correction"] == "Make the boss 12 mm tall."
    assert request["previous_design_intent"]["features"][0]["id"] == "center_boss"
    assert captured["schema_name"] == "cad_refined_design_intent"
    assert refined["features"][0]["id"] == "center_boss"
    assert refined["features"][0]["distance"] == 12


def test_refinement_feedback_loop_repairs_an_invalid_revision(monkeypatch):
    initial_intent = {"candidate": "initial"}
    repaired_intent = {"candidate": "repaired"}
    repair_calls = []

    monkeypatch.setattr(
        prompting,
        "refine_design_intent",
        lambda prompt, previous, correction: initial_intent,
    )
    monkeypatch.setattr(
        prompting,
        "evaluate_design_intent_candidate",
        lambda intent: {
            "passed": intent is repaired_intent,
            "model_data": {"operations": [{"id": "base"}]}
            if intent is repaired_intent
            else None,
            "feedback": {} if intent is repaired_intent else {"error": "repair me"},
        },
    )

    def fake_repair(prompt, intent, feedback):
        repair_calls.append((prompt, intent, feedback))
        return repaired_intent

    monkeypatch.setattr(prompting, "repair_design_intent", fake_repair)

    intent, model_data, history, evaluation = (
        prompting.refine_design_intent_with_feedback(
            "Create a plate with a centered boss.",
            {"candidate": "previous"},
            "Make the boss taller.",
            max_repairs=1,
        )
    )

    assert intent is repaired_intent
    assert model_data == {"operations": [{"id": "base"}]}
    assert evaluation["passed"] is True
    assert len(history) == 1
    assert "User-requested revision: Make the boss taller." in repair_calls[0][0]


def test_refinement_direction_feedback_rejects_inward_margin_decrease():
    previous = {
        "features": [{
            "id": "corner_holes",
            "placement": {"type": "near_corners", "count": 4, "margin": 10},
        }],
    }
    candidate = {
        "features": [{
            "id": "corner_holes",
            "placement": {"type": "near_corners", "count": 4, "margin": 5},
        }],
    }

    feedback = prompting.refinement_direction_feedback(
        previous,
        candidate,
        "Move the holes 5 mm inward from both plate edges.",
    )

    assert feedback["code"] == "wrong_directional_placement_change"
    assert feedback["wrong_changes"][0]["control"] == "near_corners.margin"


def test_refinement_direction_feedback_accepts_inward_margin_increase():
    previous = {
        "features": [{
            "id": "corner_holes",
            "placement": {"type": "near_corners", "count": 4, "margin": 10},
        }],
    }
    candidate = {
        "features": [{
            "id": "corner_holes",
            "placement": {"type": "near_corners", "count": 4, "margin": 15},
        }],
    }

    assert prompting.refinement_direction_feedback(
        previous,
        candidate,
        "Move the holes 5 mm inward from both plate edges.",
    ) is None


def test_refinement_feedback_repairs_wrong_directional_change(monkeypatch):
    previous = {
        "features": [{
            "id": "corner_holes",
            "placement": {"type": "near_corners", "count": 4, "margin": 10},
        }],
    }
    wrong = {
        "features": [{
            "id": "corner_holes",
            "placement": {"type": "near_corners", "count": 4, "margin": 5},
        }],
    }
    repaired = {
        "features": [{
            "id": "corner_holes",
            "placement": {"type": "near_corners", "count": 4, "margin": 15},
        }],
    }
    repair_feedback = []

    monkeypatch.setattr(prompting, "refine_design_intent", lambda *args: wrong)
    monkeypatch.setattr(
        prompting,
        "evaluate_design_intent_candidate",
        lambda intent: {
            "passed": True,
            "model_data": {"operations": [{"id": "base"}]},
            "feedback": {},
        },
    )

    def fake_repair(prompt, intent, feedback):
        repair_feedback.append(feedback)
        return repaired

    monkeypatch.setattr(prompting, "repair_design_intent", fake_repair)

    intent, _, history, evaluation = prompting.refine_design_intent_with_feedback(
        "Create a plate with four corner holes.",
        previous,
        "Move the holes 5 mm inward from both plate edges.",
        max_repairs=1,
    )

    assert intent is repaired
    assert evaluation["passed"] is True
    assert len(history) == 1
    assert repair_feedback[0]["refinement_semantics"]["code"] == (
        "wrong_directional_placement_change"
    )


def test_design_intent_feedback_loop_does_not_repair_valid_candidate(monkeypatch):
    intent = {"candidate": "valid"}
    evaluation = {
        "passed": True,
        "model_data": {"operations": [{"id": "base"}]},
        "feedback": {},
    }
    monkeypatch.setattr(prompting, "prompt_to_design_intent", lambda prompt: intent)
    monkeypatch.setattr(
        prompting,
        "evaluate_design_intent_candidate",
        lambda candidate: evaluation,
    )
    monkeypatch.setattr(
        prompting,
        "repair_design_intent",
        lambda *args: (_ for _ in ()).throw(
            AssertionError("A passing candidate must not spend a repair call")
        ),
    )

    result_intent, model_data, history, final_evaluation = (
        prompting.prompt_to_design_intent_with_feedback(
            "make a valid plate",
            max_repairs=3,
        )
    )

    assert result_intent is intent
    assert model_data == evaluation["model_data"]
    assert history == []
    assert final_evaluation is evaluation


def test_design_intent_feedback_loop_stops_on_unchanged_repair(monkeypatch):
    intent = {"candidate": "unchanged"}
    evaluation = {
        "passed": False,
        "model_data": None,
        "feedback": {"lowering_error": "still invalid"},
    }
    monkeypatch.setattr(prompting, "prompt_to_design_intent", lambda prompt: intent)
    monkeypatch.setattr(
        prompting,
        "evaluate_design_intent_candidate",
        lambda candidate: evaluation,
    )
    monkeypatch.setattr(
        prompting,
        "repair_design_intent",
        lambda *args: intent,
    )

    _, _, history, final_evaluation = prompting.prompt_to_design_intent_with_feedback(
        "make an impossible part",
        max_repairs=3,
    )

    assert final_evaluation is evaluation
    assert len(history) == 1
    assert history[0]["stopped_reason"] == "unchanged_candidate"


def test_design_intent_feedback_loop_aggregates_generation_and_repair_usage(
    monkeypatch,
):
    failed_intent = {"candidate": "failed"}
    repaired_intent = {"candidate": "repaired"}

    def fake_generate(prompt, telemetry=None):
        telemetry.update({
            "requested_model": "test-model",
            "response_model": "test-model-snapshot",
            "api_attempts": 1,
            "input_tokens": 100,
            "output_tokens": 20,
            "total_tokens": 120,
        })
        return failed_intent

    def fake_repair(prompt, intent, feedback, telemetry=None):
        telemetry.update({
            "requested_model": "test-model",
            "response_model": "test-model-snapshot",
            "api_attempts": 1,
            "input_tokens": 150,
            "output_tokens": 30,
            "total_tokens": 180,
        })
        return repaired_intent

    monkeypatch.setattr(prompting, "prompt_to_design_intent", fake_generate)
    monkeypatch.setattr(prompting, "repair_design_intent", fake_repair)
    monkeypatch.setattr(
        prompting,
        "evaluate_design_intent_candidate",
        lambda intent: {
            "passed": intent is repaired_intent,
            "model_data": {"operations": []} if intent is repaired_intent else None,
            "feedback": {} if intent is repaired_intent else {"error": "repair me"},
        },
    )
    telemetry = {}

    prompting.prompt_to_design_intent_with_feedback(
        "make a part",
        max_repairs=1,
        telemetry=telemetry,
    )

    assert telemetry["logical_api_calls"] == 2
    assert telemetry["api_attempts"] == 2
    assert telemetry["input_tokens"] == 250
    assert telemetry["output_tokens"] == 50
    assert telemetry["total_tokens"] == 300
    assert telemetry["response_models"] == ["test-model-snapshot"]


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
        "evaluate_model_candidate",
        lambda model_data: {
            "passed": model_data == repaired_model_data,
            "quality_report": {
                "passed": model_data == repaired_model_data,
                "status": "pass" if model_data == repaired_model_data else "fail",
                "issues": [],
            },
            "operation_effects": {
                "passed": True,
                "failures": [],
                "warnings": [],
                "trace": [],
            },
            "feedback": {},
        },
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
    assert failure_analysis["quality_report"]["passed"] is False
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
    monkeypatch.setattr(
        prompting,
        "evaluate_model_candidate",
        lambda model_data: {
            "passed": model_data == repaired_model_data,
            "quality_report": {
                "passed": True,
                "status": "pass" if model_data == repaired_model_data else "warning",
                "issues": [] if model_data == repaired_model_data else [{
                    "severity": "warning",
                    "code": "face_operation_targets_edge",
                    "suggestion": "Target a face instead of an edge selector.",
                }],
            },
            "operation_effects": {
                "passed": True,
                "failures": [],
                "warnings": [],
                "trace": [],
            },
            "feedback": {},
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


def test_build_intent_generation_input_uses_prompt_to_intent_pairs(monkeypatch):
    example = {
        "name": "centered_boss",
        "prompt": "Create a plate with a centered circular boss.",
        "tags": ["plate", "boss", "centered"],
        "design_intent": {
            "base": {
                "id": "base",
                "profile": "rectangle",
                "width": 80,
                "height": 50,
                "thickness": 6,
            },
            "features": [{
                "id": "boss",
                "operation": "extrusion",
                "target": "base.top",
                "shape": "circle",
                "diameter": 20,
                "distance": 8,
                "placement": {"type": "centered"},
            }],
        },
        "source_file": "centered_boss.json",
    }
    monkeypatch.setattr(
        prompting,
        "select_relevant_intent_examples",
        lambda user_prompt, max_examples: [example],
    )

    generation_input = json.loads(
        prompting.build_intent_generation_input("make a centered boss")
    )

    retrieved = generation_input["retrieved_intent_examples"][0]
    assert retrieved["prompt"] == example["prompt"]
    retrieved_feature = retrieved["design_intent"]["features"][0]
    assert retrieved_feature["operation"] == {
        "type": "extrusion",
        "distance": 8,
    }
    assert retrieved_feature["shape"] == {
        "type": "circle",
        "diameter": 20,
    }
    assert "model_data" not in retrieved
    assert "source_file" not in retrieved


def test_prompt_to_design_intent_uses_intent_examples_not_operation_examples(
    monkeypatch,
):
    calls = []
    monkeypatch.setattr(prompting, "create_openai_client", lambda: object())
    monkeypatch.setattr(
        prompting,
        "build_intent_generation_input",
        lambda prompt: "intent-specific-input",
    )
    monkeypatch.setattr(
        prompting,
        "build_generation_input",
        lambda prompt: (_ for _ in ()).throw(
            AssertionError("The intent path must not use operation examples")
        ),
    )

    def fake_create_json_response(client, **kwargs):
        calls.append(kwargs)
        return {
            "required_concepts": ["plate", "boss"],
            "base": {
                "id": "base",
                "role": "plate",
                "profile": "rectangle",
                "width": 80,
                "height": 50,
                "thickness": 6,
            },
            "features": [{
                "id": "boss",
                "role": "boss",
                "target": "base.top",
                "placement": {"type": "centered"},
                "operation": {"type": "extrusion", "distance": 8},
                "shape": {"type": "circle", "diameter": 20},
            }],
            "edge_treatments": [],
        }

    monkeypatch.setattr(prompting, "create_json_response", fake_create_json_response)

    result = prompting.prompt_to_design_intent("make a flange")

    assert calls[0]["input_text"] == "intent-specific-input"
    assert calls[0]["schema_name"] == "cad_design_intent"
    assert result["features"][0]["operation"] == "extrusion"
    assert result["features"][0]["shape"] == "circle"
    assert result["features"][0]["diameter"] == 20
    assert result["features"][0]["distance"] == 8


def test_missing_required_intent_dimensions_reports_api_omissions():
    intent = {
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 100,
            "height": 60,
            "thickness": 8,
        },
        "features": [
            {
                "id": "corner_holes",
                "operation": "cut",
                "target": "base.top",
                "shape": "circle",
                "diameter": None,
                "depth": "through",
                "placement": {
                    "type": "near_corners",
                    "count": 4,
                    "margin": None,
                },
            },
            {
                "id": "center_boss",
                "operation": "extrusion",
                "target": "base.top",
                "shape": "rectangle",
                "width": None,
                "height": 15,
                "distance": None,
                "placement": {
                    "type": "centered",
                },
            },
        ],
    }

    assert missing_required_intent_dimensions(intent) == [
        {
            "kind": "feature",
            "id": "corner_holes",
            "fields": ["diameter"],
        },
        {
            "kind": "feature",
            "id": "center_boss",
            "fields": ["width", "distance"],
        },
    ]
