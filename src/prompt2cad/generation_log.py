"""Save prompt-generation repair logs for future evaluation/training data."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone
import json
from pathlib import Path
import re
from typing import Any


DEFAULT_GENERATION_LOG_DIR = Path("generated/repair_logs")


def save_generation_log(
    *,
    prompt: str,
    status: str,
    final_model_data: dict | None = None,
    repair_history: list[dict] | None = None,
    quality_report: dict | None = None,
    error_message: str | None = None,
    generation_mode: str = "prompt",
    log_dir: Path = DEFAULT_GENERATION_LOG_DIR,
) -> Path:
    """Save one generation attempt as JSON and return the log path."""
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc)
    log_data = {
        "timestamp_utc": timestamp.isoformat(),
        "generation_mode": generation_mode,
        "status": status,
        "prompt": prompt,
        "final_model_data": final_model_data,
        "quality_report": quality_report,
        "repair_history": repair_history or [],
        "error_message": error_message,
    }
    log_path = log_dir / make_generation_log_filename(prompt, timestamp)
    log_path.write_text(
        json.dumps(log_data, indent=2),
        encoding="utf-8",
    )
    return log_path


def make_generation_log_filename(prompt: str, timestamp: datetime) -> str:
    """Return a stable, filesystem-safe filename for a generation log."""
    timestamp_text = timestamp.strftime("%Y%m%d-%H%M%S")
    slug = prompt.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")[:48]
    if not slug:
        slug = "prompt"

    return f"{timestamp_text}-{slug}.json"
