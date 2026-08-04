"""Tests for correctness-first OpenAI model matrix orchestration."""

import json
import os

from prompt2cad import model_matrix_eval


def fake_report(mode_statuses):
    """Return a small report shaped like tiny_api_compare output."""
    return {
        "cases": [
            {
                "case": "case_1",
                "results": [
                    {
                        "mode": mode,
                        "status": status,
                        "elapsed_seconds": 2.0,
                        "repair_count": 1 if mode == "intent_feedback" else 0,
                        "api_telemetry": {
                            "logical_api_calls": (
                                2 if mode == "intent_feedback" else 1
                            ),
                            "total_tokens": 100,
                        },
                    }
                    for mode, status in mode_statuses.items()
                ],
            }
        ],
    }


def test_compare_model_matrix_runs_both_check_suites_and_ranks(tmp_path, monkeypatch):
    prompt_file = tmp_path / "prompts.json"
    prompt_file.write_text(
        json.dumps({"cases": [{"name": "case_1", "prompt": "Make a plate."}]}),
        encoding="utf-8",
    )
    calls = []

    def fake_semantic(prompt_cases, output_path, skip_preflight, modes):
        model = os.environ["PROMPT2CAD_OPENAI_MODEL"]
        calls.append(("semantic", model, modes))
        return fake_report({
            "intent": "pass" if model == "better" else "warn",
            "intent_feedback": "pass",
        })

    def fake_exact(case_names, cases_dir, output_path, skip_preflight, modes):
        model = os.environ["PROMPT2CAD_OPENAI_MODEL"]
        calls.append(("exact", model, modes))
        return fake_report({
            "intent": "pass" if model == "better" else "warn",
            "intent_feedback": "pass" if model == "better" else "warn",
        })

    monkeypatch.setattr(model_matrix_eval, "compare_prompt_cases", fake_semantic)
    monkeypatch.setattr(model_matrix_eval, "compare_eval_cases", fake_exact)
    monkeypatch.setattr(
        model_matrix_eval,
        "check_openai_connection",
        lambda: {"passed": True},
    )

    report = model_matrix_eval.compare_model_matrix(
        ["baseline", "better"],
        prompt_file=prompt_file,
        prompt_case_names=["case_1"],
        eval_case_names=["exact_case"],
        cases_dir=tmp_path / "cases",
        output_root=tmp_path / "matrix",
        modes=["intent", "intent_feedback"],
        reasoning_effort="low",
    )

    assert report["ranking"] == ["better", "baseline"]
    assert report["model_results"][1]["production"]["strict_pass_rate"] == 1.0
    assert len(calls) == 4
    assert (tmp_path / "matrix" / "comparison_report.json").exists()
    assert "PROMPT2CAD_OPENAI_MODEL" not in os.environ


def test_model_score_prefers_correctness_before_speed():
    slower_correct = {
        "first_pass": {
            "status_counts": {"pass": 2, "warn": 0, "fail": 0},
        },
        "production": {
            "status_counts": {"pass": 2, "warn": 0, "fail": 0},
            "repair_count": 2,
            "average_seconds": 10,
            "average_tokens": 1000,
        },
    }
    faster_incorrect = {
        "first_pass": {
            "status_counts": {"pass": 1, "warn": 1, "fail": 0},
        },
        "production": {
            "status_counts": {"pass": 1, "warn": 1, "fail": 0},
            "repair_count": 0,
            "average_seconds": 1,
            "average_tokens": 100,
        },
    }

    assert (
        model_matrix_eval.model_score(slower_correct)
        > model_matrix_eval.model_score(faster_incorrect)
    )


def test_result_metrics_uses_paired_first_pass_from_feedback_result():
    report = {
        "cases": [{
            "case": "paired",
            "results": [{
                "mode": "intent_feedback",
                "status": "pass",
                "elapsed_seconds": 4.0,
                "repair_count": 1,
                "api_telemetry": {"logical_api_calls": 2, "total_tokens": 300},
                "first_pass_result": {
                    "mode": "intent",
                    "status": "warn",
                    "elapsed_seconds": 2.0,
                    "api_telemetry": {
                        "logical_api_calls": 1,
                        "total_tokens": 120,
                    },
                },
            }],
        }],
    }

    first_pass = model_matrix_eval.result_metrics([report], "intent")
    production = model_matrix_eval.result_metrics([report], "intent_feedback")

    assert first_pass["status_counts"]["warn"] == 1
    assert first_pass["logical_api_calls"] == 1
    assert production["status_counts"]["pass"] == 1
    assert production["repair_count"] == 1
