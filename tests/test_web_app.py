"""Tests for local FastAPI route helpers."""

import cadquery as cq

from prompt2cad import web_app


def test_generate_cad_from_design_intent_returns_intent_and_model(monkeypatch):
    web_app.SUCCESS_RESPONSE_CACHE.clear()
    design_intent = {
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 80,
            "height": 50,
            "thickness": 6,
        },
        "features": [],
    }
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 80,
                "height": 50,
                "distance": 6,
            }
        ],
        "relationships": [],
    }

    monkeypatch.setattr(
        web_app,
        "prompt_to_design_intent",
        lambda prompt: design_intent,
    )
    monkeypatch.setattr(
        web_app,
        "intent_to_model_data",
        lambda intent: model_data,
    )
    monkeypatch.setattr(
        web_app,
        "export_model_data",
        lambda generated_model_data, filename_hint: {
            "status": "success",
            "model_data": generated_model_data,
            "step_file": "generated/web/test.step",
            "download_url": "/download/test.step",
        },
    )

    response = web_app.generate_cad_from_design_intent(
        web_app.CADRequest(prompt="make a simple plate")
    )

    assert response["status"] == "success"
    assert response["generation_mode"] == "design_intent"
    assert response["design_intent"] == design_intent
    assert response["model_data"] == model_data
    assert response["performance"]["cache_hit"] is False


def test_generate_cad_from_design_intent_caches_successful_responses(monkeypatch):
    web_app.SUCCESS_RESPONSE_CACHE.clear()
    design_intent = {
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 80,
            "height": 50,
            "thickness": 6,
        },
        "features": [],
    }
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 80,
                "height": 50,
                "distance": 6,
            }
        ],
        "relationships": [],
    }
    calls = {"api": 0, "export": 0}

    def fake_prompt_to_design_intent(prompt):
        calls["api"] += 1
        return design_intent

    def fake_export_model_data(generated_model_data, filename_hint):
        calls["export"] += 1
        return {
            "status": "success",
            "model_data": generated_model_data,
            "step_file": "generated/web/test.step",
            "download_url": "/download/test.step",
            "performance": {"cache_hit": False},
        }

    monkeypatch.setattr(web_app, "prompt_to_design_intent", fake_prompt_to_design_intent)
    monkeypatch.setattr(web_app, "intent_to_model_data", lambda intent: model_data)
    monkeypatch.setattr(web_app, "export_model_data", fake_export_model_data)

    first_response = web_app.generate_cad_from_design_intent(
        web_app.CADRequest(prompt="make a cached plate")
    )
    second_response = web_app.generate_cad_from_design_intent(
        web_app.CADRequest(prompt="make a cached plate")
    )

    assert first_response["performance"]["cache_hit"] is False
    assert second_response["performance"]["cache_hit"] is True
    assert calls == {"api": 1, "export": 1}
    assert second_response["model_data"] == model_data


def test_generate_cad_logs_repaired_prompt_generation(monkeypatch, tmp_path):
    web_app.SUCCESS_RESPONSE_CACHE.clear()
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 80,
                "height": 50,
                "distance": 6,
            }
        ]
    }
    repair_history = [
        {
            "failure_analysis": {"passed": False},
            "failed_model_data": {"operations": []},
            "repaired_model_data": model_data,
        }
    ]
    log_calls = []

    monkeypatch.setattr(
        web_app,
        "prompt_to_model_data_with_repair",
        lambda prompt, max_repairs: (model_data, repair_history),
    )
    monkeypatch.setattr(
        web_app,
        "export_model_data",
        lambda generated_model_data, filename_hint: {
            "status": "success",
            "model_data": generated_model_data,
            "quality_report": {"status": "pass"},
            "step_file": "generated/web/test.step",
            "download_url": "/download/test.step",
        },
    )

    def fake_save_generation_log(**kwargs):
        log_calls.append(kwargs)
        return tmp_path / "repair-log.json"

    monkeypatch.setattr(web_app, "save_generation_log", fake_save_generation_log)

    response = web_app.generate_cad(
        web_app.CADRequest(prompt="make a repaired plate")
    )

    assert response["status"] == "success"
    assert response["repair_history"] == repair_history
    assert response["generation_log"] == str(tmp_path / "repair-log.json")
    assert len(log_calls) == 1
    assert log_calls[0]["prompt"] == "make a repaired plate"
    assert log_calls[0]["final_model_data"] == model_data
    assert log_calls[0]["repair_history"] == repair_history
    assert log_calls[0]["quality_report"] == {"status": "pass"}


def test_export_model_data_returns_quality_report(monkeypatch, tmp_path):
    web_app.SUCCESS_RESPONSE_CACHE.clear()
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 80,
                "height": 50,
                "distance": 6,
            }
        ]
    }

    monkeypatch.setattr(web_app, "GENERATED_DIR", tmp_path)
    monkeypatch.setattr(web_app, "build_model", lambda data: cq.Workplane("XY").box(80, 50, 6))
    monkeypatch.setattr(
        web_app.cq.exporters,
        "export",
        lambda part, path: web_app.Path(path).write_text(
            "STEP DATA",
            encoding="utf-8",
        ),
    )

    response = web_app.export_model_data(model_data, "simple plate")

    assert response["status"] == "success"
    assert response["model_data"] == model_data
    assert response["quality_report"]["status"] == "pass"
    assert response["quality_report"]["stages"]["build"] == "pass"
    assert response["quality_report"]["stages"]["export"] == "pass"
    assert response["quality_report"]["stages"]["geometry"] == "pass"
    assert response["quality_report"]["geometry_summary"]["solid_count"] == 1
    assert response["quality_report"]["issues"] == []
    assert response["performance"]["build_seconds"] >= 0
    assert response["performance"]["export_model_total_seconds"] >= 0


def test_build_cad_error_response_localizes_build_failure(monkeypatch):
    web_app.SUCCESS_RESPONSE_CACHE.clear()
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 80,
                "height": 50,
                "distance": 6,
            },
            {
                "type": "cut",
                "target": "base.Top",
                "profile": "circle",
                "positions": [[0, 0]],
                "diameter": 10,
                "depth": "through",
            },
        ]
    }

    monkeypatch.setattr(
        web_app,
        "build_model",
        lambda data: (_ for _ in ()).throw(
            ValueError("target 'base.Top' was not found")
        ),
    )

    response = web_app.build_cad(
        web_app.CADBuildRequest(model_data=model_data)
    )

    assert response["status"] == "error"
    build_issues = [
        issue for issue in response["quality_report"]["issues"]
        if issue["code"] == "operation_build_failed"
    ]
    assert len(build_issues) == 1
    assert build_issues[0]["operation_number"] == 2


def test_suggest_base_caches_successful_response(monkeypatch):
    web_app.SUCCESS_RESPONSE_CACHE.clear()
    calls = {"api": 0}

    def fake_suggest_base_model_data(**kwargs):
        calls["api"] += 1
        return {
            "operations": [
                {
                    "type": "extrude",
                    "id": "base",
                    "plane": "XY",
                    "profile": "rectangle",
                    "width": 80,
                    "height": 50,
                    "distance": 6,
                }
            ]
        }

    monkeypatch.setattr(
        web_app,
        "suggest_base_model_data",
        fake_suggest_base_model_data,
    )

    request = web_app.CADSuggestBaseRequest(
        profile="rectangle",
        description="reasonable plate",
        distance=None,
    )
    first_response = web_app.suggest_base(request)
    second_response = web_app.suggest_base(request)

    assert first_response["status"] == "success"
    assert first_response["performance"]["cache_hit"] is False
    assert second_response["performance"]["cache_hit"] is True
    assert calls["api"] == 1
