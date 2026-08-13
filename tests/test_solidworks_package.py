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

from prompt2cad.interpreter import build_model
from prompt2cad.solidworks_package import create_solidworks_package
from prompt2cad.solidworks_package import SOLIDWORKS_PACKAGE_FORMAT
from prompt2cad.solidworks_package import SOLIDWORKS_PACKAGE_VERSION
from prompt2cad.solidworks_verification import compare_geometry_metrics
from prompt2cad.solidworks_verification import geometry_metrics


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


def curved_side_attachment_model_data() -> dict:
    return {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "sketch",
                "distance": 8,
                "start": [-50, -35],
                "segments": [
                    {"type": "line", "to": [15, -35]},
                    {"type": "arc", "through": [50, 0], "to": [15, 35]},
                    {"type": "line", "to": [-50, 35]},
                ],
                "close": True,
            },
            {
                "type": "add_extrude",
                "id": "left_tab",
                "target": "base.left",
                "profile": "rectangle",
                "positions": [[0, 0]],
                "distance": 10,
                "width": 18,
                "height": 8,
            },
            {
                "type": "add_extrude",
                "id": "right_tab",
                "target": "base.right",
                "profile": "rectangle",
                "positions": [[0, 0]],
                "distance": 10,
                "width": 18,
                "height": 8,
            },
            {
                "type": "cut",
                "id": "left_hole",
                "target": "left_tab.global_top",
                "profile": "circle",
                "positions": [[0, 0]],
                "depth": "through",
                "diameter": 6,
            },
            {
                "type": "cut",
                "id": "right_hole",
                "target": "right_tab.global_top",
                "profile": "circle",
                "positions": [[0, 0]],
                "depth": "through",
                "diameter": 6,
            },
        ]
    }


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
    assert "-v7-solidworks.zip" in package.filename
    assert set(files) == {
        "Build-SolidWorks-Part.cmd",
        "Build-SolidWorks-Part.ps1",
        "Check-SolidWorks-Setup.cmd",
        "README.txt",
        "editable-model.json",
        "editability-coverage.json",
        "manifest.json",
        "solidworks-replay-plan.json",
        "solidworks_replay.ps1",
        "solidworks_replay_runner.cs",
        "source-model.json",
    }

    manifest = json.loads(files["manifest.json"])
    replay_plan = json.loads(files["solidworks-replay-plan.json"])
    editable_model = json.loads(files["editable-model.json"])
    editability_coverage = json.loads(files["editability-coverage.json"])

    assert manifest == package.manifest
    assert manifest["format"] == SOLIDWORKS_PACKAGE_FORMAT
    assert manifest["version"] == SOLIDWORKS_PACKAGE_VERSION
    assert manifest["native_result"].endswith(".SLDPRT.result.json")
    assert manifest["replay_plan"]["build_order"] == ["base", "boss"]
    assert manifest["editability"]["numeric_parameter_count"] > 0
    assert manifest["editability"]["named_binding_count"] > 0
    assert manifest["editability"]["control_coverage_ratio"] <= 1
    assert manifest["editability"]["derived_geometry_count"] == (
        editability_coverage["derived_geometry_count"]
    )
    assert manifest["editability"]["derived_geometry_parameter_ids"] == (
        editability_coverage["derived_geometry_parameter_ids"]
    )
    assert manifest["editability"]["derived_geometry_parameters"] == (
        editability_coverage["derived_geometry_parameters"]
    )
    assert manifest["editability"]["represented_count"] == (
        editability_coverage["represented_count"]
    )
    assert manifest["editability"]["unsupported_parameter_ids"] == (
        editability_coverage["unsupported_parameter_ids"]
    )
    assert manifest["editability"]["unsupported_parameters"] == (
        editability_coverage["unsupported_parameters"]
    )
    assert manifest["editability"]["restricted_count"] == 0
    assert manifest["editability"]["restricted_parameter_ids"] == (
        editability_coverage["restricted_parameter_ids"]
    )
    assert manifest["editability"]["restricted_parameters"] == (
        editability_coverage["restricted_parameters"]
    )
    assert replay_plan["source_build_order"] == ["base", "boss"]
    assert editable_model["native_replay"]["exporter_implemented"] is True
    readme = files["README.txt"]
    launcher = files["Build-SolidWorks-Part.ps1"]
    command_launcher = files["Build-SolidWorks-Part.cmd"]
    check_launcher = files["Check-SolidWorks-Setup.cmd"]
    runner = files["solidworks_replay_runner.cs"]
    assert b"Build-SolidWorks-Part.cmd" in readme
    assert b"Editability summary" in readme
    assert b"retained as native reference geometry" in readme
    assert b"editability-coverage.json" in readme
    assert b"limited to their current origin side" in readme
    assert b"will not overwrite an existing SLDPRT" in readme
    assert b"temporary staged file" in readme
    assert b"solidworks-replay-plan.json" in launcher
    assert b"SolidWorks package version 7" in launcher
    assert b"Saved file reopened" in launcher
    assert b"Get-FileHash" in launcher
    assert b"Is64BitProcess" in launcher
    assert b"GetTypeFromProgID" in launcher
    assert b".result.json" in launcher
    assert b"verified_parameter_count" in launcher
    assert b"verified_helper_count" in launcher
    assert b"verified_parameter_ids" in runner
    assert b"verified_helper_names" in runner
    assert b"mutated_parameter_ids" in runner
    assert b"published_references" in launcher
    assert b"Build-SolidWorks-Part.ps1" in command_launcher
    assert b"-Visible" in command_launcher
    assert b"Build-SolidWorks-Part.ps1" in check_launcher
    assert b"-CheckOnly" in check_launcher
    assert b"CompileOnly" in launcher
    assert b"plan_validated" in launcher
    assert b"SolidWorks setup is ready" in launcher
    assert b"$LASTEXITCODE" not in files["Build-SolidWorks-Part.ps1"]

    replay_script = files["solidworks_replay.ps1"]
    assert b"[switch]$CompileOnly" in replay_script
    assert b"if ($CompileOnly.IsPresent)" in replay_script
    assert b'compile_only = $true' in replay_script


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


def test_launcher_rejects_an_incompatible_package_version(tmp_path: Path):
    package = create_solidworks_package(fixture_model_data(), "Version check")
    extract_package(package.content, tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["version"] = SOLIDWORKS_PACKAGE_VERSION - 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

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
    assert "SolidWorks package version 7" in result.stdout + result.stderr


@pytest.mark.skipif(
    os.getenv("P2P_RUN_SOLIDWORKS_COMPILE") != "1",
    reason="Set P2P_RUN_SOLIDWORKS_COMPILE=1 to compile against installed APIs",
)
def test_extracted_package_setup_check_compiles_runner(tmp_path: Path):
    package = create_solidworks_package(fixture_model_data(), "Setup check")
    extract_package(package.content, tmp_path)

    result = subprocess.run(
        [
            powershell_path(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(tmp_path / "Build-SolidWorks-Part.ps1"),
            "-CheckOnly",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "SolidWorks setup is ready" in result.stdout


@pytest.mark.skipif(
    os.getenv("P2P_RUN_SOLIDWORKS_COMPILE") != "1",
    reason="Set P2P_RUN_SOLIDWORKS_COMPILE=1 to compile against installed APIs",
)
def test_setup_check_rejects_conflicting_canonical_revolve_axis(tmp_path: Path):
    model_data = {
        "operations": [
            {
                "type": "revolve",
                "id": "shaft",
                "plane": "XY",
                "profile": "rectangle",
                "positions": [[5, 0]],
                "width": 10,
                "height": 40,
                "axis_start": [0, -1],
                "axis_end": [0, 1],
                "angle": 360,
            }
        ]
    }
    package = create_solidworks_package(model_data, "Axis validation")
    extract_package(package.content, tmp_path)
    plan_path = tmp_path / "solidworks-replay-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["features"][0]["feature"]["canonical_axis"]["direction"] = [1, 0]
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    result = subprocess.run(
        [
            powershell_path(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(tmp_path / "solidworks_replay.ps1"),
            "-PlanPath",
            str(plan_path),
            "-OutputPath",
            str(tmp_path / "unused.SLDPRT"),
            "-CompileOnly",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode != 0
    assert "Canonical axis direction X does not match" in (
        result.stdout + result.stderr
    )


@pytest.mark.skipif(
    os.getenv("P2P_RUN_SOLIDWORKS_COMPILE") != "1",
    reason="Set P2P_RUN_SOLIDWORKS_COMPILE=1 to compile against installed APIs",
)
def test_setup_check_rejects_duplicate_native_names(tmp_path: Path):
    package = create_solidworks_package(fixture_model_data(), "Name validation")
    extract_package(package.content, tmp_path)
    plan_path = tmp_path / "solidworks-replay-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["features"][1]["feature_name"] = plan["features"][0]["feature_name"]
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    result = subprocess.run(
        [
            powershell_path(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(tmp_path / "solidworks_replay.ps1"),
            "-PlanPath",
            str(plan_path),
            "-OutputPath",
            str(tmp_path / "unused.SLDPRT"),
            "-CompileOnly",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode != 0
    assert "duplicate native feature name" in (
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


@pytest.mark.skipif(
    os.getenv("P2P_RUN_SOLIDWORKS_NATIVE") != "1",
    reason="Set P2P_RUN_SOLIDWORKS_NATIVE=1 to open installed SolidWorks",
)
def test_curved_side_attachment_matches_cadquery_in_native_solidworks(
    tmp_path: Path,
):
    model_data = curved_side_attachment_model_data()
    expected_geometry = geometry_metrics(build_model(model_data))
    package = create_solidworks_package(
        model_data,
        "Curved side attachment",
    )
    extract_package(package.content, tmp_path)
    output_path = tmp_path / "curved-side-attachment.SLDPRT"

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
    assert report["feature_count"] == 5
    assert report["verified_parameter_count"] == report["declared_parameter_count"]
    assert report["health"]["feature_error_count"] == 0
    assert report["health"]["under_defined_sketch_count"] == 0
    comparison = compare_geometry_metrics(expected_geometry, report["geometry"])
    assert comparison["passed"] is True
