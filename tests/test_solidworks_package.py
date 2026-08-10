"""Tests for portable SolidWorks replay packages."""

from io import BytesIO
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

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
    assert manifest["replay_plan"]["build_order"] == ["base", "boss"]
    assert replay_plan["source_build_order"] == ["base", "boss"]
    assert editable_model["native_replay"]["exporter_implemented"] is True
    assert b"Build-SolidWorks-Part.ps1" in files["README.txt"]
    assert b"solidworks-replay-plan.json" in files["Build-SolidWorks-Part.ps1"]
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
