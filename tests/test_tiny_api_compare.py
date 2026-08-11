"""Tests for tiny API comparison utilities."""

import json
import sys

import pytest

from prompt2cad import tiny_api_compare


def test_parse_args_accepts_isolated_model_override(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["tiny_api_compare", "--model", "gpt-test", "--mode", "intent"],
    )

    args = tiny_api_compare.parse_args()

    assert args.model == "gpt-test"
    assert args.mode == ["intent"]


def test_parse_args_accepts_strict_release_gate(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["tiny_api_compare", "--require-all-pass"],
    )

    args = tiny_api_compare.parse_args()

    assert args.require_all_pass is True


def test_parse_args_accepts_deployed_service(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "tiny_api_compare",
            "--api-base-url",
            "https://cad.example",
            "--mode",
            "deployed",
        ],
    )

    args = tiny_api_compare.parse_args()

    assert args.api_base_url == "https://cad.example"
    assert args.mode == ["deployed"]


def test_finish_cli_report_fails_strict_gate_on_warning(tmp_path, capsys):
    report = {
        "api_call_budget": 1,
        "cases": [],
        "summary": {
            "case_count": 1,
            "result_count": 1,
            "status_counts": {"pass": 0, "warn": 1, "fail": 0},
            "average_elapsed_seconds": 0,
            "total_elapsed_seconds": 0,
            "slowest_results": [],
        },
    }

    with pytest.raises(SystemExit) as caught:
        tiny_api_compare.finish_cli_report(
            report,
            tmp_path / "report.json",
            require_all_pass=True,
        )

    assert caught.value.code == 1
    assert "RESULTS" in capsys.readouterr().out


def test_finish_cli_report_accepts_all_pass(tmp_path):
    report = {
        "api_call_budget": 1,
        "cases": [],
        "summary": {
            "case_count": 1,
            "result_count": 1,
            "status_counts": {"pass": 1, "warn": 0, "fail": 0},
            "average_elapsed_seconds": 0,
            "total_elapsed_seconds": 0,
            "slowest_results": [],
        },
    }

    tiny_api_compare.finish_cli_report(
        report,
        tmp_path / "report.json",
        require_all_pass=True,
    )


def test_run_deployed_rechecks_returned_model_locally(monkeypatch):
    response_payload = {
        "status": "success",
        "generation_path": "design_intent",
        "generation_mode": "automatic",
        "design_intent": {
            "required_concepts": ["plate"],
            "base": {
                "id": "base",
                "role": "plate",
                "profile": "rectangle",
                "width": 20,
                "height": 12,
                "thickness": 3,
            },
            "features": [],
            "edge_treatments": [],
        },
        "model_data": {
            "operations": [
                {
                    "type": "extrude",
                    "id": "base",
                    "plane": "XY",
                    "profile": "rectangle",
                    "width": 20,
                    "height": 12,
                    "distance": 3,
                }
            ],
            "relationships": [],
        },
        "performance": {"api_seconds": 1.2, "total_seconds": 1.4},
    }

    class FakeResponse:
        status = 200
        reason = "OK"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(response_payload).encode("utf-8")

    monkeypatch.setattr(
        tiny_api_compare,
        "urlopen",
        lambda request, timeout: FakeResponse(),
    )

    result = tiny_api_compare.run_deployed(
        "Create a plate.",
        "https://cad.example/",
    )

    assert result["status"] == "pass"
    assert result["generation_path"] == "design_intent"
    assert result["build_succeeded"] is True
    assert result["operation_effects_passed"] is True
    assert result["intent_coverage_passed"] is True
    assert result["server_performance"]["api_seconds"] == 1.2


def test_load_prompt_cases_from_named_case_file(tmp_path):
    prompt_file = tmp_path / "gap_tests.json"
    prompt_file.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "name": "counterbore",
                        "prompt": "Create a block with a counterbore.",
                        "focus": "counterbore vocabulary",
                    },
                    "Create a hollow box.",
                ]
            }
        ),
        encoding="utf-8",
    )

    assert tiny_api_compare.load_prompt_cases(prompt_file) == [
        {
            "case": "counterbore",
            "prompt": "Create a block with a counterbore.",
            "focus": "counterbore vocabulary",
        },
        {
            "case": "2",
            "prompt": "Create a hollow box.",
        },
    ]


def test_compare_prompt_cases_saves_first_pass_and_feedback_outputs(
    tmp_path,
    monkeypatch,
):
    calls = []

    def fake_run_case(prompt, mode):
        calls.append((prompt, mode))
        return {
            "mode": mode,
            "status": "pass",
            "elapsed_seconds": 0.01,
            "model_data": {
                "operations": [
                    {
                        "type": "extrude",
                        "id": "base",
                        "plane": "XY",
                        "profile": "rectangle",
                        "width": 10,
                        "height": 10,
                        "distance": 2,
                    }
                ],
                "relationships": [],
            },
            "quality_passed": True,
        }

    monkeypatch.setattr(tiny_api_compare, "run_case", fake_run_case)
    monkeypatch.setattr(
        tiny_api_compare,
        "check_openai_connection",
        lambda: {"passed": True},
    )

    output_path = tmp_path / "report.json"
    report = tiny_api_compare.compare_prompt_cases(
        [
            {
                "case": "rounded box",
                "prompt": "Create a rounded box.",
                "focus": "rounded vocabulary",
            }
        ],
        output_path=output_path,
    )

    assert calls == [
        ("Create a rounded box.", "intent_feedback"),
    ]
    assert report["api_call_budget"] == 1
    assert output_path.exists()
    assert (
        tmp_path / "models" / "intent_feedback" / "rounded_box.json"
    ).exists()
    assert report["cases"][0]["focus"] == "rounded vocabulary"
    assert report["summary"]["result_count"] == 1
    assert report["summary"]["status_counts"]["pass"] == 1
    assert report["summary"]["average_elapsed_seconds"] == 0.01


def test_compare_prompt_cases_attaches_concept_expectations(tmp_path, monkeypatch):
    def fake_run_case(prompt, mode):
        return {
            "mode": mode,
            "status": "pass",
            "elapsed_seconds": 0.01,
            "model_data": {
                "operations": [
                    {
                        "type": "extrude",
                        "id": "base",
                        "plane": "XY",
                        "profile": "rectangle",
                        "width": 10,
                        "height": 10,
                        "distance": 2,
                    }
                ],
                "relationships": [],
            },
            "quality_passed": True,
            "quality_report": {
                "geometry_summary": {
                    "solid_count": 1,
                    "bounding_box": {
                        "xlen": 10,
                        "ylen": 10,
                        "zlen": 2,
                    },
                },
            },
        }

    monkeypatch.setattr(tiny_api_compare, "run_case", fake_run_case)
    monkeypatch.setattr(
        tiny_api_compare,
        "check_openai_connection",
        lambda: {"passed": True},
    )

    report = tiny_api_compare.compare_prompt_cases(
        [
            {
                "case": "simple_plate",
                "prompt": "Create a simple plate.",
                "expected_concepts": {
                    "base": {
                        "type": "extrude",
                        "profile": "rectangle",
                    },
                    "geometry": {
                        "solid_count": 1,
                        "bounding_box": {
                            "xlen": {"approx": 10, "tolerance": 0.1},
                        },
                    },
                },
            }
        ],
        output_path=tmp_path / "report.json",
    )

    direct_result = report["cases"][0]["results"][0]
    assert direct_result["concept_passed"] is True
    assert direct_result["concept_failures"] == []


def test_attach_report_summary_counts_statuses_and_slowest_results():
    report = {
        "cases": [
            {
                "case": "fast",
                "results": [
                    {
                        "mode": "intent",
                        "status": "pass",
                        "elapsed_seconds": 1.0,
                        "performance": {
                            "api_seconds": 0.8,
                            "build_seconds": 0.1,
                        },
                    }
                ],
            },
            {
                "case": "slow",
                "results": [
                    {
                        "mode": "intent",
                        "status": "warn",
                        "elapsed_seconds": 3.0,
                        "performance": {
                            "api_seconds": 2.4,
                            "build_seconds": 0.2,
                        },
                    }
                ],
            },
            {
                "case": "fail",
                "results": [
                    {
                        "mode": "direct",
                        "status": "fail",
                        "elapsed_seconds": 2.0,
                        "performance": {
                            "api_seconds": 1.5,
                        },
                    }
                ],
            },
        ]
    }

    tiny_api_compare.attach_report_summary(report)

    assert report["summary"]["case_count"] == 3
    assert report["summary"]["result_count"] == 3
    assert report["summary"]["status_counts"] == {
        "pass": 1,
        "warn": 1,
        "fail": 1,
    }
    assert report["summary"]["mode_counts"] == {
        "intent": 2,
        "direct": 1,
    }
    assert report["summary"]["average_elapsed_seconds"] == 2.0
    assert report["summary"]["total_elapsed_seconds"] == 6.0
    assert report["summary"]["slowest_results"][0]["case"] == "slow"
    assert report["summary"]["performance_totals"] == {
        "api_seconds": 4.7,
        "build_seconds": 0.3,
    }
    assert report["summary"]["performance_averages"] == {
        "api_seconds": 1.567,
        "build_seconds": 0.15,
    }
    assert report["summary"]["performance_sample_counts"] == {
        "api_seconds": 3,
        "build_seconds": 2,
    }
    assert report["summary"]["dominant_stage"] == "api_seconds"


def test_evaluate_model_data_reports_local_stage_timings():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 20,
                "height": 12,
                "distance": 3,
            }
        ]
    }

    result = tiny_api_compare.evaluate_model_data(model_data)

    assert result["build_succeeded"] is True
    assert result["operation_effects_passed"] is True
    assert set(result["performance"]) == {
        "validation_seconds",
        "build_seconds",
        "quality_seconds",
        "operation_effects_seconds",
        "evaluation_total_seconds",
    }
    assert all(value >= 0 for value in result["performance"].values())


def test_run_intent_reports_generation_lowering_and_evaluation_timings(monkeypatch):
    monkeypatch.setattr(
        tiny_api_compare,
        "prompt_to_design_intent",
        lambda prompt, telemetry=None: {
            "required_concepts": ["plate"],
            "base": {
                "id": "base",
                "role": "plate",
                "profile": "rectangle",
                "width": 20,
                "height": 12,
                "thickness": 3,
            },
            "features": [],
            "edge_treatments": [],
        },
    )

    result = tiny_api_compare.run_intent("Create a small plate.")

    assert result["build_succeeded"] is True
    assert set(tiny_api_compare.CANONICAL_TIMING_STAGES[:-1]).issubset(
        result["performance"]
    )
    assert result["performance"]["total_seconds"] >= 0


def test_run_intent_preserves_api_telemetry_when_local_lowering_fails(monkeypatch):
    def fake_prompt(prompt, telemetry=None):
        telemetry.update({"reasoning_tokens": 123})
        return {}

    monkeypatch.setattr(
        tiny_api_compare,
        "prompt_to_design_intent",
        fake_prompt,
    )

    with pytest.raises(Exception) as caught:
        tiny_api_compare.run_intent("Create an invalid test part.")

    assert caught.value.api_telemetry == {"reasoning_tokens": 123}


def test_run_intent_feedback_reports_repairs_and_aggregate_telemetry(monkeypatch):
    def fake_feedback(prompt, telemetry=None):
        telemetry.update({
            "logical_api_calls": 2,
            "total_tokens": 250,
        })
        intent = {
            "required_concepts": ["plate"],
            "base": {
                "id": "base",
                "role": "plate",
                "profile": "rectangle",
                "width": 20,
                "height": 12,
                "thickness": 3,
            },
            "features": [],
            "edge_treatments": [],
        }
        model_data = {
            "operations": [{
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 20,
                "height": 12,
                "distance": 3,
            }],
        }
        return (
            intent,
            model_data,
            [{"attempt": 1, "failed_design_intent": intent}],
            {"passed": True},
        )

    monkeypatch.setattr(
        tiny_api_compare,
        "prompt_to_design_intent_with_feedback",
        fake_feedback,
    )

    result = tiny_api_compare.run_intent_feedback("Create a plate.")

    assert result["repair_count"] == 1
    assert result["recovered_after_feedback"] is True
    assert result["api_telemetry"]["logical_api_calls"] == 2
    assert result["quality_passed"] is True


def test_attach_report_summary_aggregates_api_usage():
    report = {
        "cases": [
            {
                "case": "one",
                "results": [
                    {
                        "mode": "intent",
                        "status": "pass",
                        "elapsed_seconds": 1.0,
                        "api_telemetry": {
                            "input_tokens": 100,
                            "cached_input_tokens": 40,
                            "output_tokens": 20,
                            "reasoning_tokens": 10,
                            "total_tokens": 120,
                        },
                    }
                ],
            },
            {
                "case": "two",
                "results": [
                    {
                        "mode": "intent",
                        "status": "pass",
                        "elapsed_seconds": 2.0,
                        "api_telemetry": {
                            "input_tokens": 200,
                            "cached_input_tokens": 80,
                            "output_tokens": 40,
                            "reasoning_tokens": 20,
                            "total_tokens": 240,
                        },
                    }
                ],
            },
        ]
    }

    tiny_api_compare.attach_report_summary(report)

    assert report["summary"]["api_usage_totals"] == {
        "input_tokens": 300,
        "cached_input_tokens": 120,
        "output_tokens": 60,
        "reasoning_tokens": 30,
        "total_tokens": 360,
    }
    assert report["summary"]["api_usage_averages"] == {
        "input_tokens": 150.0,
        "cached_input_tokens": 60.0,
        "output_tokens": 30.0,
        "reasoning_tokens": 15.0,
        "total_tokens": 180.0,
    }


def test_filter_prompt_cases_uses_requested_names():
    cases = [
        {"case": "shaft", "prompt": "Create a shaft."},
        {"case": "box", "prompt": "Create a box."},
        {"case": "slot", "prompt": "Create a slot."},
    ]

    assert tiny_api_compare.filter_prompt_cases(cases, ["box", "slot"]) == [
        {"case": "box", "prompt": "Create a box."},
        {"case": "slot", "prompt": "Create a slot."},
    ]


def test_compare_prompt_cases_can_run_intent_only(tmp_path, monkeypatch):
    calls = []

    def fake_run_case(prompt, mode):
        calls.append((prompt, mode))
        return {
            "mode": mode,
            "status": "pass",
            "elapsed_seconds": 0.01,
            "model_data": {
                "operations": [
                    {
                        "type": "extrude",
                        "id": "base",
                        "plane": "XY",
                        "profile": "rectangle",
                        "width": 10,
                        "height": 10,
                        "distance": 2,
                    }
                ],
                "relationships": [],
            },
            "quality_passed": True,
        }

    monkeypatch.setattr(tiny_api_compare, "run_case", fake_run_case)
    monkeypatch.setattr(
        tiny_api_compare,
        "check_openai_connection",
        lambda: {"passed": True},
    )

    report = tiny_api_compare.compare_prompt_cases(
        [{"case": "box", "prompt": "Create a box."}],
        output_path=tmp_path / "report.json",
        modes=["intent"],
    )

    assert calls == [("Create a box.", "intent")]
    assert report["api_call_budget"] == 1
    assert report["modes"] == ["intent"]


def test_rescore_report_adds_concept_results_without_api_calls(tmp_path):
    report_path = tmp_path / "old_report.json"
    output_path = tmp_path / "rescored_report.json"
    report_path.write_text(
        json.dumps(
            {
                "api_call_budget": 2,
                "cases": [
                    {
                        "case": "shaft",
                        "prompt": "Create a shaft.",
                        "results": [
                            {
                                "mode": "intent",
                                "status": "warn",
                                "elapsed_seconds": 9.5,
                                "model_data": {
                                    "operations": [
                                        {
                                            "type": "revolve",
                                            "id": "base",
                                            "plane": "XY",
                                            "profile": "rectangle",
                                            "positions": [[5, 0]],
                                            "width": 10,
                                            "height": 80,
                                            "axis_start": [0, -1],
                                            "axis_end": [0, 1],
                                            "angle": 360,
                                        }
                                    ],
                                    "relationships": [],
                                },
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = tiny_api_compare.rescore_report(
        report_path,
        output_path=output_path,
        prompt_cases=[
            {
                "case": "shaft",
                "expected_concepts": {
                    "base": {
                        "type": "revolve",
                        "angle": 360,
                    },
                    "geometry": {
                        "solid_count": 1,
                    },
                },
            }
        ],
    )

    result = report["cases"][0]["results"][0]
    assert report["api_call_budget"] == 0
    assert report["summary"]["result_count"] == 1
    assert output_path.exists()
    assert result["status"] == "pass"
    assert result["quality_passed"] is True
    assert result["concept_passed"] is True
    assert result["original_elapsed_seconds"] == 9.5
    assert result["elapsed_seconds"] >= 0
    assert result["performance"]["total_seconds"] >= 0


def test_rescore_report_uses_current_prompt_case_expectations(tmp_path):
    report_path = tmp_path / "old_report.json"
    report_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case": "shaft",
                        "prompt": "Create a stepped shaft.",
                        "expected_concepts": {
                            "base": {
                                "type": "extrude",
                            }
                        },
                        "results": [
                            {
                                "mode": "intent",
                                "status": "warn",
                                "model_data": {
                                    "operations": [
                                        {
                                            "type": "revolve",
                                            "id": "base",
                                            "plane": "XY",
                                            "profile": "rectangle",
                                            "positions": [[3, 0]],
                                            "width": 6,
                                            "height": 120,
                                            "axis_start": [0, -1],
                                            "axis_end": [0, 1],
                                            "angle": 360,
                                        },
                                        {
                                            "type": "add_revolve",
                                            "id": "step_1",
                                            "plane": "XY",
                                            "profile": "rectangle",
                                            "positions": [[7, 30]],
                                            "width": 2,
                                            "height": 20,
                                            "axis_start": [0, -1],
                                            "axis_end": [0, 1],
                                            "angle": 360,
                                        },
                                        {
                                            "type": "add_revolve",
                                            "id": "step_2",
                                            "plane": "XY",
                                            "profile": "rectangle",
                                            "positions": [[8, -30]],
                                            "width": 4,
                                            "height": 20,
                                            "axis_start": [0, -1],
                                            "axis_end": [0, 1],
                                            "angle": 360,
                                        },
                                    ],
                                    "relationships": [],
                                },
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = tiny_api_compare.rescore_report(
        report_path,
        output_path=tmp_path / "rescored.json",
        prompt_cases=[
            {
                "case": "shaft",
                "expected_concepts": {
                    "base": {
                        "type": "revolve",
                    },
                    "min_operation_counts": {
                        "add_revolve": 2,
                    },
                },
            }
        ],
    )

    assert report["cases"][0]["results"][0]["status"] == "pass"


def test_rescore_report_can_relower_saved_design_intent(tmp_path):
    report_path = tmp_path / "old_report.json"
    report_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case": "countersink",
                        "prompt": "Create a countersunk hole.",
                        "results": [
                            {
                                "mode": "intent",
                                "status": "fail",
                                "message": "Old lowering error",
                                "design_intent": {
                                    "base": {
                                        "id": "base",
                                        "profile": "rectangle",
                                        "width": 80,
                                        "height": 40,
                                        "thickness": 6,
                                    },
                                    "features": [
                                        {
                                            "id": "countersink",
                                            "operation": "revolved_cut",
                                            "target": "base.top",
                                            "shape": "polyline",
                                            "points": [[2.5, 0], [7.5, 0], [0, -2.5]],
                                            "placement": {"type": "centered"},
                                        }
                                    ],
                                    "edge_treatments": [],
                                },
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = tiny_api_compare.rescore_report(
        report_path,
        output_path=tmp_path / "rescored.json",
    )

    result = report["cases"][0]["results"][0]
    assert "message" not in result
    assert result["model_data"]["operations"][1]["type"] == "cut_revolve"
    assert result["model_data"]["operations"][1]["profile"] == "polyline"


def test_rescore_report_relowers_stale_saved_model_data(tmp_path):
    report_path = tmp_path / "old_report.json"
    report_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case": "hex_plate",
                        "prompt": "Create a hexagonal plate.",
                        "results": [
                            {
                                "mode": "intent",
                                "status": "fail",
                                "message": "Old stale lowering error",
                                "design_intent": {
                                    "base": {
                                        "id": "hex_plate",
                                        "profile": "polygon",
                                        "width": 80,
                                        "sides": 6,
                                        "thickness": 6,
                                    },
                                    "features": [],
                                    "edge_treatments": [],
                                },
                                "model_data": {
                                    "operations": [
                                        {
                                            "type": "extrude",
                                            "id": "base",
                                            "plane": "XY",
                                            "profile": "rectangle",
                                            "width": 1,
                                            "height": 1,
                                            "distance": 1,
                                        }
                                    ],
                                    "relationships": [],
                                },
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = tiny_api_compare.rescore_report(
        report_path,
        output_path=tmp_path / "rescored.json",
    )

    result = report["cases"][0]["results"][0]
    assert result["status"] == "pass"
    assert "message" not in result
    assert result["model_data"]["operations"][0]["profile"] == "polygon"
    assert result["model_data"]["operations"][0]["diameter"] == 80.0


def test_rescore_report_warns_on_missing_required_concept(tmp_path):
    report_path = tmp_path / "old_report.json"
    report_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case": "cradle",
                        "prompt": "Create a cradle with a mounting plate.",
                        "results": [
                            {
                                "mode": "intent",
                                "status": "pass",
                                "design_intent": {
                                    "required_concepts": [
                                        "cradle",
                                        "mounting_plate",
                                    ],
                                    "base": {
                                        "id": "base",
                                        "role": "cradle",
                                        "profile": "half_cylinder",
                                        "diameter": 60,
                                        "length": 100,
                                    },
                                    "features": [],
                                    "edge_treatments": [],
                                },
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    report = tiny_api_compare.rescore_report(
        report_path,
        output_path=tmp_path / "rescored.json",
    )

    result = report["cases"][0]["results"][0]
    assert result["status"] == "warn"
    assert result["intent_coverage_passed"] is False
    assert "mounting_plate" in result["intent_coverage_failures"][0]
