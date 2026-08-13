"""Contract checks for the one-command deterministic release gate."""

from pathlib import Path
import os
import shutil
import subprocess

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RELEASE_SCRIPT = PROJECT_ROOT / "scripts" / "check_release.ps1"
NATIVE_RELEASE_SCRIPT = (
    PROJECT_ROOT / "scripts" / "check_solidworks_release.ps1"
)
SOLIDWORKS_PACKAGE_TESTS = PROJECT_ROOT / "tests" / "test_solidworks_package.py"


def powershell_path() -> str:
    executable = shutil.which("powershell.exe") or shutil.which("powershell")
    if executable is None:
        pytest.skip("Windows PowerShell is not available")
    return executable


def test_release_script_is_valid_powershell():
    result = subprocess.run(
        [
            powershell_path(),
            "-NoProfile",
            "-Command",
            (
                "$tokens=$null; $errors=$null; "
                "[System.Management.Automation.Language.Parser]::ParseFile("
                f"'{RELEASE_SCRIPT}', [ref]$tokens, [ref]$errors) | Out-Null; "
                "if ($errors.Count) { $errors | Out-String; exit 1 }"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_release_script_restores_shell_state_after_failure():
    environment = os.environ.copy()
    environment["P2P_RELEASE_SCRIPT"] = str(RELEASE_SCRIPT)
    result = subprocess.run(
        [
            powershell_path(),
            "-NoProfile",
            "-Command",
            (
                "$before=(Get-Location).Path; "
                "$env:PYTHONPATH='prompt2cad-release-sentinel'; "
                "$env:PROMPT2CAD_PYTHON='missing-prompt2cad-python.exe'; "
                "try { & $env:P2P_RELEASE_SCRIPT; exit 91 } catch {}; "
                "if ((Get-Location).Path -ne $before) { exit 92 }; "
                "if ($env:PYTHONPATH -ne 'prompt2cad-release-sentinel') "
                "{ exit 93 }; exit 0"
            ),
        ],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_native_release_script_is_valid_powershell():
    result = subprocess.run(
        [
            powershell_path(),
            "-NoProfile",
            "-Command",
            (
                "$tokens=$null; $errors=$null; "
                "[System.Management.Automation.Language.Parser]::ParseFile("
                f"'{NATIVE_RELEASE_SCRIPT}', [ref]$tokens, [ref]$errors) "
                "| Out-Null; if ($errors.Count) { $errors | Out-String; exit 1 }"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_release_script_keeps_native_execution_explicit():
    source = RELEASE_SCRIPT.read_text(encoding="utf-8")

    assert "-m pytest -q" in source
    assert "scripts\\check_secrets.py" in source
    assert "prompt2cad.release_matrix" in source
    assert "prompt2cad.capability_audit" in source
    assert "P2P_RUN_SOLIDWORKS_COMPILE" in source
    assert "-m pytest -m solidworks_compile -q" in source
    assert "test_setup_check_rejects_conflicting_canonical_revolve_axis" not in source
    assert "--export-steps" in source
    assert "PROMPT2CAD_NODE" in source
    assert "solidworks-package-smoke.mjs" in source
    assert "vite\\bin\\vite.js" in source
    assert "PROMPT2CAD_PNPM" not in source
    assert "--execute-native" not in source
    assert "OPENAI_API_KEY" not in source
    assert "$previousLocation = Get-Location" in source
    assert "$previousPythonPath = $env:PYTHONPATH" in source
    assert "Set-Location $previousLocation" in source
    assert "Remove-Item Env:PYTHONPATH" in source


def test_every_compile_gated_package_case_is_in_the_release_marker():
    source = SOLIDWORKS_PACKAGE_TESTS.read_text(encoding="utf-8")

    assert source.count("@pytest.mark.solidworks_compile") == source.count(
        'os.getenv("P2P_RUN_SOLIDWORKS_COMPILE")'
    )


def test_native_release_script_runs_every_focused_live_gate():
    source = NATIVE_RELEASE_SCRIPT.read_text(encoding="utf-8")

    assert "P2P_RUN_SOLIDWORKS_NATIVE" in source
    assert "test_extracted_package_builds_verified_native_part" in source
    assert "test_curved_side_attachment_matches_cadquery" in source
    assert "prompt2cad.solidworks_smoke" in source
    assert "--verify-editability" in source
    assert "prompt2cad.release_matrix" in source
    assert "--verify-native-editability" in source
    assert "solidworks-release-v{0}-{1}" in source
    assert "solidworks-release-v10-" not in source
    assert source.index("SOLIDWORKS_PACKAGE_VERSION") < source.index(
        "if (-not $OutputRoot)"
    )
    assert "Refusing to overwrite" in source
    assert "DownloadedPackagePath" in source
    assert "prompt2cad.solidworks_package_check extract" in source
    assert "prompt2cad.solidworks_package_check verify" in source
    assert "downloaded-package-native-verification.json" in source
    assert "prompt2cad.solidworks_package_check mutation" in source
    assert "prompt2cad.solidworks_package_check verify-edit" in source
    assert "--source $downloadedOutput" in source
    assert "downloaded-package-edit-verification.json" in source
    assert "-ExistingPartPath" in source
    assert "-MutationPath" in source
    assert "Start-Transcript" in source
    assert "Stop-Transcript" in source
    assert "prompt2cad.solidworks-release-evidence" in source
    assert "public_release_ready" in source
    assert "SOLIDWORKS_PACKAGE_VERSION" in source
    assert "package_version = $packageVersion" in source
    assert "native_gate_coverage.passed" in source
    assert "native_edit_coverage.passed" in source
    assert "native_smoke_coverage" in source
    assert "native_edit_coverage" in source
    assert "package_version = 8" not in source
    assert "source_zip_sha256" in source
    assert "release-summary.json" in source
    assert "OPENAI_API_KEY" not in source
