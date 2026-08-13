"""Generate and audit the supported CAD feature-composition surface.

The operation schema permits an infinite number of feature sequences, so a
literal exhaustive search is impossible.  This module instead generates a
deterministic pairwise matrix across every profile family, operation family,
planar support direction, and native pattern family.  Each case must validate,
build as one CadQuery solid, lower to a native SOLIDWORKS replay plan, survive
a transactional parameter edit, and optionally round-trip through STEP.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
import time

import cadquery as cq

from prompt2cad.editable_model import build_editable_model_document
from prompt2cad.editable_model import rebuild_with_parameter_updates
from prompt2cad.exporter import export_step
from prompt2cad.schema import validate_model_data
from prompt2cad.solidworks_replay import export_solidworks_part
from prompt2cad.solidworks_replay import build_solidworks_replay_plan
from prompt2cad.solidworks_replay import verify_solidworks_editability
from prompt2cad.solidworks_replay import validate_solidworks_mutations
from prompt2cad.solidworks_editability import native_parameter_coverage
from prompt2cad.solidworks_verification import compare_geometry_metrics
from prompt2cad.solidworks_verification import geometry_metrics
from prompt2cad.solidworks_verification import validate_published_references


PROFILE_TYPES = ("rectangle", "circle", "polygon", "polyline", "sketch")
PLANAR_FACE_TARGETS = ("top", "bottom", "front", "back", "left", "right")
PATTERN_TYPES = ("mirror", "circular", "linear")


@dataclass(frozen=True)
class CapabilityCase:
    """One deterministic composition expected to work in both CAD paths."""

    name: str
    category: str
    facets: tuple[str, ...]
    model_data: dict
    mutations: dict[str, int | float | str]


def profile_fields(profile: str, half_size: float) -> dict:
    """Return a centered, convex profile that safely nests at ``half_size``."""
    if profile == "rectangle":
        return {"width": 2 * half_size, "height": 1.5 * half_size}
    if profile == "circle":
        return {"diameter": 1.6 * half_size}
    if profile == "polygon":
        return {"sides": 6, "diameter": 1.8 * half_size}
    if profile == "polyline":
        return {
            "points": [
                [-half_size, -0.65 * half_size],
                [half_size, -0.65 * half_size],
                [0.8 * half_size, 0.65 * half_size],
                [-0.8 * half_size, 0.65 * half_size],
            ]
        }
    if profile == "sketch":
        return {
            "start": [-half_size, -0.55 * half_size],
            "segments": [
                {"type": "line", "to": [half_size, -0.55 * half_size]},
                {
                    "type": "arc",
                    "through": [1.25 * half_size, 0],
                    "to": [half_size, 0.55 * half_size],
                },
                {"type": "line", "to": [-half_size, 0.55 * half_size]},
                {
                    "type": "arc",
                    "through": [-1.25 * half_size, 0],
                    "to": [-half_size, -0.55 * half_size],
                },
            ],
            "close": True,
        }
    raise ValueError(f"Unsupported audit profile '{profile}'")


def base_extrude(profile: str, *, distance: float = 12) -> dict:
    """Return one generously sized base extrusion."""
    return {
        "type": "extrude",
        "id": "base",
        "plane": "XY",
        "profile": profile,
        "distance": distance,
        **profile_fields(profile, 42),
    }


def base_revolve(profile: str, *, angle: float) -> dict:
    """Return a valid ring-sector revolve for any supported profile."""
    return {
        "type": "revolve",
        "id": "base",
        "plane": "XY",
        "profile": profile,
        "positions": [[12, 0]],
        "axis_start": [0, -1],
        "axis_end": [0, 1],
        "angle": angle,
        **profile_fields(profile, 3.5),
    }


def profile_feature(
    operation_type: str,
    feature_id: str,
    target: str,
    profile: str,
    *,
    half_size: float,
    position: tuple[float, float] = (0, 0),
) -> dict:
    """Return one additive or subtractive extrusion."""
    operation = {
        "type": operation_type,
        "id": feature_id,
        "target": target,
        "profile": profile,
        "positions": [[position[0], position[1]]],
        **profile_fields(profile, half_size),
    }
    if operation_type == "add_extrude":
        operation["distance"] = 7
    elif operation_type == "cut":
        operation["depth"] = 4
    else:
        raise ValueError(f"Unsupported profile feature '{operation_type}'")
    return operation


def pattern_spec(pattern_type: str) -> tuple[list[list[float]], dict]:
    """Return exact instance positions and matching canonical metadata."""
    if pattern_type == "mirror":
        positions = [[22, 15], [22, -15], [-22, 15], [-22, -15]]
        return positions, {
            "type": "mirror",
            "seed_position": [22, 15],
            "axes": ["x", "y"],
        }
    if pattern_type == "circular":
        radius = 28
        count = 6
        positions = [
            [
                round(radius * math.cos(2 * math.pi * index / count), 6),
                round(radius * math.sin(2 * math.pi * index / count), 6),
            ]
            for index in range(count)
        ]
        return positions, {
            "type": "circular",
            "seed_position": positions[0],
            "center": [0, 0],
            "count": count,
            "total_angle_degrees": 360,
        }
    if pattern_type == "linear":
        positions = [
            [-30, -20],
            [0, -20],
            [30, -20],
            [-30, 20],
            [0, 20],
            [30, 20],
        ]
        return positions, {
            "type": "linear",
            "seed_position": [-30, -20],
            "direction_1": [1, 0],
            "count_1": 3,
            "spacing_1": 30,
            "direction_2": [0, 1],
            "count_2": 2,
            "spacing_2": 40,
        }
    raise ValueError(f"Unsupported audit pattern '{pattern_type}'")


def side_pattern_spec(pattern_type: str) -> tuple[list[list[float]], dict]:
    """Return compact patterns that fit on a 100 by 24 mm side face."""
    if pattern_type == "mirror":
        positions = [[25, 5], [25, -5], [-25, 5], [-25, -5]]
        return positions, {
            "type": "mirror",
            "seed_position": positions[0],
            "axes": ["x", "y"],
        }
    if pattern_type == "circular":
        positions = [[7, 0], [0, 7], [-7, 0], [0, -7]]
        return positions, {
            "type": "circular",
            "seed_position": positions[0],
            "center": [0, 0],
            "count": 4,
            "total_angle_degrees": 360,
        }
    if pattern_type == "linear":
        positions = [
            [-25, -5],
            [0, -5],
            [25, -5],
            [-25, 5],
            [0, 5],
            [25, 5],
        ]
        return positions, {
            "type": "linear",
            "seed_position": positions[0],
            "direction_1": [1, 0],
            "count_1": 3,
            "spacing_1": 25,
            "direction_2": [0, 1],
            "count_2": 2,
            "spacing_2": 10,
        }
    raise ValueError(f"Unsupported side pattern '{pattern_type}'")


def shaft_base(*, angle: float = 360) -> dict:
    """Return a centered shaft whose axis follows local Y."""
    return {
        "type": "revolve",
        "id": "base",
        "plane": "XY",
        "profile": "rectangle",
        "positions": [[6, 0]],
        "axis_start": [0, -1],
        "axis_end": [0, 1],
        "angle": angle,
        "width": 12,
        "height": 80,
    }


def generated_capability_cases() -> tuple[CapabilityCase, ...]:
    """Return the deterministic positive support matrix."""
    cases: list[CapabilityCase] = []

    for profile in PROFILE_TYPES:
        cases.append(
            CapabilityCase(
                name=f"base_extrude__{profile}",
                category="base_profiles",
                facets=("extrude", profile, "XY"),
                model_data={"operations": [base_extrude(profile)]},
                mutations={"base.feature.distance": 14},
            )
        )
        for angle_name, angle in (("full", 360), ("partial", 240)):
            cases.append(
                CapabilityCase(
                    name=f"base_revolve_{angle_name}__{profile}",
                    category="base_profiles",
                    facets=("revolve", profile, angle_name),
                    model_data={"operations": [base_revolve(profile, angle=angle)]},
                    mutations={"base.feature.angle": angle - 20},
                )
            )

    for base_profile in PROFILE_TYPES:
        for operation_type in ("add_extrude", "cut"):
            for feature_profile in PROFILE_TYPES:
                feature = profile_feature(
                    operation_type,
                    "feature",
                    "base.top",
                    feature_profile,
                    half_size=7,
                )
                mutation_key = (
                    "feature.feature.distance"
                    if operation_type == "add_extrude"
                    else "feature.feature.depth"
                )
                mutation_value: int | float | str = (
                    9 if operation_type == "add_extrude" else 5
                )
                cases.append(
                    CapabilityCase(
                        name=(
                            f"top_{operation_type}__{base_profile}__"
                            f"{feature_profile}"
                        ),
                        category="top_profile_pairs",
                        facets=(
                            base_profile,
                            operation_type,
                            feature_profile,
                            "top",
                        ),
                        model_data={
                            "operations": [base_extrude(base_profile), feature]
                        },
                        mutations={mutation_key: mutation_value},
                    )
                )

    for boss_profile in PROFILE_TYPES:
        for cut_profile in PROFILE_TYPES:
            cases.append(
                CapabilityCase(
                    name=f"nested_boss_cut__{boss_profile}__{cut_profile}",
                    category="nested_profile_pairs",
                    facets=(
                        "add_extrude",
                        boss_profile,
                        "cut",
                        cut_profile,
                        "feature.top",
                    ),
                    model_data={
                        "operations": [
                            base_extrude("rectangle"),
                            profile_feature(
                                "add_extrude",
                                "boss",
                                "base.top",
                                boss_profile,
                                half_size=15,
                            ),
                            profile_feature(
                                "cut",
                                "pocket",
                                "boss.top",
                                cut_profile,
                                half_size=3.5,
                            ),
                        ]
                    },
                    mutations={"boss.feature.distance": 9},
                )
            )

    for face_name in PLANAR_FACE_TARGETS:
        for operation_type in ("add_extrude", "cut"):
            for profile in PROFILE_TYPES:
                cases.append(
                    CapabilityCase(
                        name=f"face_{face_name}__{operation_type}__{profile}",
                        category="planar_face_supports",
                        facets=(face_name, operation_type, profile),
                        model_data={
                            "operations": [
                                {
                                    "type": "extrude",
                                    "id": "base",
                                    "plane": "XY",
                                    "profile": "rectangle",
                                    "width": 100,
                                    "height": 80,
                                    "distance": 24,
                                },
                                profile_feature(
                                    operation_type,
                                    "face_feature",
                                    f"base.{face_name}",
                                    profile,
                                    half_size=5,
                                ),
                            ]
                        },
                        mutations={"base.feature.distance": 26},
                    )
                )

    for pattern_type in PATTERN_TYPES:
        positions, pattern = pattern_spec(pattern_type)
        for operation_type in ("add_extrude", "cut"):
            for profile in PROFILE_TYPES:
                operation = profile_feature(
                    operation_type,
                    "patterned_feature",
                    "base.top",
                    profile,
                    half_size=4,
                )
                operation["positions"] = positions
                operation["pattern"] = pattern
                cases.append(
                    CapabilityCase(
                        name=f"pattern_{pattern_type}__{operation_type}__{profile}",
                        category="patterns",
                        facets=(pattern_type, operation_type, profile),
                        model_data={
                            "operations": [
                                {
                                    "type": "extrude",
                                    "id": "base",
                                    "plane": "XY",
                                    "profile": "rectangle",
                                    "width": 120,
                                    "height": 100,
                                    "distance": 10,
                                },
                                operation,
                            ]
                        },
                        mutations={"base.feature.distance": 12},
                    )
                )

        countersink = {
            "type": "countersink",
            "id": "patterned_countersink",
            "target": "base.top",
            "positions": positions,
            "diameter": 4,
            "countersink_diameter": 8,
            "angle": 82,
            "depth": "through",
            "pattern": pattern,
        }
        cases.append(
            CapabilityCase(
                name=f"pattern_{pattern_type}__countersink",
                category="patterns",
                facets=(pattern_type, "countersink", "circle"),
                model_data={
                    "operations": [
                        {
                            "type": "extrude",
                            "id": "base",
                            "plane": "XY",
                            "profile": "rectangle",
                            "width": 120,
                            "height": 100,
                            "distance": 10,
                        },
                        countersink,
                    ]
                },
                mutations={
                    "patterned_countersink.feature.diameter": 5,
                    "patterned_countersink.placement.inst001.x": (
                        float(pattern["seed_position"][0])
                        - math.copysign(2.0, pattern["seed_position"][0])
                    ),
                },
            )
        )

    for operation_type in ("add_revolve", "cut_revolve"):
        for profile in PROFILE_TYPES:
            feature = {
                "type": operation_type,
                "id": "revolved_feature",
                "plane": "XY",
                "profile": profile,
                "positions": [[12, 0]],
                "axis_start": [0, -1],
                "axis_end": [0, 1],
                "angle": 360,
                **profile_fields(profile, 3),
            }
            cases.append(
                CapabilityCase(
                    name=f"revolved_feature__{operation_type}__{profile}",
                    category="revolved_features",
                    facets=(operation_type, profile, "full"),
                    model_data={
                        "operations": [
                            {
                                "type": "revolve",
                                "id": "base",
                                "plane": "XY",
                                "profile": "rectangle",
                                "positions": [[6, 0]],
                                "axis_start": [0, -1],
                                "axis_end": [0, 1],
                                "angle": 360,
                                "width": 12,
                                "height": 80,
                            },
                            feature,
                        ]
                    },
                    mutations={"revolved_feature.feature.angle": 300},
                )
            )

    for profile in PROFILE_TYPES:
        for operation_type, dimension_name, value in (
            ("chamfer", "distance", 1.0),
            ("fillet", "radius", 1.0),
        ):
            cases.append(
                CapabilityCase(
                    name=f"edge_{operation_type}__{profile}",
                    category="edge_treatments",
                    facets=(operation_type, profile, "top_outer_edges"),
                    model_data={
                        "operations": [
                            base_extrude(profile),
                            {
                                "type": operation_type,
                                "id": "edge_treatment",
                                "target": "base.top_outer_edges",
                                dimension_name: value,
                            },
                        ]
                    },
                    mutations={
                        f"edge_treatment.feature.{dimension_name}": 1.25
                    },
                )
            )

    # Real editing chains exercise reference survival across intermediate
    # features, rather than testing only one operation on a base body.
    for boss_profile in PROFILE_TYPES:
        for child_profile in PROFILE_TYPES:
            cases.append(
                CapabilityCase(
                    name=f"nested_boss_add__{boss_profile}__{child_profile}",
                    category="composition_chains",
                    facets=(
                        "add_extrude",
                        boss_profile,
                        "add_extrude",
                        child_profile,
                        "boss.top",
                    ),
                    model_data={
                        "operations": [
                            base_extrude("rectangle"),
                            profile_feature(
                                "add_extrude",
                                "boss",
                                "base.top",
                                boss_profile,
                                half_size=14,
                            ),
                            profile_feature(
                                "add_extrude",
                                "child",
                                "boss.top",
                                child_profile,
                                half_size=4,
                            ),
                        ]
                    },
                    mutations={"child.feature.distance": 9},
                )
            )

    for profile in PROFILE_TYPES:
        cases.append(
            CapabilityCase(
                name=f"cut_then_add__{profile}",
                category="composition_chains",
                facets=("cut", "add_extrude", profile, "reference_survival"),
                model_data={
                    "operations": [
                        base_extrude("rectangle"),
                        {
                            "type": "cut",
                            "id": "pocket",
                            "target": "base.top",
                            "profile": "circle",
                            "positions": [[-18, 0]],
                            "diameter": 12,
                            "depth": 4,
                        },
                        profile_feature(
                            "add_extrude",
                            "post_cut_feature",
                            "base.top",
                            profile,
                            half_size=5,
                            position=(18, 0),
                        ),
                    ]
                },
                mutations={"post_cut_feature.feature.distance": 9},
            )
        )

        cases.append(
            CapabilityCase(
                name=f"stacked_through_cut__{profile}",
                category="composition_chains",
                facets=("add_extrude", "add_extrude", "through", profile),
                model_data={
                    "operations": [
                        base_extrude("rectangle"),
                        {
                            "type": "add_extrude",
                            "id": "lower_boss",
                            "target": "base.top",
                            "profile": "rectangle",
                            "positions": [[0, 0]],
                            "width": 36,
                            "height": 28,
                            "distance": 6,
                        },
                        {
                            "type": "add_extrude",
                            "id": "upper_boss",
                            "target": "lower_boss.top",
                            "profile": "circle",
                            "positions": [[0, 0]],
                            "diameter": 18,
                            "distance": 5,
                        },
                        {
                            **profile_feature(
                                "cut",
                                "through_feature",
                                "upper_boss.top",
                                profile,
                                half_size=2.5,
                            ),
                            "depth": "through",
                        },
                    ]
                },
                mutations={"base.feature.distance": 14},
            )
        )

        cases.append(
            CapabilityCase(
                name=f"edge_then_add__{profile}",
                category="composition_chains",
                facets=("fillet", "add_extrude", profile, "reference_survival"),
                model_data={
                    "operations": [
                        base_extrude("rectangle"),
                        {
                            "type": "fillet",
                            "id": "base_fillet",
                            "target": "base.vertical_edges",
                            "radius": 3,
                        },
                        profile_feature(
                            "add_extrude",
                            "post_fillet_feature",
                            "base.top",
                            profile,
                            half_size=5,
                        ),
                    ]
                },
                mutations={"post_fillet_feature.feature.distance": 9},
            )
        )

        for treatment, dimension_name in (
            ("chamfer", "distance"),
            ("fillet", "radius"),
        ):
            cases.append(
                CapabilityCase(
                    name=f"child_edge_{treatment}__{profile}",
                    category="composition_chains",
                    facets=(
                        "add_extrude",
                        profile,
                        treatment,
                        "child.top_outer_edges",
                    ),
                    model_data={
                        "operations": [
                            base_extrude("rectangle"),
                            profile_feature(
                                "add_extrude",
                                "child",
                                "base.top",
                                profile,
                                half_size=12,
                            ),
                            {
                                "type": treatment,
                                "id": "child_edge_treatment",
                                "target": "child.top_outer_edges",
                                dimension_name: 1,
                            },
                        ]
                    },
                    mutations={
                        f"child_edge_treatment.feature.{dimension_name}": 1.25
                    },
                )
            )

    for pattern_type in PATTERN_TYPES:
        positions, pattern = pattern_spec(pattern_type)
        for profile in PROFILE_TYPES:
            patterned_feature = profile_feature(
                "add_extrude",
                "patterned",
                "base.top",
                profile,
                half_size=4,
            )
            patterned_feature["positions"] = positions
            patterned_feature["pattern"] = pattern
            cases.append(
                CapabilityCase(
                    name=f"pattern_child__{pattern_type}__{profile}",
                    category="composition_chains",
                    facets=(pattern_type, profile, "instance_child", "cut"),
                    model_data={
                        "operations": [
                            {
                                "type": "extrude",
                                "id": "base",
                                "plane": "XY",
                                "profile": "rectangle",
                                "width": 120,
                                "height": 100,
                                "distance": 10,
                            },
                            patterned_feature,
                            {
                                "type": "cut",
                                "id": "instance_hole",
                                "target": "patterned.inst002.top",
                                "profile": "circle",
                                "positions": [[0, 0]],
                                "diameter": 3,
                                "depth": "through",
                            },
                        ]
                    },
                    mutations={"patterned.feature.distance": 9},
                )
            )

        side_positions, side_pattern = side_pattern_spec(pattern_type)
        for operation_type in ("add_extrude", "cut"):
            side_feature = profile_feature(
                operation_type,
                "side_pattern",
                "base.front",
                "circle",
                half_size=2,
            )
            side_feature["positions"] = side_positions
            side_feature["pattern"] = side_pattern
            cases.append(
                CapabilityCase(
                    name=f"side_pattern__{pattern_type}__{operation_type}",
                    category="composition_chains",
                    facets=("front", pattern_type, operation_type, "circle"),
                    model_data={
                        "operations": [
                            {
                                "type": "extrude",
                                "id": "base",
                                "plane": "XY",
                                "profile": "rectangle",
                                "width": 100,
                                "height": 80,
                                "distance": 24,
                            },
                            side_feature,
                        ]
                    },
                    mutations={"base.sketch.width": 110},
                )
            )

            angled_feature = profile_feature(
                operation_type,
                "angled_pattern",
                "base.side_face.s002",
                "circle",
                half_size=2,
            )
            angled_feature["positions"] = side_positions
            angled_feature["pattern"] = side_pattern
            cases.append(
                CapabilityCase(
                    name=(
                        f"angled_pattern__{pattern_type}__{operation_type}"
                    ),
                    category="composition_chains",
                    facets=(
                        "angled_planar",
                        pattern_type,
                        operation_type,
                        "circle",
                    ),
                    model_data={
                        "operations": [
                            {
                                "type": "extrude",
                                "id": "base",
                                "plane": "XY",
                                "profile": "polyline",
                                "distance": 20,
                                "points": [
                                    [-40, -30],
                                    [40, -30],
                                    [25, 30],
                                    [-25, 30],
                                ],
                            },
                            angled_feature,
                        ]
                    },
                    mutations={"angled_pattern.sketch.diameter": 3.5},
                )
            )

    for operation_type in ("add_extrude", "cut"):
        for profile in PROFILE_TYPES:
            cases.append(
                CapabilityCase(
                    name=f"revolve_end_face__{operation_type}__{profile}",
                    category="composition_chains",
                    facets=("revolve", "front", operation_type, profile),
                    model_data={
                        "operations": [
                            shaft_base(),
                            profile_feature(
                                operation_type,
                                "end_feature",
                                "base.front",
                                profile,
                                half_size=3,
                            ),
                        ]
                    },
                    mutations={"base.sketch.height": 90},
                )
            )

    for treatment, dimension_name in (
        ("chamfer", "distance"),
        ("fillet", "radius"),
    ):
        cases.append(
            CapabilityCase(
                name=f"revolve_end_edge__{treatment}",
                category="composition_chains",
                facets=("revolve", "front_outer_edges", treatment),
                model_data={
                    "operations": [
                        shaft_base(),
                        {
                            "type": treatment,
                            "id": "end_treatment",
                            "target": "base.front_outer_edges",
                            dimension_name: 1,
                        },
                    ]
                },
                mutations={f"end_treatment.feature.{dimension_name}": 1.25},
            )
        )

    return tuple(cases)


def shape_metrics(part: cq.Workplane) -> dict:
    """Return exact-enough body metrics for STEP round-trip comparison."""
    solids = part.solids().vals()
    if len(solids) != 1:
        raise ValueError(f"Expected one solid, found {len(solids)}")
    solid = solids[0]
    box = solid.BoundingBox()
    return {
        "solid_count": 1,
        "volume_mm3": solid.Volume(),
        "bounding_box_mm": [
            box.xmin,
            box.ymin,
            box.zmin,
            box.xmax,
            box.ymax,
            box.zmax,
        ],
    }


def compare_shape_metrics(expected: dict, actual: dict) -> dict:
    """Reject material or extents lost by STEP serialization."""
    expected_volume = expected["volume_mm3"]
    actual_volume = actual["volume_mm3"]
    relative_volume_error = abs(actual_volume - expected_volume) / max(
        abs(expected_volume), 1.0
    )
    span_errors = []
    for start_index, end_index in ((0, 3), (1, 4), (2, 5)):
        expected_span = (
            expected["bounding_box_mm"][end_index]
            - expected["bounding_box_mm"][start_index]
        )
        actual_span = (
            actual["bounding_box_mm"][end_index]
            - actual["bounding_box_mm"][start_index]
        )
        span_errors.append(abs(actual_span - expected_span))
    if relative_volume_error > 1e-6 or max(span_errors) > 1e-5:
        raise ValueError(
            "STEP round-trip geometry changed "
            f"(volume error {relative_volume_error}, span errors {span_errors})"
        )
    return {
        "relative_volume_error": relative_volume_error,
        "span_errors_mm": span_errors,
    }


def audit_capability_case(
    case: CapabilityCase,
    *,
    step_directory: Path | None = None,
    native_directory: Path | None = None,
    verify_native_editability: bool = False,
    visible: bool = False,
    template_path: Path | None = None,
) -> dict:
    """Run every deterministic gate for one composition."""
    started = time.perf_counter()
    stage = "schema"
    try:
        validate_model_data(case.model_data)
        stage = "cadquery_build"
        part, document = build_editable_model_document(case.model_data)
        original_metrics = shape_metrics(part)

        stage = "solidworks_plan"
        plan = build_solidworks_replay_plan(document)
        if len(plan.features) != len(case.model_data["operations"]):
            raise ValueError("Native plan dropped one or more operations")
        parameter_coverage = native_parameter_coverage(
            case.model_data,
            plan,
            document=document,
        )

        stage = "solidworks_mutation_preflight"
        mutation_preflight = validate_solidworks_mutations(
            plan,
            case.mutations,
        )

        stage = "parameter_repair"
        edited_part, edited_document = rebuild_with_parameter_updates(
            document,
            case.mutations,
        )
        edited_metrics = shape_metrics(edited_part)
        edited_plan = build_solidworks_replay_plan(edited_document)

        step_result = None
        if step_directory is not None:
            stage = "step_export"
            step_path = export_step(part, step_directory / f"{case.name}.step")
            stage = "step_import"
            imported_part = cq.importers.importStep(str(step_path))
            imported_metrics = shape_metrics(imported_part)
            step_result = {
                "path": str(step_path),
                "comparison": compare_shape_metrics(
                    original_metrics,
                    imported_metrics,
                ),
            }

        native_result = None
        if native_directory is not None:
            native_path = native_directory / f"{case.name}.SLDPRT"
            native_result_path = native_directory / f"{case.name}.result.json"
            stage = "solidworks_native_replay"
            export_solidworks_part(
                plan,
                native_path,
                visible=visible,
                template_path=template_path,
                result_output_path=native_result_path,
            )
            replay_result = json.loads(
                native_result_path.read_text(encoding="utf-8")
            )
            reference_summary = validate_published_references(
                plan,
                replay_result,
                context=f"{case.name} native replay",
            )
            geometry_comparison = compare_geometry_metrics(
                geometry_metrics(part),
                replay_result.get("geometry", {}),
            )
            native_result = {
                "path": str(native_path),
                "result_path": str(native_result_path),
                "geometry_comparison": geometry_comparison,
                "published_references": reference_summary,
                "editability": None,
            }

            if verify_native_editability:
                mutated_path = native_directory / f"{case.name}.mutated.SLDPRT"
                edit_result_path = (
                    native_directory / f"{case.name}.edit-result.json"
                )
                stage = "solidworks_native_edit"
                verify_solidworks_editability(
                    plan,
                    native_path,
                    mutated_path,
                    case.mutations,
                    visible=visible,
                    result_output_path=edit_result_path,
                )
                edit_result = json.loads(
                    edit_result_path.read_text(encoding="utf-8")
                )
                if not edit_result.get("reopened"):
                    raise RuntimeError(
                        "Native edit verification did not reopen the saved part"
                    )
                if edit_result.get("mutation_count") != len(case.mutations):
                    raise RuntimeError(
                        "Native edit verification did not apply every mutation"
                    )
                edited_references = validate_published_references(
                    edited_plan,
                    edit_result,
                    context=f"{case.name} native edit",
                )
                edited_comparison = compare_geometry_metrics(
                    geometry_metrics(edited_part),
                    edit_result.get("after_geometry", {}),
                )
                native_result["editability"] = {
                    "path": str(mutated_path),
                    "result_path": str(edit_result_path),
                    "geometry_comparison": edited_comparison,
                    "published_references": edited_references,
                    "reopened": True,
                }

        return {
            "name": case.name,
            "category": case.category,
            "facets": list(case.facets),
            "status": "pass",
            "operation_count": len(case.model_data["operations"]),
            "native_feature_count": len(plan.features),
            "native_parameter_coverage": parameter_coverage,
            "original_geometry": original_metrics,
            "edited_geometry": edited_metrics,
            "mutations": case.mutations,
            "native_mutation_preflight": mutation_preflight,
            "step_round_trip": step_result,
            "solidworks_native": native_result,
            "elapsed_seconds": round(time.perf_counter() - started, 4),
        }
    except Exception as error:
        return {
            "name": case.name,
            "category": case.category,
            "facets": list(case.facets),
            "status": "fail",
            "failed_stage": stage,
            "error_type": type(error).__name__,
            "error": str(error),
            "elapsed_seconds": round(time.perf_counter() - started, 4),
        }


def run_capability_audit(
    *,
    output_root: Path | None = None,
    export_steps: bool = False,
    execute_native: bool = False,
    verify_native_editability: bool = False,
    visible: bool = False,
    template_path: Path | None = None,
    case_names: tuple[str, ...] | None = None,
    categories: tuple[str, ...] | None = None,
) -> dict:
    """Run the complete generated matrix and optionally persist STEP files."""
    cases = generated_capability_cases()
    if case_names:
        known_names = {case.name for case in cases}
        unknown_names = sorted(set(case_names) - known_names)
        if unknown_names:
            raise ValueError(
                "Unknown capability cases: " + ", ".join(unknown_names)
            )
        cases = tuple(case for case in cases if case.name in set(case_names))
    if categories:
        known_categories = {case.category for case in cases}
        unknown_categories = sorted(set(categories) - known_categories)
        if unknown_categories:
            raise ValueError(
                "Unknown capability categories: " + ", ".join(unknown_categories)
            )
        cases = tuple(case for case in cases if case.category in set(categories))

    if verify_native_editability:
        execute_native = True
    step_directory = None
    if export_steps:
        if output_root is None:
            raise ValueError("output_root is required when exporting STEP files")
        step_directory = output_root / "steps"
    native_directory = None
    if execute_native:
        if output_root is None:
            raise ValueError("output_root is required for native execution")
        native_directory = output_root / "native"

    results = [
        audit_capability_case(
            case,
            step_directory=step_directory,
            native_directory=native_directory,
            verify_native_editability=verify_native_editability,
            visible=visible,
            template_path=template_path,
        )
        for case in cases
    ]
    category_summary = {}
    for category in sorted({case.category for case in cases}):
        category_results = [
            result for result in results if result["category"] == category
        ]
        category_summary[category] = {
            "passed": sum(item["status"] == "pass" for item in category_results),
            "failed": sum(item["status"] == "fail" for item in category_results),
            "total": len(category_results),
        }
    successful_coverages = [
        result["native_parameter_coverage"]
        for result in results
        if result["status"] == "pass"
    ]
    numeric_source_count = sum(
        coverage["numeric_source_count"] for coverage in successful_coverages
    )
    bound_count = sum(
        coverage["bound_count"] for coverage in successful_coverages
    )
    relation_controlled_count = sum(
        coverage["relation_controlled_count"]
        for coverage in successful_coverages
    )
    derived_geometry_count = sum(
        coverage["derived_geometry_count"]
        for coverage in successful_coverages
    )
    restricted_parameter_count = sum(
        len(coverage["restricted_parameter_ids"])
        for coverage in successful_coverages
    )
    unsupported_parameter_count = sum(
        len(coverage["unsupported_parameter_ids"])
        for coverage in successful_coverages
    )
    controlled_count = bound_count + relation_controlled_count
    represented_count = controlled_count + derived_geometry_count
    return {
        "case_count": len(cases),
        "passed": sum(result["status"] == "pass" for result in results),
        "failed": sum(result["status"] == "fail" for result in results),
        "categories": category_summary,
        "native_parameter_coverage": {
            "numeric_source_count": numeric_source_count,
            "bound_count": bound_count,
            "coverage_ratio": (
                bound_count / numeric_source_count
                if numeric_source_count
                else 1.0
            ),
            "relation_controlled_count": relation_controlled_count,
            "controlled_count": controlled_count,
            "control_coverage_ratio": (
                controlled_count / numeric_source_count
                if numeric_source_count
                else 1.0
            ),
            "derived_geometry_count": derived_geometry_count,
            "represented_count": represented_count,
            "representation_coverage_ratio": (
                represented_count / numeric_source_count
                if numeric_source_count
                else 1.0
            ),
            "fully_bound_cases": sum(
                coverage["coverage_ratio"] == 1.0
                for coverage in successful_coverages
            ),
            "fully_controlled_cases": sum(
                coverage["control_coverage_ratio"] == 1.0
                for coverage in successful_coverages
            ),
            "fully_represented_cases": sum(
                coverage["representation_coverage_ratio"] == 1.0
                for coverage in successful_coverages
            ),
            "cases_with_derived_geometry": sum(
                bool(coverage["derived_geometry_parameter_ids"])
                for coverage in successful_coverages
            ),
            "restricted_parameter_count": restricted_parameter_count,
            "cases_with_restricted_parameters": sum(
                bool(coverage["restricted_parameter_ids"])
                for coverage in successful_coverages
            ),
            "unsupported_parameter_count": unsupported_parameter_count,
            "cases_with_unsupported_parameters": sum(
                bool(coverage["unsupported_parameter_ids"])
                for coverage in successful_coverages
            ),
            "cases_measured": len(successful_coverages),
        },
        "results": results,
    }


def main() -> None:
    """Run the reusable release capability audit."""
    parser = argparse.ArgumentParser(
        description="Audit pairwise STEP and SolidWorks feature compositions."
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("generated/capability-audit"),
    )
    parser.add_argument(
        "--export-steps",
        action="store_true",
        help="Export and re-import a STEP file for every generated case.",
    )
    parser.add_argument(
        "--execute-native",
        action="store_true",
        help="Replay each selected case into an installed SOLIDWORKS application.",
    )
    parser.add_argument(
        "--verify-native-editability",
        action="store_true",
        help=(
            "Reopen each native part, mutate its declared parameters, rebuild, "
            "save, and reopen it again. Implies --execute-native."
        ),
    )
    parser.add_argument(
        "--case",
        action="append",
        dest="case_names",
        help="Run one generated case by name; repeat to select several.",
    )
    parser.add_argument(
        "--category",
        action="append",
        dest="categories",
        help="Run one generated category; repeat to select several.",
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Show SOLIDWORKS while native cases run.",
    )
    parser.add_argument("--template", type=Path)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    report = run_capability_audit(
        output_root=args.output_root,
        export_steps=args.export_steps,
        execute_native=args.execute_native,
        verify_native_editability=args.verify_native_editability,
        visible=args.visible,
        template_path=args.template,
        case_names=tuple(args.case_names) if args.case_names else None,
        categories=tuple(args.categories) if args.categories else None,
    )
    report_path = args.output_root / "report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for category, summary in report["categories"].items():
        print(
            f"{category}: {summary['passed']}/{summary['total']} passed, "
            f"{summary['failed']} failed"
        )
    print(
        f"RESULTS pass={report['passed']} fail={report['failed']} "
        f"total={report['case_count']}"
    )
    print(f"WROTE {report_path}")
    if report["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
