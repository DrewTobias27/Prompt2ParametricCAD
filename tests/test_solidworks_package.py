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

from prompt2cad.editable_model import model_data_to_editable_document
from prompt2cad.interpreter import build_model
from prompt2cad.solidworks_package import create_solidworks_package
from prompt2cad.solidworks_package import SOLIDWORKS_PACKAGE_FORMAT
from prompt2cad.solidworks_package import SOLIDWORKS_PACKAGE_VERSION
from prompt2cad.solidworks_replay import build_solidworks_replay_plan
from prompt2cad.solidworks_verification import compare_geometry_metrics
from prompt2cad.solidworks_verification import geometry_metrics
from prompt2cad.solidworks_verification import validate_native_build_result
from prompt2cad.solidworks_verification import validate_published_references


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


def patterned_model_data() -> dict:
    return json.loads(
        (
            PROJECT_ROOT
            / "examples"
            / "models"
            / "solidworks_smoke_patterned_plate.json"
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
    assert "-v12-solidworks.zip" in package.filename
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
    expected_geometry = geometry_metrics(build_model(fixture_model_data()))
    assert replay_plan["expected_geometry"]["solid_body_count"] == (
        expected_geometry["solid_body_count"]
    )
    assert replay_plan["expected_geometry"]["volume_mm3"] == pytest.approx(
        expected_geometry["volume_mm3"]
    )
    assert replay_plan["expected_geometry"]["surface_area_mm2"] == pytest.approx(
        expected_geometry["surface_area_mm2"]
    )
    assert replay_plan["expected_geometry"]["center_of_mass_mm"] == pytest.approx(
        expected_geometry["center_of_mass_mm"]
    )
    assert replay_plan["expected_geometry"]["bounding_box_mm"] == pytest.approx(
        expected_geometry["bounding_box_mm"]
    )
    assert replay_plan["capabilities"]["native_geometry_oracle"] is True
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
    assert b"will not overwrite an existing SLDPRT or verification" in readme
    assert b"temporary staged file" in readme
    assert b"SLDPRT.replay.log" in readme
    assert b"Successful runs remove this diagnostic log" in readme
    assert b"P2P_SOLIDWORKS_ROOT" in readme
    assert b"interop version it selected" in readme
    assert b"solidworks-replay-plan.json" in launcher
    assert b"SolidWorks package version 12" in launcher
    assert b"Saved file reopened" in launcher
    assert b"CadQuery geometry matched" in launcher
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
    assert b"SolidWorks API root:" in launcher
    assert b"Interop version:" in launcher
    assert b"Refusing to overwrite existing SolidWorks part" in launcher
    assert b"Refusing to overwrite existing verification report" in launcher
    assert b"complete verified-build receipt" in launcher
    assert b"receipt identifies a different output part" in launcher
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


def write_mutation_document(
    plan_path: Path,
    mutation_path: Path,
    changes: dict[str, float | int],
) -> None:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    bindings = {
        binding["parameter_id"]: binding
        for feature in plan["features"]
        for binding in feature["parameter_bindings"]
    }
    mutation_path.write_text(
        json.dumps(
            {
                "format": "prompt2cad.solidworks-mutations",
                "version": 2,
                "expected_geometry": plan["expected_geometry"],
                "mutations": [
                    {
                        "parameter_id": parameter_id,
                        "value": value,
                        "unit": bindings[parameter_id]["unit"],
                    }
                    for parameter_id, value in changes.items()
                ],
            }
        ),
        encoding="utf-8",
    )


def complete_native_receipt(plan: dict, output_path: Path) -> dict:
    features = plan["features"]
    bindings = [
        binding
        for feature in features
        for binding in feature["parameter_bindings"]
    ]
    helper_names = []
    for feature in features:
        if feature["support"]["kind"] == "offset_plane":
            helper_names.append(feature["support"]["name"])
        pattern = feature.get("pattern")
        if pattern is None:
            continue
        helper_names.append(pattern["seed_feature_name"])
        if pattern["kind"] in {"circular_pattern", "linear_pattern"}:
            helper_names.append(pattern["reference_sketch_name"])
        if pattern["kind"] == "circular_pattern":
            helper_names.append(pattern["axis_name"])
        elif pattern["kind"] == "mirror_pattern":
            helper_names.append(pattern["placement_sketch_name"])
    references = [
        reference
        for feature in features
        for reference in feature["publish_references"]
    ]
    return {
        "status": "success",
        "output_path": str(output_path.resolve()),
        "output_sha256": sha256(b"P2PCAD").hexdigest(),
        "native_features": [feature["feature_name"] for feature in features],
        "feature_count": len(features),
        "verification_passed": True,
        "geometry_verification_passed": True,
        "reopened": True,
        "verified_dimension_count": sum(
            binding["binding_kind"] == "named_dimension"
            for binding in bindings
        ),
        "declared_parameter_count": len(bindings),
        "verified_parameter_count": len(bindings),
        "verified_parameter_ids": [
            binding["parameter_id"] for binding in bindings
        ],
        "declared_helper_count": len(helper_names),
        "verified_helper_count": len(helper_names),
        "verified_helper_names": helper_names,
        "health": {
            "feature_error_count": 0,
            "features": [
                {
                    "feature_name": feature["feature_name"],
                    "error_code": 0,
                    "is_warning": False,
                }
                for feature in features
            ],
            "sketches": [
                {
                    "sketch_name": feature["sketch_name"],
                    "is_valid": True,
                }
                for feature in features
                if feature.get("sketch_name")
            ],
        },
        "published_references": [
            {
                "reference_id": reference["reference_id"],
                "persistent_id_base64": f"persistent-{index}",
                "resolved": True,
                "resolution_error_code": 0,
            }
            for index, reference in enumerate(references, start=1)
        ],
    }


def install_fake_package_runner(root: Path, receipt: dict) -> None:
    receipt_json = json.dumps(receipt)
    (root / "solidworks_replay.ps1").write_text(
        "\n".join(
            [
                "param([string]$PlanPath, [string]$OutputPath)",
                "[System.IO.File]::WriteAllBytes(",
                "    $OutputPath,",
                "    [byte[]](80, 50, 80, 67, 65, 68)",
                ")",
                "@'",
                receipt_json,
                "'@",
                "",
            ]
        ),
        encoding="utf-8",
    )


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
    assert "SolidWorks package version 12" in result.stdout + result.stderr


@pytest.mark.skipif(
    os.getenv("P2P_RUN_SOLIDWORKS_COMPILE") != "1",
    reason="Set P2P_RUN_SOLIDWORKS_COMPILE=1 to use installed API registration",
)
@pytest.mark.solidworks_compile
@pytest.mark.parametrize(
    "model_data",
    [
        fixture_model_data(),
        patterned_model_data(),
        curved_side_attachment_model_data(),
    ],
    ids=["basic", "native-patterns", "virtual-face-supports"],
)
def test_launcher_accepts_only_a_complete_native_receipt(
    tmp_path: Path,
    model_data: dict,
):
    package = create_solidworks_package(model_data, "Receipt check")
    extract_package(package.content, tmp_path)
    plan = json.loads(
        (tmp_path / "solidworks-replay-plan.json").read_text(encoding="utf-8")
    )
    output_path = tmp_path / "receipt-check.SLDPRT"
    receipt = complete_native_receipt(plan, output_path)
    install_fake_package_runner(tmp_path, receipt)

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
            "-SkipIntegrityCheck",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert output_path.read_bytes() == b"P2PCAD"
    saved_receipt = json.loads(
        Path(f"{output_path}.result.json").read_text(encoding="utf-8-sig")
    )
    assert saved_receipt == receipt


@pytest.mark.skipif(
    os.getenv("P2P_RUN_SOLIDWORKS_COMPILE") != "1",
    reason="Set P2P_RUN_SOLIDWORKS_COMPILE=1 to use installed API registration",
)
@pytest.mark.solidworks_compile
def test_launcher_rejects_receipt_for_different_native_bytes(tmp_path: Path):
    package = create_solidworks_package(fixture_model_data(), "Hash failure")
    extract_package(package.content, tmp_path)
    plan = json.loads(
        (tmp_path / "solidworks-replay-plan.json").read_text(encoding="utf-8")
    )
    output_path = tmp_path / "hash-failure.SLDPRT"
    result_path = Path(f"{output_path}.result.json")
    receipt = complete_native_receipt(plan, output_path)
    receipt["output_sha256"] = "0" * 64
    install_fake_package_runner(tmp_path, receipt)

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
            "-SkipIntegrityCheck",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode != 0
    assert "output SHA-256 digest" in result.stdout + result.stderr
    assert not output_path.exists()
    assert not result_path.exists()


@pytest.mark.skipif(
    os.getenv("P2P_RUN_SOLIDWORKS_COMPILE") != "1",
    reason="Set P2P_RUN_SOLIDWORKS_COMPILE=1 to use installed API registration",
)
@pytest.mark.solidworks_compile
def test_launcher_removes_output_when_native_receipt_is_incomplete(
    tmp_path: Path,
):
    package = create_solidworks_package(fixture_model_data(), "Receipt failure")
    extract_package(package.content, tmp_path)
    plan = json.loads(
        (tmp_path / "solidworks-replay-plan.json").read_text(encoding="utf-8")
    )
    output_path = tmp_path / "receipt-failure.SLDPRT"
    result_path = Path(f"{output_path}.result.json")
    receipt = complete_native_receipt(plan, output_path)
    receipt["verified_parameter_ids"] = receipt[
        "verified_parameter_ids"
    ][:-1]
    install_fake_package_runner(tmp_path, receipt)

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
            "-SkipIntegrityCheck",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode != 0
    assert "Verified parameter identities count" in (
        result.stdout + result.stderr
    )
    assert not output_path.exists()
    assert not result_path.exists()


@pytest.mark.skipif(
    os.getenv("P2P_RUN_SOLIDWORKS_COMPILE") != "1",
    reason="Set P2P_RUN_SOLIDWORKS_COMPILE=1 to use installed API registration",
)
@pytest.mark.solidworks_compile
def test_launcher_preserves_an_existing_verification_report(tmp_path: Path):
    package = create_solidworks_package(fixture_model_data(), "Report collision")
    extract_package(package.content, tmp_path)
    plan = json.loads(
        (tmp_path / "solidworks-replay-plan.json").read_text(encoding="utf-8")
    )
    output_path = tmp_path / "report-collision.SLDPRT"
    result_path = Path(f"{output_path}.result.json")
    original_report = b'{"status":"existing-user-evidence"}'
    result_path.write_bytes(original_report)
    install_fake_package_runner(
        tmp_path,
        complete_native_receipt(plan, output_path),
    )

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
            "-SkipIntegrityCheck",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode != 0
    assert "Refusing to overwrite existing verification report" in (
        result.stdout + result.stderr
    )
    assert not output_path.exists()
    assert result_path.read_bytes() == original_report


@pytest.mark.skipif(
    os.getenv("P2P_RUN_SOLIDWORKS_COMPILE") != "1",
    reason="Set P2P_RUN_SOLIDWORKS_COMPILE=1 to compile against installed APIs",
)
@pytest.mark.solidworks_compile
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
    api_root_line = next(
        line
        for line in result.stdout.splitlines()
        if line.startswith("SolidWorks API root: ")
    )
    api_root = Path(api_root_line.removeprefix("SolidWorks API root: "))
    assert api_root.is_dir()
    interop_version_line = next(
        line
        for line in result.stdout.splitlines()
        if line.startswith("Interop version: ")
    )
    assert interop_version_line.removeprefix("Interop version: ").strip()


@pytest.mark.skipif(
    os.getenv("P2P_RUN_SOLIDWORKS_COMPILE") != "1",
    reason="Set P2P_RUN_SOLIDWORKS_COMPILE=1 to compile against installed APIs",
)
@pytest.mark.solidworks_compile
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
@pytest.mark.solidworks_compile
def test_setup_check_rejects_a_malformed_geometry_oracle(tmp_path: Path):
    package = create_solidworks_package(fixture_model_data(), "Oracle validation")
    extract_package(package.content, tmp_path)
    plan_path = tmp_path / "solidworks-replay-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["expected_geometry"]["volume_mm3"] = 0
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
    assert "Expected geometry volume must be positive" in (
        result.stdout + result.stderr
    )


@pytest.mark.skipif(
    os.getenv("P2P_RUN_SOLIDWORKS_COMPILE") != "1",
    reason="Set P2P_RUN_SOLIDWORKS_COMPILE=1 to compile against installed APIs",
)
@pytest.mark.solidworks_compile
def test_compile_only_geometry_probe_executes_native_comparator(tmp_path: Path):
    package = create_solidworks_package(fixture_model_data(), "Geometry probe")
    extract_package(package.content, tmp_path)
    plan_path = tmp_path / "solidworks-replay-plan.json"
    expected_geometry = json.loads(plan_path.read_text(encoding="utf-8"))[
        "expected_geometry"
    ]
    expected_path = tmp_path / "expected-geometry.json"
    actual_path = tmp_path / "actual-geometry.json"
    expected_path.write_text(json.dumps(expected_geometry), encoding="utf-8")
    actual_path.write_text(json.dumps(expected_geometry), encoding="utf-8")

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
            "-ExpectedGeometryPath",
            str(expected_path),
            "-ActualGeometryPath",
            str(actual_path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    output = json.loads(result.stdout.strip().splitlines()[-1])
    assert output["geometry_contract_validated"] is True


@pytest.mark.skipif(
    os.getenv("P2P_RUN_SOLIDWORKS_COMPILE") != "1",
    reason="Set P2P_RUN_SOLIDWORKS_COMPILE=1 to compile against installed APIs",
)
@pytest.mark.solidworks_compile
def test_compile_only_geometry_probe_rejects_volume_mismatch(tmp_path: Path):
    package = create_solidworks_package(fixture_model_data(), "Geometry mismatch")
    extract_package(package.content, tmp_path)
    plan_path = tmp_path / "solidworks-replay-plan.json"
    expected_geometry = json.loads(plan_path.read_text(encoding="utf-8"))[
        "expected_geometry"
    ]
    actual_geometry = dict(expected_geometry)
    actual_geometry["volume_mm3"] *= 1.02
    expected_path = tmp_path / "expected-geometry.json"
    actual_path = tmp_path / "actual-geometry.json"
    expected_path.write_text(json.dumps(expected_geometry), encoding="utf-8")
    actual_path.write_text(json.dumps(actual_geometry), encoding="utf-8")

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
            "-ExpectedGeometryPath",
            str(expected_path),
            "-ActualGeometryPath",
            str(actual_path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode != 0
    assert "volume differs from the CadQuery source" in (
        result.stdout + result.stderr
    )


@pytest.mark.skipif(
    os.getenv("P2P_RUN_SOLIDWORKS_COMPILE") != "1",
    reason="Set P2P_RUN_SOLIDWORKS_COMPILE=1 to compile against installed APIs",
)
@pytest.mark.solidworks_compile
def test_compile_only_mutation_probe_accepts_pattern_controls(tmp_path: Path):
    model_data = json.loads(
        (
            PROJECT_ROOT
            / "examples"
            / "models"
            / "solidworks_smoke_circular_pattern.json"
        ).read_text(encoding="utf-8")
    )
    package = create_solidworks_package(model_data, "Pattern mutation probe")
    extract_package(package.content, tmp_path)
    plan_path = tmp_path / "solidworks-replay-plan.json"
    mutation_path = tmp_path / "mutations.json"
    write_mutation_document(
        plan_path,
        mutation_path,
        {
            "radial_posts.pattern.count": 5,
            "radial_posts.pattern.total_angle": 300,
        },
    )

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
            "-MutationPath",
            str(mutation_path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    output = json.loads(result.stdout.strip().splitlines()[-1])
    assert output["mutation_contract_validated"] is True
    assert output["mutation_count"] == 2
    assert output["topology_changed"] is True
    assert output["topology_changing_parameter_ids"] == [
        "radial_posts.pattern.count"
    ]


@pytest.mark.skipif(
    os.getenv("P2P_RUN_SOLIDWORKS_COMPILE") != "1",
    reason="Set P2P_RUN_SOLIDWORKS_COMPILE=1 to compile against installed APIs",
)
@pytest.mark.solidworks_compile
def test_compile_only_mutation_probe_rejects_collapsed_linear_pattern(
    tmp_path: Path,
):
    model_data = json.loads(
        (
            PROJECT_ROOT
            / "examples"
            / "models"
            / "solidworks_smoke_linear_pattern.json"
        ).read_text(encoding="utf-8")
    )
    package = create_solidworks_package(model_data, "Invalid pattern mutation")
    extract_package(package.content, tmp_path)
    plan_path = tmp_path / "solidworks-replay-plan.json"
    mutation_path = tmp_path / "mutations.json"
    write_mutation_document(
        plan_path,
        mutation_path,
        {
            "mounting_pads.pattern.count_1": 1,
            "mounting_pads.pattern.count_2": 1,
        },
    )

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
            "-MutationPath",
            str(mutation_path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode != 0
    assert "must retain at least two instances" in result.stdout + result.stderr


@pytest.mark.skipif(
    os.getenv("P2P_RUN_SOLIDWORKS_COMPILE") != "1",
    reason="Set P2P_RUN_SOLIDWORKS_COMPILE=1 to compile against installed APIs",
)
@pytest.mark.solidworks_compile
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
    os.getenv("P2P_RUN_SOLIDWORKS_COMPILE") != "1",
    reason="Set P2P_RUN_SOLIDWORKS_COMPILE=1 to compile against installed APIs",
)
@pytest.mark.solidworks_compile
def test_setup_check_rejects_unknown_semantic_datum_plane(tmp_path: Path):
    package = create_solidworks_package(fixture_model_data(), "Datum validation")
    extract_package(package.content, tmp_path)
    plan_path = tmp_path / "solidworks-replay-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["features"][0]["support"]["semantic_plane"] = "localized-name"
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
    assert "requires semantic plane XY, XZ, or YZ" in (
        result.stdout + result.stderr
    )


@pytest.mark.skipif(
    os.getenv("P2P_RUN_SOLIDWORKS_NATIVE") != "1",
    reason="Set P2P_RUN_SOLIDWORKS_NATIVE=1 to open installed SolidWorks",
)
@pytest.mark.solidworks_native
def test_extracted_package_builds_verified_native_part(tmp_path: Path):
    model_data = fixture_model_data()
    expected_geometry = geometry_metrics(build_model(model_data))
    plan = build_solidworks_replay_plan(
        model_data_to_editable_document(model_data)
    )
    package = create_solidworks_package(model_data, "Native package")
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
    contract = validate_native_build_result(
        plan,
        report,
        context="downloaded package",
    )
    references = validate_published_references(
        plan,
        report,
        context="downloaded package",
    )
    comparison = compare_geometry_metrics(expected_geometry, report["geometry"])

    assert contract["verification_passed"] is True
    assert references["resolved_count"] == references["expected_count"]
    assert comparison["passed"] is True


@pytest.mark.skipif(
    os.getenv("P2P_RUN_SOLIDWORKS_NATIVE") != "1",
    reason="Set P2P_RUN_SOLIDWORKS_NATIVE=1 to open installed SolidWorks",
)
@pytest.mark.solidworks_native
def test_curved_side_attachment_matches_cadquery_in_native_solidworks(
    tmp_path: Path,
):
    model_data = curved_side_attachment_model_data()
    expected_geometry = geometry_metrics(build_model(model_data))
    plan = build_solidworks_replay_plan(
        model_data_to_editable_document(model_data)
    )
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
    contract = validate_native_build_result(
        plan,
        report,
        context="curved-side package",
    )
    references = validate_published_references(
        plan,
        report,
        context="curved-side package",
    )
    comparison = compare_geometry_metrics(expected_geometry, report["geometry"])

    assert contract["verification_passed"] is True
    assert references["resolved_count"] == references["expected_count"]
    assert comparison["passed"] is True
