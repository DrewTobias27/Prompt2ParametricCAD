"""Tests for generating eval CAD model JSON files."""

import json

from prompt2cad import eval_generator


def test_generate_eval_models_saves_model_json(tmp_path, monkeypatch):
    cases_dir = tmp_path / "cases"
    output_dir = tmp_path / "generated"
    cases_dir.mkdir()

    case_path = cases_dir / "simple_plate.json"
    case_path.write_text(
        json.dumps(
            {
                "name": "simple_plate",
                "prompt": "Make a simple rectangular plate.",
                "expected": {},
            }
        ),
        encoding="utf-8",
    )

    def fake_prompt_to_model_data(prompt: str) -> dict:
        assert prompt == "Make a simple rectangular plate."
        return {
            "operations": [
                {
                    "type": "extrude",
                    "id": "base",
                    "plane": "XY",
                    "profile": "rectangle",
                    "width": 40,
                    "height": 20,
                    "distance": 5,
                }
            ]
        }

    monkeypatch.setattr(
        eval_generator,
        "prompt_to_model_data",
        fake_prompt_to_model_data,
    )

    generated_paths = eval_generator.generate_eval_models(
        cases_dir=cases_dir,
        output_dir=output_dir,
    )

    output_path = output_dir / "simple_plate.json"
    saved_model_data = json.loads(output_path.read_text(encoding="utf-8"))

    assert generated_paths == [output_path]
    assert saved_model_data["operations"][0]["profile"] == "rectangle"


def test_generate_eval_models_skips_existing_files(tmp_path, monkeypatch):
    cases_dir = tmp_path / "cases"
    output_dir = tmp_path / "generated"
    cases_dir.mkdir()
    output_dir.mkdir()

    (cases_dir / "simple_plate.json").write_text(
        json.dumps(
            {
                "name": "simple_plate",
                "prompt": "Make a simple rectangular plate.",
                "expected": {},
            }
        ),
        encoding="utf-8",
    )
    existing_output = output_dir / "simple_plate.json"
    existing_output.write_text('{"already": "there"}\n', encoding="utf-8")

    def fake_prompt_to_model_data(prompt: str) -> dict:
        raise AssertionError("API generator should not be called.")

    monkeypatch.setattr(
        eval_generator,
        "prompt_to_model_data",
        fake_prompt_to_model_data,
    )

    generated_paths = eval_generator.generate_eval_models(
        cases_dir=cases_dir,
        output_dir=output_dir,
    )

    assert generated_paths == []
    assert existing_output.read_text(encoding="utf-8") == '{"already": "there"}\n'
