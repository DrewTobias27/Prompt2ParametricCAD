"""Shared pytest fixtures for native-CAD contract tests."""

from collections.abc import Callable

import pytest


@pytest.fixture
def native_result_factory() -> Callable[..., dict]:
    """Build a complete synthetic result matching one replay plan."""

    def factory(plan, *, editability: bool = False, **values) -> dict:
        mutated_parameter_ids = sorted(values.pop("mutated_parameter_ids", ()))
        parameter_bindings = [
            binding
            for feature in plan.features
            for binding in feature.parameter_bindings
        ]
        helper_names = []
        for feature in plan.features:
            if feature.support.get("kind") == "offset_plane":
                helper_names.append(feature.support["name"])
            pattern = feature.pattern
            if pattern is None:
                continue
            helper_names.append(pattern["seed_feature_name"])
            if pattern["kind"] in {"circular_pattern", "linear_pattern"}:
                helper_names.append(pattern["reference_sketch_name"])
            if pattern["kind"] == "circular_pattern":
                helper_names.append(pattern["axis_name"])
            elif pattern["kind"] == "mirror_pattern":
                helper_names.append(pattern["placement_sketch_name"])

        report = {
            "status": "success",
            "declared_parameter_count": len(parameter_bindings),
            "verified_parameter_count": len(parameter_bindings),
            "verified_parameter_ids": [
                binding["parameter_id"] for binding in parameter_bindings
            ],
            "declared_helper_count": len(helper_names),
            "verified_helper_count": len(helper_names),
            "verified_helper_names": helper_names,
            "health": {
                "features": [
                    {
                        "feature_name": feature.feature_name,
                        "error_code": 0,
                        "is_warning": False,
                        "status": "healthy",
                    }
                    for feature in plan.features
                ],
                "sketches": [
                    {
                        "sketch_name": feature.sketch_name,
                        "is_valid": True,
                    }
                    for feature in plan.features
                    if feature.sketch_name
                ],
                "feature_error_count": 0,
                "feature_warning_count": 0,
            },
        }
        if editability:
            report.update(
                {
                    "reopened": True,
                    "source_geometry_verification_passed": (
                        plan.expected_geometry is not None
                    ),
                    "edited_geometry_verification_passed": True,
                    "mutation_count": len(mutated_parameter_ids),
                    "mutated_parameter_ids": mutated_parameter_ids,
                }
            )
        else:
            report.update(
                {
                    "verification_passed": True,
                    "geometry_verification_passed": (
                        plan.expected_geometry is not None
                    ),
                    "reopened": True,
                    "feature_count": len(plan.features),
                    "native_features": [
                        feature.feature_name for feature in plan.features
                    ],
                    "verified_dimension_count": sum(
                        binding.get("binding_kind") == "named_dimension"
                        for binding in parameter_bindings
                    ),
                }
            )
        report.update(values)
        return report

    return factory
