"""Shared geometry and persistent-reference checks for native CAD replay."""

import math
from collections.abc import Collection

from prompt2cad.solidworks_replay import SolidWorksReplayPlan


def validate_native_build_result(
    plan: SolidWorksReplayPlan,
    native_result: dict,
    *,
    context: str,
) -> dict:
    """Require a complete, current native-build verification report."""
    _require_success_result(native_result, context=context)
    if native_result.get("verification_passed") is not True:
        raise RuntimeError(f"{context} did not pass saved-history verification")
    if native_result.get("reopened") is not True:
        raise RuntimeError(f"{context} did not reopen the saved native part")

    expected_features = [feature.feature_name for feature in plan.features]
    actual_features = native_result.get("native_features")
    if actual_features != expected_features:
        raise RuntimeError(
            f"{context} native feature order does not match the replay plan"
        )
    if native_result.get("feature_count") != len(expected_features):
        raise RuntimeError(f"{context} reported the wrong native feature count")

    summary = _validate_native_contract_counts(
        plan,
        native_result,
        context=context,
    )
    summary["verification_passed"] = True
    return summary


def validate_native_editability_result(
    plan: SolidWorksReplayPlan,
    native_result: dict,
    *,
    expected_mutation_ids: Collection[str],
    context: str,
) -> dict:
    """Require a complete save/reopen report after native parameter edits."""
    _require_success_result(native_result, context=context)
    if native_result.get("reopened") is not True:
        raise RuntimeError(f"{context} did not reopen the saved native part")
    expected_ids = sorted(expected_mutation_ids)
    if native_result.get("mutation_count") != len(expected_ids):
        raise RuntimeError(f"{context} did not apply every requested mutation")
    if native_result.get("mutated_parameter_ids") != expected_ids:
        raise RuntimeError(
            f"{context} mutated parameter identities do not match the request"
        )

    summary = _validate_native_contract_counts(
        plan,
        native_result,
        context=context,
    )
    summary.update(
        {
            "reopened": True,
            "mutation_count": len(expected_ids),
            "mutated_parameter_ids": expected_ids,
        }
    )
    return summary


def _require_success_result(native_result: dict, *, context: str) -> None:
    if not isinstance(native_result, dict):
        raise RuntimeError(f"{context} did not return a JSON object")
    if native_result.get("status") != "success":
        raise RuntimeError(f"{context} did not report success")


def _validate_native_contract_counts(
    plan: SolidWorksReplayPlan,
    native_result: dict,
    *,
    context: str,
) -> dict:
    expected_parameter_count = sum(
        len(feature.parameter_bindings) for feature in plan.features
    )
    expected_dimension_count = sum(
        binding.get("binding_kind") == "named_dimension"
        for feature in plan.features
        for binding in feature.parameter_bindings
    )
    expected_helper_names = _expected_native_helper_names(plan)

    _require_exact_count(
        native_result,
        "declared_parameter_count",
        expected_parameter_count,
        context=context,
    )
    _require_exact_count(
        native_result,
        "verified_parameter_count",
        expected_parameter_count,
        context=context,
    )
    expected_parameter_ids = [
        binding["parameter_id"]
        for feature in plan.features
        for binding in feature.parameter_bindings
    ]
    if native_result.get("verified_parameter_ids") != expected_parameter_ids:
        raise RuntimeError(
            f"{context} verified parameter identities do not match the replay plan"
        )
    if "verified_dimension_count" in native_result:
        _require_exact_count(
            native_result,
            "verified_dimension_count",
            expected_dimension_count,
            context=context,
        )
    _require_exact_count(
        native_result,
        "declared_helper_count",
        len(expected_helper_names),
        context=context,
    )
    _require_exact_count(
        native_result,
        "verified_helper_count",
        len(expected_helper_names),
        context=context,
    )
    if native_result.get("verified_helper_names") != list(expected_helper_names):
        raise RuntimeError(
            f"{context} verified helper identities do not match the replay plan"
        )
    _validate_native_health(plan, native_result.get("health"), context=context)
    return {
        "parameter_count": expected_parameter_count,
        "dimension_count": expected_dimension_count,
        "helper_count": len(expected_helper_names),
        "health_passed": True,
    }


def _require_exact_count(
    report: dict,
    field_name: str,
    expected: int,
    *,
    context: str,
) -> None:
    if report.get(field_name) != expected:
        raise RuntimeError(
            f"{context} reported {field_name}={report.get(field_name)!r}; "
            f"expected {expected}"
        )


def _expected_native_helper_names(plan: SolidWorksReplayPlan) -> tuple[str, ...]:
    names: list[str] = []
    for feature in plan.features:
        if feature.support.get("kind") == "offset_plane":
            names.append(feature.support["name"])
        pattern = feature.pattern
        if pattern is None:
            continue
        names.append(pattern["seed_feature_name"])
        if pattern["kind"] in {"circular_pattern", "linear_pattern"}:
            names.append(pattern["reference_sketch_name"])
        if pattern["kind"] == "circular_pattern":
            names.append(pattern["axis_name"])
        elif pattern["kind"] == "mirror_pattern":
            names.append(pattern["placement_sketch_name"])
    return tuple(names)


def _validate_native_health(
    plan: SolidWorksReplayPlan,
    health: object,
    *,
    context: str,
) -> None:
    if not isinstance(health, dict):
        raise RuntimeError(f"{context} did not report native feature health")
    if health.get("feature_error_count") != 0:
        raise RuntimeError(f"{context} reports native feature errors")

    expected_feature_names = [feature.feature_name for feature in plan.features]
    feature_records = health.get("features")
    if not isinstance(feature_records, list):
        raise RuntimeError(f"{context} did not report native feature records")
    actual_feature_names = [record.get("feature_name") for record in feature_records]
    if actual_feature_names != expected_feature_names:
        raise RuntimeError(f"{context} health report does not cover every feature")
    invalid_features = [
        record.get("feature_name")
        for record in feature_records
        if record.get("error_code") not in {0, None}
        and record.get("is_warning") is not True
    ]
    if invalid_features:
        raise RuntimeError(
            f"{context} has unhealthy native features: {invalid_features}"
        )

    expected_sketch_names = [
        feature.sketch_name for feature in plan.features if feature.sketch_name
    ]
    sketch_records = health.get("sketches")
    if not isinstance(sketch_records, list):
        raise RuntimeError(f"{context} did not report native sketch records")
    actual_sketch_names = [record.get("sketch_name") for record in sketch_records]
    if actual_sketch_names != expected_sketch_names:
        raise RuntimeError(f"{context} health report does not cover every sketch")
    invalid_sketches = [
        record.get("sketch_name")
        for record in sketch_records
        if record.get("is_valid") is not True
    ]
    if invalid_sketches:
        raise RuntimeError(
            f"{context} has invalid native sketches: {invalid_sketches}"
        )


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
