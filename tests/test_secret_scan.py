"""Tests for the non-disclosing release credential scan."""

from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCANNER = PROJECT_ROOT / "scripts" / "check_secrets.py"


def test_secret_scan_accepts_placeholders_and_rejects_token_shapes(tmp_path: Path):
    (tmp_path / "safe.txt").write_text(
        'OPENAI_API_KEY="replace-with-your-key"\n',
        encoding="utf-8",
    )
    safe = subprocess.run(
        [sys.executable, str(SCANNER), "--root", str(tmp_path), "--all-files"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert safe.returncode == 0

    fake_token = "sk-" + "proj-" + "A" * 40
    (tmp_path / "unsafe.txt").write_text(fake_token, encoding="utf-8")
    unsafe = subprocess.run(
        [sys.executable, str(SCANNER), "--root", str(tmp_path), "--all-files"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert unsafe.returncode == 1
    assert "unsafe.txt:1" in unsafe.stdout
    assert fake_token not in unsafe.stdout


def test_repository_secret_scan_passes():
    result = subprocess.run(
        [sys.executable, str(SCANNER), "--root", str(PROJECT_ROOT)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
