"""Tests for model A/B eval orchestration."""

import os

from prompt2cad import model_ab_eval


def test_compare_models_sets_model_env_and_writes_report(tmp_path, monkeypatch):
    cases_dir = tmp_path / "cases"
    output_root = tmp_path / "ab"
    cases_dir.mkdir()
    calls = []

    def fake_generate_eval_models(
        cases_dir,
        output_dir,
        overwrite,
        case_names,
    ):
        model = os.environ["PROMPT2CAD_OPENAI_MODEL"]
        calls.append(("generate", model, output_dir, overwrite, case_names))
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "case.json"
        output_path.write_text('{"operations": []}', encoding="utf-8")
        return [output_path], []

    def fake_run_batch(models_dir, cases_dir, case_names):
        model = os.environ["PROMPT2CAD_OPENAI_MODEL"]
        calls.append(("run", model, models_dir, case_names))
        return []

    monkeypatch.setattr(
        model_ab_eval,
        "generate_eval_models",
        fake_generate_eval_models,
    )
    monkeypatch.setattr(model_ab_eval, "run_batch", fake_run_batch)

    report = model_ab_eval.compare_models(
        ["gpt-mini", "gpt-better"],
        cases_dir=cases_dir,
        output_root=output_root,
        overwrite=True,
        case_names=["case"],
    )

    assert [model["model"] for model in report["models"]] == [
        "gpt-mini",
        "gpt-better",
    ]
    assert all(model["passed"] for model in report["models"])
    assert calls == [
        ("generate", "gpt-mini", output_root / "gpt-mini", True, ["case"]),
        ("run", "gpt-mini", output_root / "gpt-mini", ["case"]),
        ("generate", "gpt-better", output_root / "gpt-better", True, ["case"]),
        ("run", "gpt-better", output_root / "gpt-better", ["case"]),
    ]
    assert (output_root / "comparison_report.json").exists()


def test_compare_models_restores_existing_model_env(tmp_path, monkeypatch):
    monkeypatch.setenv("PROMPT2CAD_OPENAI_MODEL", "original-model")
    monkeypatch.setattr(
        model_ab_eval,
        "generate_eval_models",
        lambda **kwargs: ([], []),
    )
    monkeypatch.setattr(model_ab_eval, "run_batch", lambda **kwargs: [])

    model_ab_eval.compare_models(
        ["temporary-model"],
        output_root=tmp_path,
    )

    assert os.environ["PROMPT2CAD_OPENAI_MODEL"] == "original-model"
