"""Tests for saved prompt-generation repair logs."""

import json

from prompt2cad.generation_log import save_generation_log


def test_save_generation_log_writes_training_ready_json(tmp_path):
    repair_history = [
        {
            "failure_analysis": {
                "passed": False,
                "failure_type": "quality_gate_failed",
            },
            "failed_model_data": {"operations": []},
            "repaired_model_data": {"operations": [{"type": "extrude"}]},
        }
    ]

    log_path = save_generation_log(
        prompt="Create a plate with four holes",
        status="success",
        final_model_data={"operations": [{"type": "extrude"}]},
        repair_history=repair_history,
        quality_report={"status": "pass"},
        log_dir=tmp_path,
    )

    log_data = json.loads(log_path.read_text(encoding="utf-8"))
    assert log_path.name.endswith("create-a-plate-with-four-holes.json")
    assert log_data["generation_mode"] == "prompt"
    assert log_data["status"] == "success"
    assert log_data["prompt"] == "Create a plate with four holes"
    assert log_data["quality_report"] == {"status": "pass"}
    assert log_data["repair_history"] == repair_history
