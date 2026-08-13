"""Shared geometry and persistent-reference checks for native CAD replay."""

import math

from prompt2cad.solidworks_replay import SolidWorksReplayPlan


def validate_published_references(
    plan: SolidWorksReplayPlan,
    native_result: dict,
    *,
    context: str,
) -> dict:
    """Require every planned semantic entity to retain a resolvable PID."""
    expected_records = [
        reference
        for feature in plan.features
        for reference in feature.publish_references
    ]
    expected_ids = [reference["reference_id"] for reference in expected_records]
    expected = set(expected_ids)
    if len(expected) != len(expected_ids):
        raise RuntimeError(f"{context} replay plan repeats a reference ID")
    expected_by_id = {
        reference["reference_id"]: reference
        for reference in expected_records
    }
    records = native_result.get("published_references")
    if not isinstance(records, list):
        raise RuntimeError(f"{context} did not report persistent references")

    actual_ids = [record.get("reference_id") for record in records]
    actual = set(actual_ids)
    if len(actual) != len(actual_ids):
        raise RuntimeError(f"{context} repeats a native reference ID")
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise RuntimeError(
            f"{context} persistent-reference mismatch; "
            f"missing={missing}, unexpected={unexpected}"
        )
    metadata_mismatches = [
        reference_id
        for reference_id, expected_record in expected_by_id.items()
        for actual_record in records
        if actual_record.get("reference_id") == reference_id
        and (
            actual_record.get("entity_name") != expected_record["entity_name"]
            or actual_record.get("entity_type") != expected_record["entity_type"]
        )
    ]
    if metadata_mismatches:
        raise RuntimeError(
            f"{context} native reference metadata does not match the plan: "
            + ", ".join(metadata_mismatches)
        )
    invalid = [
        record.get("reference_id")
        for record in records
        if record.get("resolved") is not True
        or not record.get("persistent_id_base64")
        or record.get("resolution_error_code") != 0
    ]
    if invalid:
        raise RuntimeError(
            f"{context} has unresolved persistent references: "
            + ", ".join(str(reference_id) for reference_id in invalid)
        )
    persistent_ids = [record["persistent_id_base64"] for record in records]
    if len(set(persistent_ids)) != len(persistent_ids):
        raise RuntimeError(
            f"{context} maps multiple semantic references to one native entity"
        )
    return {
        "expected_count": len(expected),
        "resolved_count": len(records),
        "passed": True,
    }


def geometry_metrics(part) -> dict:
    """Measure the invariant geometry used to compare both CAD kernels."""
    solids = list(part.solids().vals())
    bounding_box = part.val().BoundingBox()
    volumes = [float(solid.Volume()) for solid in solids]
    total_volume = sum(volumes)
    if total_volume <= 0 or not math.isfinite(total_volume):
        raise RuntimeError("CAD geometry did not report a positive finite volume")
    centers = [solid.centerOfMass(solid) for solid in solids]
    center_of_mass = [
        sum(
            volume * float(getattr(center, axis))
            for volume, center in zip(volumes, centers)
        )
        / total_volume
        for axis in ("x", "y", "z")
    ]
    return {
        "solid_body_count": len(solids),
        "volume_mm3": total_volume,
        "surface_area_mm2": sum(float(solid.Area()) for solid in solids),
        "center_of_mass_mm": center_of_mass,
        "bounding_box_mm": [
            float(bounding_box.xmin),
            float(bounding_box.ymin),
            float(bounding_box.zmin),
            float(bounding_box.xmax),
            float(bounding_box.ymax),
            float(bounding_box.zmax),
        ],
    }


def compare_geometry_metrics(cadquery: dict, solidworks: dict) -> dict:
    """Reject material or envelope differences large enough to change a part."""
    if solidworks.get("solid_body_count") != cadquery["solid_body_count"]:
        raise RuntimeError(
            "SolidWorks body count does not match the CadQuery result"
        )

    expected_volume = float(cadquery["volume_mm3"])
    native_volume = float(solidworks.get("volume_mm3", 0.0))
    relative_volume_error = abs(native_volume - expected_volume) / max(
        expected_volume,
        1.0,
    )
    if relative_volume_error > 0.005:
        raise RuntimeError(
            "SolidWorks volume differs from CadQuery by "
            f"{relative_volume_error:.2%}"
        )

    expected_area = float(cadquery["surface_area_mm2"])
    native_area = _finite_scalar(
        solidworks.get("surface_area_mm2"),
        "SolidWorks surface area",
    )
    relative_area_error = abs(native_area - expected_area) / max(
        abs(expected_area),
        1.0,
    )
    if relative_area_error > 0.01:
        raise RuntimeError(
            "SolidWorks surface area differs from CadQuery by "
            f"{relative_area_error:.2%}"
        )

    expected_box = cadquery["bounding_box_mm"]
    native_box = solidworks.get("bounding_box_mm")
    if not isinstance(native_box, list) or len(native_box) != 6:
        raise RuntimeError("SolidWorks did not report a valid bounding box")
    native_box = _finite_vector(
        native_box,
        length=6,
        label="SolidWorks bounding box",
    )
    expected_spans = [
        expected_box[index + 3] - expected_box[index] for index in range(3)
    ]
    native_spans = [
        float(native_box[index + 3]) - float(native_box[index])
        for index in range(3)
    ]
    span_errors = [
        abs(native - expected)
        for native, expected in zip(native_spans, expected_spans)
    ]
    for error, expected in zip(span_errors, expected_spans):
        if error > max(0.5, abs(expected) * 0.01):
            raise RuntimeError(
                "SolidWorks bounding-box span does not match CadQuery"
            )
    bound_errors = [
        abs(native - float(expected))
        for native, expected in zip(native_box, expected_box)
    ]
    for index, error in enumerate(bound_errors):
        axis = index % 3
        if error > max(0.5, abs(expected_spans[axis]) * 0.01):
            raise RuntimeError(
                "SolidWorks bounding-box position does not match CadQuery"
            )

    expected_center = _finite_vector(
        cadquery["center_of_mass_mm"],
        length=3,
        label="CadQuery center of mass",
    )
    native_center = _finite_vector(
        solidworks.get("center_of_mass_mm"),
        length=3,
        label="SolidWorks center of mass",
    )
    center_errors = [
        abs(native - expected)
        for native, expected in zip(native_center, expected_center)
    ]
    for axis, error in enumerate(center_errors):
        if error > max(0.5, abs(expected_spans[axis]) * 0.01):
            raise RuntimeError(
                "SolidWorks center of mass does not match CadQuery"
            )
    return {
        "passed": True,
        "relative_volume_error": relative_volume_error,
        "relative_surface_area_error": relative_area_error,
        "span_errors_mm": span_errors,
        "bound_errors_mm": bound_errors,
        "center_of_mass_errors_mm": center_errors,
    }


def _finite_scalar(value, label: str) -> float:
    """Return one finite float from an external geometry report."""
    try:
        numeric = float(value)
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"{label} is not numeric") from error
    if not math.isfinite(numeric):
        raise RuntimeError(f"{label} is not finite")
    return numeric


def _finite_vector(value, *, length: int, label: str) -> list[float]:
    """Validate fixed-length numeric vectors from external CAD output."""
    if not isinstance(value, list) or len(value) != length:
        raise RuntimeError(f"{label} must contain {length} values")
    return [
        _finite_scalar(item, f"{label} value {index + 1}")
        for index, item in enumerate(value)
    ]
