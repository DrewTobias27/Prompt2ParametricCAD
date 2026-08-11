"""Tests for portable SolidWorks replay packages."""

from io import BytesIO
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
from zipfile import ZipFile

import pytest

from prompt2cad.solidworks_package import create_solidworks_package
from prompt2cad.solidworks_package import SOLIDWORKS_PACKAGE_FORMAT
from prompt2cad.solidworks_package import SOLIDWORKS_PACKAGE_VERSION


PROJECT_ROOT = Path(__file__).parents[1]


def fixture_model_data() -> dict:
    return json.loads(
        (
            PROJECT_ROOT
            / "examples"
            / "models"
            / "circular_base_rectangular_boss.json"
        ).read_text(encoding="utf-8")
    )


def package_files(content: bytes) -> dict[str, bytes]:
    with ZipFile(BytesIO(content)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def test_package_contains_validated_native_replay_and_local_runner():
    package = create_solidworks_package(
        fixture_model_data(),
        "Circular base with rectangular boss",
    )
    files = package_files(package.content)

    assert package.filename.endswith("-solidworks.zip")
    assert set(files) == {
        "Build-SolidWorks-Part.cmd",
        "Build-SolidWorks-Part.ps1",
        "README.txt",
        "editable-model.json",
        "manifest.json",
        "solidworks-replay-plan.json",
        "solidworks_replay.ps1",
        "solidworks_replay_runner.cs",
        "source-model.json",
    }

    manifest = json.loads(files["manifest.json"])
    replay_plan = json.loads(files["solidworks-replay-plan.json"])
    editable_model = json.loads(files["editable-model.json"])

    assert manifest == package.manifest
    assert manifest["format"] == SOLIDWORKS_PACKAGE_FORMAT
    assert manifest["version"] == SOLIDWORKS_PACKAGE_VERSION
    assert manifest["native_result"].endswith(".SLDPRT.result.json")
    assert manifest["replay_plan"]["build_order"] == ["base", "boss"]
    assert replay_plan["source_build_order"] == ["base", "boss"]
    assert editable_model["native_replay"]["exporter_implemented"] is True
    readme = files["README.txt"]
    launcher = files["Build-SolidWorks-Part.ps1"]
    command_launcher = files["Build-SolidWorks-Part.cmd"]
    assert b"Build-SolidWorks-Part.cmd" in readme
    assert b"solidworks-replay-plan.json" in launcher
    assert b"Get-FileHash" in launcher
    assert b"Is64BitProcess" in launcher
    assert b"GetTypeFromProgID" in launcher
    assert b".result.json" in launcher
    assert b"verified_parameter_count" in launcher
    assert b"published_references" in launcher
    assert b"Build-SolidWorks-Part.ps1" in command_launcher
    assert b"-Visible" in command_launcher
    assert b"$LASTEXITCODE" not in files["Build-SolidWorks-Part.ps1"]


def test_package_is_deterministic_and_contains_no_prompt_or_credentials():
    model_data = fixture_model_data()
    first = create_solidworks_package(model_data, "Demo part")
    second = create_solidworks_package(model_data, "Demo part")

    assert first.filename == second.filename
    assert first.content == second.content
    for content in package_files(first.content).values():
        assert b"OPENAI_API_KEY" not in content
        assert b"sk-proj-" not in content


def test_package_manifest_checksums_cover_every_payload_file():
    package = create_solidworks_package(fixture_model_data(), "Checksum part")
    files = package_files(package.content)

    assert "manifest.json" not in {
        item["path"] for item in package.manifest["files"]
    }
    for item in package.manifest["files"]:
        assert len(files[item["path"]]) == item["size_bytes"]
        assert sha256(files[item["path"]]).hexdigest() == item["sha256"]


def powershell_path() -> str:
    executable = shutil.which("powershell.exe") or shutil.which("powershell")
    if executable is None:
        pytest.skip("Windows PowerShell is not available")
    return executable


def extract_package(content: bytes, destination: Path) -> None:
    with ZipFile(BytesIO(content)) as archive:
        archive.extractall(destination)


def test_generated_launcher_is_valid_powershell(tmp_path: Path):
    package = create_solidworks_package(fixture_model_data(), "Parser check")
    extract_package(package.content, tmp_path)
    launcher_path = tmp_path / "Build-SolidWorks-Part.ps1"
    environment = os.environ.copy()
    environment["P2P_LAUNCHER_TO_PARSE"] = str(launcher_path)

    result = subprocess.run(
        [
            powershell_path(),
            "-NoProfile",
            "-Command",
            (
                "$tokens=$null; $errors=$null; "
                "[System.Management.Automation.Language.Parser]::ParseFile("
                "$env:P2P_LAUNCHER_TO_PARSE, [ref]$tokens, [ref]$errors) "
                "| Out-Null; if ($errors.Count) { $errors | Out-String; exit 1 }"
            ),
        ],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_launcher_rejects_tampered_package_before_solidworks(tmp_path: Path):
    package = create_solidworks_package(fixture_model_data(), "Tamper check")
    extract_package(package.content, tmp_path)
    (tmp_path / "source-model.json").write_text("{}\n", encoding="utf-8")

    result = subprocess.run(
        [
            powershell_path(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(tmp_path / "Build-SolidWorks-Part.ps1"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Integrity check failed for source-model.json" in (
        result.stdout + result.stderr
    )


@pytest.mark.skipif(
    os.getenv("P2P_RUN_SOLIDWORKS_NATIVE") != "1",
    reason="Set P2P_RUN_SOLIDWORKS_NATIVE=1 to open installed SolidWorks",
)
def test_extracted_package_builds_verified_native_part(tmp_path: Path):
    package = create_solidworks_package(fixture_model_data(), "Native package")
    extract_package(package.content, tmp_path)
    output_path = tmp_path / "native-package.SLDPRT"

    result = subprocess.run(
        [
            powershell_path(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(tmp_path / "Build-SolidWorks-Part.ps1"),
            "-OutputPath",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert output_path.is_file()
    report_path = Path(f"{output_path}.result.json")
    assert report_path.is_file()
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    assert report["status"] == "success"
    assert report["feature_count"] == 2
    assert report["verified_parameter_count"] == report["declared_parameter_count"]
    assert report["health"]["feature_error_count"] == 0
    assert report["health"]["under_defined_sketch_count"] == 0
    assert report["published_references"]
    assert all(item["resolved"] for item in report["published_references"])
