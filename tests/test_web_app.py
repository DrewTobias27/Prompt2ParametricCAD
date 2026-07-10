"""Tests for local FastAPI route helpers."""

import cadquery as cq

from prompt2cad import web_app


def test_generate_cad_from_design_intent_returns_intent_and_model(monkeypatch):
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


def test_export_model_data_returns_quality_report(monkeypatch, tmp_path):
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


def test_build_cad_error_response_localizes_build_failure(monkeypatch):
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
