"""Shared geometry and persistent-reference checks for native CAD replay."""

from prompt2cad.solidworks_replay import SolidWorksReplayPlan


def validate_published_references(
    plan: SolidWorksReplayPlan,
    native_result: dict,
    *,
    context: str,
) -> dict:
    """Require every planned semantic entity to retain a resolvable PID."""
    expected = {
        reference["reference_id"]
        for feature in plan.features
        for reference in feature.publish_references
    }
    records = native_result.get("published_references")
    if not isinstance(records, list):
        raise RuntimeError(f"{context} did not report persistent references")

    actual = {record.get("reference_id") for record in records}
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise RuntimeError(
            f"{context} persistent-reference mismatch; "
            f"missing={missing}, unexpected={unexpected}"
        )
    invalid = [
        record.get("reference_id")
        for record in records
        if record.get("resolved") is not True
        or not record.get("persistent_id_base64")
    ]
    if invalid:
        raise RuntimeError(
            f"{context} has unresolved persistent references: "
            + ", ".join(str(reference_id) for reference_id in invalid)
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
    return {
        "solid_body_count": len(solids),
        "volume_mm3": sum(float(solid.Volume()) for solid in solids),
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

    expected_box = cadquery["bounding_box_mm"]
    native_box = solidworks.get("bounding_box_mm")
    if not isinstance(native_box, list) or len(native_box) != 6:
        raise RuntimeError("SolidWorks did not report a valid bounding box")
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
    return {
        "passed": True,
        "relative_volume_error": relative_volume_error,
        "span_errors_mm": span_errors,
    }
