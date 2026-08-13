"""Release-evidence checks for downloaded SolidWorks packages."""

import base64
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from prompt2cad.interpreter import build_model
from prompt2cad.solidworks_package import create_solidworks_package
from prompt2cad.solidworks_package_check import (
    extract_verified_solidworks_package,
)
from prompt2cad.solidworks_package_check import verify_solidworks_package
from prompt2cad.solidworks_package_check import verify_solidworks_package_result
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


def write_package_zip(tmp_path: Path) -> Path:
    package = create_solidworks_package(
        fixture_model_data(),
        "Downloaded release package",
    )
    archive_path = tmp_path / package.filename
    archive_path.write_bytes(package.content)
    return archive_path


def persistent_reference_records(plan) -> list[dict]:
    return [
        {
            "reference_id": reference["reference_id"],
            "entity_name": reference["entity_name"],
            "entity_type": reference["entity_type"],
            "persistent_id_base64": base64.b64encode(
                index.to_bytes(4, byteorder="little")
            ).decode("ascii"),
            "resolved": True,
            "resolution_error_code": 0,
        }
        for index, reference in enumerate(
            (
                reference
                for feature in plan.features
                for reference in feature.publish_references
            ),
            start=1,
        )
    ]


def test_downloaded_package_extracts_and_rebuilds_every_derived_artifact(
    tmp_path: Path,
):
    archive_path = write_package_zip(tmp_path)
    extracted = tmp_path / "verified-package"

    verified = extract_verified_solidworks_package(
        archive_path,
        extracted,
    )

    assert verified.root == extracted
    assert verified.summary()["verification_scope"] == "package"
    assert verified.summary()["feature_count"] == 2
    assert verify_solidworks_package(extracted).plan.to_dict() == (
        verified.plan.to_dict()
    )


def test_downloaded_package_result_proves_native_contract_and_geometry(
    tmp_path: Path,
    native_result_factory,
):
    archive_path = write_package_zip(tmp_path)
    extracted = tmp_path / "verified-package"
    verified = extract_verified_solidworks_package(archive_path, extracted)
    output_path = tmp_path / "downloaded-package.SLDPRT"
    output_path.write_bytes(b"synthetic native part for contract testing")
    result_path = Path(f"{output_path}.result.json")
    result = native_result_factory(
        verified.plan,
        output_path=str(output_path),
        geometry=geometry_metrics(build_model(verified.model_data)),
        published_references=persistent_reference_records(verified.plan),
    )
    result_path.write_text(json.dumps(result), encoding="utf-8")

    summary = verify_solidworks_package_result(extracted, result_path)

    assert summary["verification_scope"] == "package_and_native_result"
    assert summary["native_contract"]["verification_passed"] is True
    assert summary["persistent_references"]["passed"] is True
    assert summary["geometry_comparison"]["passed"] is True


def test_package_checker_rejects_payload_hash_mismatch(tmp_path: Path):
    archive_path = write_package_zip(tmp_path)
    extracted = tmp_path / "verified-package"
    extract_verified_solidworks_package(archive_path, extracted)
    (extracted / "source-model.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="payload (size|hash) mismatch"):
        verify_solidworks_package(extracted)


def test_package_checker_rebuilds_plan_instead_of_trusting_manifest_hashes(
    tmp_path: Path,
):
    archive_path = write_package_zip(tmp_path)
    extracted = tmp_path / "verified-package"
    extract_verified_solidworks_package(archive_path, extracted)
    plan_path = extracted / "solidworks-replay-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["source_build_order"] = list(reversed(plan["source_build_order"]))
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    manifest_path = extracted / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    content = plan_path.read_bytes()
    record = next(
        item
        for item in manifest["files"]
        if item["path"] == "solidworks-replay-plan.json"
    )
    record["size_bytes"] = len(content)
    record["sha256"] = sha256(content).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(RuntimeError, match="replay plan does not match"):
        verify_solidworks_package(extracted)


def test_package_checker_rejects_unsafe_archive_paths(tmp_path: Path):
    archive_path = tmp_path / "unsafe.zip"
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("../outside.txt", b"unsafe")

    with pytest.raises(RuntimeError, match="Unsafe ZIP entry path"):
        extract_verified_solidworks_package(
            archive_path,
            tmp_path / "unsafe-package",
        )
    assert not (tmp_path / "outside.txt").exists()


def test_package_result_must_point_to_its_own_nonempty_sldprt(
    tmp_path: Path,
    native_result_factory,
):
    archive_path = write_package_zip(tmp_path)
    extracted = tmp_path / "verified-package"
    verified = extract_verified_solidworks_package(archive_path, extracted)
    output_path = tmp_path / "empty.SLDPRT"
    output_path.touch()
    result_path = tmp_path / "unrelated.result.json"
    result = native_result_factory(
        verified.plan,
        output_path=str(output_path),
        geometry=geometry_metrics(build_model(verified.model_data)),
        published_references=persistent_reference_records(verified.plan),
    )
    result_path.write_text(json.dumps(result), encoding="utf-8")

    with pytest.raises(RuntimeError, match="missing or empty"):
        verify_solidworks_package_result(extracted, result_path)


def test_package_result_rejects_wrong_exact_parameter_identity(
    tmp_path: Path,
    native_result_factory,
):
    archive_path = write_package_zip(tmp_path)
    extracted = tmp_path / "verified-package"
    verified = extract_verified_solidworks_package(archive_path, extracted)
    output_path = tmp_path / "native.SLDPRT"
    output_path.write_bytes(b"synthetic native part")
    result_path = Path(f"{output_path}.result.json")
    result = native_result_factory(
        verified.plan,
        output_path=str(output_path),
        geometry=geometry_metrics(build_model(verified.model_data)),
        published_references=persistent_reference_records(verified.plan),
    )
    result["verified_parameter_ids"][0] = "wrong.parameter"
    result_path.write_text(json.dumps(result), encoding="utf-8")

    with pytest.raises(RuntimeError, match="parameter identities"):
        verify_solidworks_package_result(extracted, result_path)
