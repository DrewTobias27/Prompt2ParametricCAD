"""Tests for local FastAPI route helpers."""

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
