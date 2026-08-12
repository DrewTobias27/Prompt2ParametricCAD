"""Tests for local FastAPI route helpers."""

import cadquery as cq
from fastapi import HTTPException
from fastapi.responses import FileResponse
import pytest

from prompt2cad import web_app


def test_health_reports_backend_ready():
    assert web_app.health() == {"status": "ok"}


def test_download_route_rejects_missing_or_unsafe_files(monkeypatch, tmp_path):
    monkeypatch.setattr(web_app, "GENERATED_DIR", tmp_path)

    with pytest.raises(HTTPException, match="STEP file not found"):
        web_app.download_step_file("missing.step")

    with pytest.raises(HTTPException, match="STEP file not found"):
        web_app.download_step_file("../outside.step")


def test_safe_filename_avoids_collisions_after_readable_prefix():
    shared_prefix = "Create a very long mechanical mounting plate " * 3

    first = web_app.make_safe_filename(shared_prefix + "with two holes")
    second = web_app.make_safe_filename(shared_prefix + "with four holes")

    assert first != second
    assert first.endswith(".step")
    assert second.endswith(".step")


def test_editable_routes_are_exposed_in_the_api_contract():
    paths = web_app.app.openapi()["paths"]

    assert "post" in paths["/editable-model"]
    assert "post" in paths["/edit-parameters"]
    assert "post" in paths["/solidworks-package"]


def test_solidworks_package_route_returns_downloadable_zip(monkeypatch):
    class FakePackage:
        filename = "demo-solidworks.zip"
        content = b"zip-bytes"
        manifest = {
            "version": 4,
            "editability": {
                "numeric_parameter_count": 12,
                "named_binding_count": 9,
                "relation_controlled_count": 2,
                "unsupported_count": 1,
                "control_coverage_ratio": 11 / 12,
            },
        }

    monkeypatch.setattr(
        web_app,
        "create_solidworks_package",
        lambda model_data, filename_hint: FakePackage(),
    )

    response = web_app.download_solidworks_package(
        web_app.CADSolidWorksPackageRequest(
            model_data={"operations": []},
            filename_hint="demo",
        )
    )

    assert response.media_type == "application/zip"
    assert response.headers["content-disposition"] == (
        'attachment; filename="demo-solidworks.zip"'
    )
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-prompt2cad-package-version"] == "4"
    assert response.headers["x-prompt2cad-numeric-parameters"] == "12"
    assert response.headers["x-prompt2cad-named-bindings"] == "9"
    assert response.headers["x-prompt2cad-relation-controls"] == "2"
    assert response.headers["x-prompt2cad-unsupported-parameters"] == "1"
    assert float(response.headers["x-prompt2cad-control-coverage"]) == pytest.approx(
        11 / 12
    )
    assert "X-Prompt2CAD-Control-Coverage" in response.headers[
        "access-control-expose-headers"
    ]


def test_solidworks_package_route_reports_unsupported_models(monkeypatch):
    def reject_package(model_data, filename_hint):
        raise ValueError("feature_2 cannot be replayed")

    monkeypatch.setattr(web_app, "create_solidworks_package", reject_package)

    with pytest.raises(HTTPException) as error:
        web_app.download_solidworks_package(
            web_app.CADSolidWorksPackageRequest(
                model_data={"operations": []},
                filename_hint="demo",
            )
        )

    assert error.value.status_code == 422
    assert "feature_2 cannot be replayed" in error.value.detail


def test_home_reports_when_frontend_is_not_built(monkeypatch, tmp_path):
    monkeypatch.setattr(web_app, "FRONTEND_DIST_DIR", tmp_path)

    response = web_app.home()

    assert response["status"] == "ok"
    assert response["frontend"] == "not built"


def test_home_serves_built_frontend(monkeypatch, tmp_path):
    index_path = tmp_path / "index.html"
    index_path.write_text("<main>Prompt2ParametricCAD</main>", encoding="utf-8")
    monkeypatch.setattr(web_app, "FRONTEND_DIST_DIR", tmp_path)

    response = web_app.home()

    assert isinstance(response, FileResponse)
    assert web_app.Path(response.path) == index_path


def test_generate_cad_prefers_design_intent_and_returns_model(monkeypatch):
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
        "prompt_to_design_intent_with_feedback",
        lambda prompt, max_repairs: (
            design_intent,
            model_data,
            [],
            {"passed": True, "feedback": {}},
        ),
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
    monkeypatch.setattr(
        web_app,
        "prompt_to_model_data_with_repair",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Direct fallback should not run")
        ),
    )

    response = web_app.generate_cad(
        web_app.CADRequest(prompt="make a simple plate")
    )

    assert response["status"] == "success"
    assert response["generation_mode"] == "automatic"
    assert response["generation_path"] == "design_intent"
    assert response["design_intent"] == design_intent
    assert response["model_data"] == model_data
    assert response["pipeline_attempts"] == [
        {"path": "design_intent", "status": "success"}
    ]
    assert response["performance"]["cache_hit"] is False
    assert response["performance"]["api_seconds"] >= 0
    assert response["performance"]["lowering_seconds"] >= 0
    assert response["performance"]["local_processing_seconds"] >= 0
    assert response["performance"]["total_seconds"] >= 0


def test_generate_cad_caches_successful_automatic_responses(monkeypatch):
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

    def fake_prompt_to_design_intent(prompt, max_repairs):
        calls["api"] += 1
        return (
            design_intent,
            model_data,
            [],
            {"passed": True, "feedback": {}},
        )

    def fake_export_model_data(generated_model_data, filename_hint):
        calls["export"] += 1
        return {
            "status": "success",
            "model_data": generated_model_data,
            "step_file": "generated/web/test.step",
            "download_url": "/download/test.step",
            "performance": {"cache_hit": False},
        }

    monkeypatch.setattr(
        web_app,
        "prompt_to_design_intent_with_feedback",
        fake_prompt_to_design_intent,
    )
    monkeypatch.setattr(web_app, "export_model_data", fake_export_model_data)

    first_response = web_app.generate_cad(
        web_app.CADRequest(prompt="make a cached plate")
    )
    second_response = web_app.generate_cad(
        web_app.CADRequest(prompt="make a cached plate")
    )

    assert first_response["performance"]["cache_hit"] is False
    assert second_response["performance"]["cache_hit"] is True
    assert calls == {"api": 1, "export": 1}
    assert second_response["model_data"] == model_data


def test_generate_cad_uses_direct_fallback_after_intent_failure(monkeypatch):
    web_app.SUCCESS_RESPONSE_CACHE.clear()
    design_intent = {
        "base": {"id": "base", "profile": "rectangle"},
        "features": [],
    }
    direct_model_data = {
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
    direct_repair_limits = []

    def fake_direct_fallback(prompt, max_repairs):
        direct_repair_limits.append(max_repairs)
        return direct_model_data, []

    monkeypatch.setattr(
        web_app,
        "prompt_to_design_intent_with_feedback",
        lambda prompt, max_repairs: (
            design_intent,
            None,
            [],
            {
                "passed": False,
                "feedback": {"lowering_error": "unsupported relationship"},
            },
        ),
    )
    monkeypatch.setattr(
        web_app,
        "prompt_to_model_data_with_repair",
        fake_direct_fallback,
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
    monkeypatch.setattr(
        web_app,
        "save_generation_log",
        lambda **kwargs: web_app.Path("generated/log.json"),
    )

    response = web_app.generate_cad(
        web_app.CADRequest(prompt="make a compatibility case")
    )

    assert response["status"] == "success"
    assert response["generation_mode"] == "automatic"
    assert response["generation_path"] == "direct_fallback"
    assert response["design_intent"] == design_intent
    assert response["model_data"] == direct_model_data
    assert response["pipeline_attempts"][0]["status"] == "failed"
    assert response["pipeline_attempts"][1] == {
        "path": "direct",
        "status": "success",
    }
    assert response["performance"]["intent_api_seconds"] >= 0
    assert response["performance"]["direct_api_seconds"] >= 0
    assert response["performance"]["lowering_seconds"] >= 0
    assert direct_repair_limits == [2]


def test_generate_cad_does_not_retry_missing_credentials(monkeypatch):
    web_app.SUCCESS_RESPONSE_CACHE.clear()
    direct_calls = []

    monkeypatch.setattr(
        web_app,
        "prompt_to_design_intent_with_feedback",
        lambda prompt, max_repairs: (_ for _ in ()).throw(
            RuntimeError("Missing credentials. Set OPENAI_API_KEY.")
        ),
    )
    monkeypatch.setattr(
        web_app,
        "prompt_to_model_data_with_repair",
        lambda *args, **kwargs: direct_calls.append(True),
    )
    monkeypatch.setattr(
        web_app,
        "save_generation_log",
        lambda **kwargs: web_app.Path("generated/log.json"),
    )

    response = web_app.generate_cad(
        web_app.CADRequest(prompt="make a plate")
    )

    assert response["status"] == "error"
    assert response["generation_path"] == "design_intent"
    assert direct_calls == []


def test_generate_cad_stops_after_intent_repair_budget_is_exhausted(monkeypatch):
    web_app.SUCCESS_RESPONSE_CACHE.clear()
    direct_calls = []
    repair_history = [
        {"attempt": attempt, "evaluation_feedback": {"failed": True}}
        for attempt in range(1, 4)
    ]
    monkeypatch.setattr(web_app, "max_repair_attempts", lambda task: 3)
    monkeypatch.setattr(
        web_app,
        "prompt_to_design_intent_with_feedback",
        lambda prompt, max_repairs: (
            {"base": {"id": "base"}, "features": []},
            None,
            repair_history,
            {"passed": False, "feedback": {"still_invalid": True}},
        ),
    )
    monkeypatch.setattr(
        web_app,
        "prompt_to_model_data_with_repair",
        lambda *args, **kwargs: direct_calls.append(True),
    )
    monkeypatch.setattr(
        web_app,
        "save_generation_log",
        lambda **kwargs: web_app.Path("generated/log.json"),
    )

    response = web_app.generate_cad(
        web_app.CADRequest(prompt="make a persistently invalid part")
    )

    assert response["status"] == "error"
    assert response["generation_path"] == "design_intent"
    assert response["intent_repair_history"] == repair_history
    assert direct_calls == []


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
        "prompt_to_design_intent_with_feedback",
        lambda prompt, max_repairs: (_ for _ in ()).throw(
            ValueError("intent lowering needs compatibility fallback")
        ),
    )

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


def test_refine_cad_reuses_saved_intent_and_returns_next_revision(monkeypatch):
    web_app.SUCCESS_RESPONSE_CACHE.clear()
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
        "features": [],
        "edge_treatments": [],
    }
    refined_intent = {
        **previous_intent,
        "required_concepts": ["plate", "boss"],
    }
    previous_model_data = {
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
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 80,
                "height": 50,
                "distance": 8,
            }
        ]
    }
    calls = {}

    def fake_refine(prompt, intent, correction, max_repairs, telemetry):
        calls["refine_count"] = calls.get("refine_count", 0) + 1
        calls["refine"] = (prompt, intent, correction, max_repairs)
        telemetry.update({"api_seconds": 0.4, "logical_api_calls": 1})
        return refined_intent, model_data, [], {"passed": True, "feedback": {}}

    def fake_export(generated_model_data, filename_hint):
        calls["filename_hint"] = filename_hint
        return {
            "status": "success",
            "model_data": generated_model_data,
            "quality_report": {"status": "pass"},
            "step_file": "generated/web/refined.step",
            "download_url": "/download/refined.step",
            "performance": {"export_model_total_seconds": 0.1},
        }

    monkeypatch.setattr(
        web_app,
        "refine_design_intent_with_feedback",
        fake_refine,
    )
    monkeypatch.setattr(
        web_app,
        "intent_to_model_data",
        lambda intent: previous_model_data,
    )
    monkeypatch.setattr(web_app, "export_model_data", fake_export)

    response = web_app.refine_cad(
        web_app.CADRefineRequest(
            original_prompt="Create a plate with a centered boss.",
            correction="Make the boss taller.",
            design_intent=previous_intent,
            revision=1,
        )
    )

    assert calls["refine"][0] == "Create a plate with a centered boss."
    assert calls["refine"][1] == previous_intent
    assert calls["refine"][2] == "Make the boss taller."
    assert calls["filename_hint"].startswith("revision-2")
    assert response["status"] == "success"
    assert response["design_intent"] == refined_intent
    assert response["generation_path"] == "design_intent_refinement"
    assert response["revision"] == 2
    assert response["refinement"] == {
        "from_revision": 1,
        "correction": "Make the boss taller.",
    }
    assert response["performance"]["logical_api_calls"] == 1
    assert response["revision_summary"] == {
        "has_operation_changes": True,
        "change_count": 1,
        "added_operations": [],
        "removed_operations": [],
        "changed_operations": ["base"],
        "operation_order_changed": False,
    }

    cached_response = web_app.refine_cad(
        web_app.CADRefineRequest(
            original_prompt="Create a plate with a centered boss.",
            correction="Make the boss taller.",
            design_intent=previous_intent,
            revision=1,
        )
    )

    assert calls["refine_count"] == 1
    assert cached_response["performance"]["cache_hit"] is True


def test_refine_cad_rejects_a_revision_with_no_cad_operation_changes(
    monkeypatch,
):
    web_app.SUCCESS_RESPONSE_CACHE.clear()
    previous_intent = {
        "required_concepts": ["plate"],
        "base": {
            "id": "base",
            "role": "plate",
            "profile": "rectangle",
            "width": 80,
            "height": 50,
            "thickness": 6,
        },
        "features": [],
        "edge_treatments": [],
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
        ]
    }
    export_calls = []

    monkeypatch.setattr(
        web_app,
        "refine_design_intent_with_feedback",
        lambda *args, **kwargs: (
            previous_intent,
            model_data,
            [],
            {"passed": True, "feedback": {}},
        ),
    )
    monkeypatch.setattr(
        web_app,
        "intent_to_model_data",
        lambda intent: model_data,
    )
    monkeypatch.setattr(
        web_app,
        "export_model_data",
        lambda *args: export_calls.append(args),
    )

    response = web_app.refine_cad(
        web_app.CADRefineRequest(
            original_prompt="Create a rectangular plate.",
            correction="Make it more robust.",
            design_intent=previous_intent,
            revision=1,
        )
    )

    assert response["status"] == "error"
    assert "did not change the generated CAD operations" in response["message"]
    assert response["revision_summary"]["has_operation_changes"] is False
    assert export_calls == []


def test_summarize_operation_changes_detects_feature_order_changes():
    base = {"type": "extrude", "id": "base"}
    first_feature = {"type": "add_extrude", "id": "feature_1"}
    second_feature = {"type": "cut", "id": "feature_2"}

    summary = web_app.summarize_operation_changes(
        {"operations": [base, first_feature, second_feature]},
        {"operations": [base, second_feature, first_feature]},
    )

    assert summary["has_operation_changes"] is True
    assert summary["change_count"] == 1
    assert summary["operation_order_changed"] is True


def test_refine_cad_keeps_the_last_valid_revision_when_refinement_fails(
    monkeypatch,
):
    web_app.SUCCESS_RESPONSE_CACHE.clear()
    previous_intent = {
        "required_concepts": ["plate"],
        "base": {
            "id": "base",
            "role": "plate",
            "profile": "rectangle",
            "width": 80,
            "height": 50,
            "thickness": 6,
        },
        "features": [],
        "edge_treatments": [],
    }

    monkeypatch.setattr(
        web_app,
        "refine_design_intent_with_feedback",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ValueError("Refinement could not preserve a connected solid")
        ),
    )

    response = web_app.refine_cad(
        web_app.CADRefineRequest(
            original_prompt="Create a plate.",
            correction="Add an unsupported feature.",
            design_intent=previous_intent,
            revision=2,
        )
    )

    assert response["status"] == "error"
    assert response["design_intent"] == previous_intent
    assert response["model_data"] is None
    assert response["revision"] == 2
    assert response["generation_path"] == "design_intent_refinement"


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
    assert response["performance"]["local_processing_seconds"] >= 0
    assert response["performance"]["build_reused"] is False


def editable_web_model_data():
    return {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "width": 80,
                "height": 50,
                "distance": 8,
            },
            {
                "type": "add_extrude",
                "id": "boss",
                "target": "base.top",
                "profile": "rectangle",
                "positions": [[0, 0]],
                "width": 20,
                "height": 12,
                "distance": 10,
            },
        ]
    }


def test_editable_model_route_returns_named_parameters_and_dependencies():
    response = web_app.editable_model(
        web_app.CADEditableModelRequest(model_data=editable_web_model_data())
    )

    assert response["status"] == "success"
    editable_model = response["editable_model"]
    assert editable_model["format"] == "prompt2cad.editable-model"
    assert editable_model["build_order"] == ["base", "boss"]
    assert editable_model["features"][1]["parent_feature_ids"] == ["base"]
    parameter_ids = {
        parameter["id"]
        for feature in editable_model["features"]
        for parameter in feature["parameters"]
    }
    assert "base.sketch.width" in parameter_ids
    assert "boss.feature.distance" in parameter_ids


def test_edit_parameters_route_exports_only_the_valid_rebuilt_revision(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(web_app, "GENERATED_DIR", tmp_path)
    monkeypatch.setattr(
        web_app.cq.exporters,
        "export",
        lambda part, path: web_app.Path(path).write_text(
            "STEP DATA",
            encoding="utf-8",
        ),
    )

    response = web_app.edit_parameters(
        web_app.CADParameterEditRequest(
            model_data=editable_web_model_data(),
            updates={
                "base.sketch.width": 100,
                "boss.feature.distance": 15,
            },
            filename_hint="wider plate",
        )
    )

    assert response["status"] == "success"
    assert response["model_data"]["operations"][0]["width"] == 100
    assert response["model_data"]["operations"][1]["distance"] == 15
    assert response["editable_model"]["build_order"] == ["base", "boss"]
    assert response["performance"]["build_reused"] is True
    assert response["performance"]["editable_rebuild_seconds"] >= 0
    assert (tmp_path / web_app.make_safe_filename("wider plate")).exists()


def test_edit_parameters_route_preserves_last_good_model_when_edit_fails(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(web_app, "GENERATED_DIR", tmp_path)
    model_data = editable_web_model_data()

    response = web_app.edit_parameters(
        web_app.CADParameterEditRequest(
            model_data=model_data,
            updates={"boss.placement.inst001.x": 100},
            filename_hint="disconnected boss",
        )
    )

    assert response["status"] == "error"
    assert response["edit_rejected"] is True
    assert response["model_data"] == model_data
    assert response["editable_model"]["source_model_data"] == model_data
    boss_parameters = response["editable_model"]["features"][1]["parameters"]
    original_x = next(
        parameter["value"]
        for parameter in boss_parameters
        if parameter["id"] == "boss.placement.inst001.x"
    )
    assert original_x == 0
    assert list(tmp_path.glob("*.step")) == []


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


def test_suggest_feature_returns_one_constrained_operation(monkeypatch):
    web_app.SUCCESS_RESPONSE_CACHE.clear()
    calls = {"api": 0}

    def fake_suggest_feature_model_data(**kwargs):
        calls["api"] += 1
        assert kwargs == {
            "operation_type": "add_extrude",
            "target": "base.top",
            "profile": "rectangle",
            "description": "reasonable boss",
        }
        return {
            "operations": [
                {
                    "type": "add_extrude",
                    "id": "suggested_feature",
                    "target": "base.top",
                    "profile": "rectangle",
                    "positions": [[0, 0]],
                    "width": 24,
                    "height": 16,
                    "distance": 6,
                }
            ]
        }

    monkeypatch.setattr(
        web_app,
        "suggest_feature_model_data",
        fake_suggest_feature_model_data,
    )

    request = web_app.CADSuggestFeatureRequest(
        operation_type="add_extrude",
        target="base.top",
        profile="rectangle",
        description="reasonable boss",
    )
    first_response = web_app.suggest_feature(request)
    second_response = web_app.suggest_feature(request)

    assert first_response["status"] == "success"
    assert first_response["model_data"]["operations"][0]["width"] == 24
    assert first_response["performance"]["cache_hit"] is False
    assert second_response["performance"]["cache_hit"] is True
    assert calls["api"] == 1
