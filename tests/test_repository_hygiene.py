"""Prevent secrets and generated CAD artifacts from entering source control."""

from pathlib import Path
import re
import subprocess

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_KEY_PATTERN = re.compile(
    rb"sk-(?:proj|org|svcacct)-[A-Za-z0-9_-]{20,}"
)


def tracked_paths() -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            check=True,
        )
    except FileNotFoundError:
        pytest.skip("Git is unavailable")
    return [
        PROJECT_ROOT / path.decode("utf-8")
        for path in result.stdout.split(b"\0")
        if path
    ]


def test_tracked_files_contain_no_openai_api_keys():
    matches = []
    for path in tracked_paths():
        if path.is_file() and API_KEY_PATTERN.search(path.read_bytes()):
            matches.append(str(path.relative_to(PROJECT_ROOT)))

    assert matches == [], f"Potential API key found in tracked files: {matches}"


def test_secrets_and_generated_cad_outputs_are_not_tracked():
    tracked = {
        path.relative_to(PROJECT_ROOT).as_posix() for path in tracked_paths()
    }
    forbidden = sorted(
        path
        for path in tracked
        if (path.startswith("generated/") and path != "generated/.gitkeep")
        or Path(path).suffix.lower() in {".env", ".step", ".sldprt"}
    )

    assert forbidden == []
