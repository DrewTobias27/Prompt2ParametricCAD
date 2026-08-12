"""Canonical geometry for operation-level feature patterns.

Operation JSON stores exact positions for deterministic CadQuery execution and
also stores pattern metadata for editable native CAD replay.  This module is
the single source of truth that keeps those two representations synchronized.
"""

from __future__ import annotations

import math
from typing import Any


PATTERN_POSITION_TOLERANCE = 1e-5


def pattern_positions(pattern: dict[str, Any]) -> list[list[float]]:
    """Return exact instance positions implied by canonical pattern metadata."""
    pattern_type = pattern.get("type")
    if pattern_type == "circular":
        return _circular_positions(pattern)
    if pattern_type == "linear":
        return _linear_positions(pattern)
    if pattern_type == "mirror":
        return _mirror_positions(pattern)
    raise ValueError(f"Unsupported feature pattern type: {pattern_type!r}")


def synchronize_pattern_positions(model_data: dict[str, Any]) -> None:
    """Regenerate every patterned operation's exact execution positions."""
    for operation in model_data.get("operations", []):
        pattern = operation.get("pattern")
        if isinstance(pattern, dict):
            operation["positions"] = pattern_positions(pattern)


def validate_pattern_positions(model_data: dict[str, Any]) -> None:
    """Reject metadata that would make STEP and native CAD disagree."""
    for operation_index, operation in enumerate(
        model_data.get("operations", []), start=1
    ):
        pattern = operation.get("pattern")
        if not isinstance(pattern, dict):
            continue
        expected = pattern_positions(pattern)
        actual = operation.get("positions", [])
        feature_name = operation.get("id", f"operation {operation_index}")
        if len(actual) != len(expected):
            raise ValueError(
                f"Pattern position count must match metadata for feature "
                f"'{feature_name}': expected {len(expected)}, got {len(actual)}"
            )
        for position_index, (actual_point, expected_point) in enumerate(
            zip(actual, expected), start=1
        ):
            if not _points_close(actual_point, expected_point):
                raise ValueError(
                    f"Pattern positions do not match metadata for feature "
                    f"'{feature_name}' at instance {position_index}: "
                    f"expected {expected_point}, got {actual_point}"
                )


def _circular_positions(pattern: dict[str, Any]) -> list[list[float]]:
    seed = _point(pattern["seed_position"], "seed_position")
    center = _point(pattern["center"], "center")
    count = int(pattern["count"])
    total_angle = float(pattern["total_angle_degrees"])
    if count < 2:
        raise ValueError("Circular pattern count must be at least 2")
    if not 0 < total_angle <= 360:
        raise ValueError("Circular pattern total angle must be in (0, 360]")

    offset_x = seed[0] - center[0]
    offset_y = seed[1] - center[1]
    radius = math.hypot(offset_x, offset_y)
    if radius <= 1e-12:
        raise ValueError("Circular pattern seed cannot equal its center")
    start_angle = math.atan2(offset_y, offset_x)
    # A closed 360-degree pattern must not duplicate its seed. A partial
    # pattern includes both ends of the requested angular span.
    interval_count = count if math.isclose(total_angle, 360.0) else count - 1
    angle_step = math.radians(total_angle) / interval_count
    result = [
        _rounded_point(
            [
                center[0] + radius * math.cos(start_angle + index * angle_step),
                center[1] + radius * math.sin(start_angle + index * angle_step),
            ]
        )
        for index in range(count)
    ]
    result[0] = _rounded_point(seed)
    return result


def _linear_positions(pattern: dict[str, Any]) -> list[list[float]]:
    seed = _point(pattern["seed_position"], "seed_position")
    count_1 = int(pattern["count_1"])
    count_2 = int(pattern["count_2"])
    spacing_1 = float(pattern["spacing_1"])
    spacing_2 = float(pattern["spacing_2"])
    if count_1 < 1 or count_2 < 1:
        raise ValueError("Linear pattern counts must be at least 1")
    if spacing_1 < 0 or spacing_2 < 0:
        raise ValueError("Linear pattern spacing cannot be negative")
    if count_1 > 1 and spacing_1 <= 0:
        raise ValueError("Repeated linear pattern direction 1 needs spacing")
    if count_2 > 1 and spacing_2 <= 0:
        raise ValueError("Repeated linear pattern direction 2 needs spacing")

    direction_1 = _normalized_direction(
        pattern["direction_1"], required=count_1 > 1, name="direction_1"
    )
    direction_2 = _normalized_direction(
        pattern["direction_2"], required=count_2 > 1, name="direction_2"
    )
    return [
        _rounded_point(
            [
                seed[0]
                + index_1 * spacing_1 * direction_1[0]
                + index_2 * spacing_2 * direction_2[0],
                seed[1]
                + index_1 * spacing_1 * direction_1[1]
                + index_2 * spacing_2 * direction_2[1],
            ]
        )
        for index_2 in range(count_2)
        for index_1 in range(count_1)
    ]


def _mirror_positions(pattern: dict[str, Any]) -> list[list[float]]:
    seed = _point(pattern["seed_position"], "seed_position")
    axes = set(pattern["axes"])
    x_values = [seed[0], -seed[0]] if "y" in axes else [seed[0]]
    y_values = [seed[1], -seed[1]] if "x" in axes else [seed[1]]
    result: list[list[float]] = []
    for x_value in x_values:
        for y_value in y_values:
            point = _rounded_point([x_value, y_value])
            if not any(_points_close(point, existing) for existing in result):
                result.append(point)
    if len(result) < 2:
        raise ValueError("Mirror pattern must create at least two positions")
    return result


def _normalized_direction(
    value: Any,
    *,
    required: bool,
    name: str,
) -> list[float]:
    direction = _point(value, name)
    magnitude = math.hypot(direction[0], direction[1])
    if magnitude <= 1e-12:
        if required:
            raise ValueError(f"Linear pattern {name} cannot be zero")
        return [0.0, 0.0]
    return [direction[0] / magnitude, direction[1] / magnitude]


def _point(value: Any, name: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"Pattern {name} must contain two coordinates")
    point = [float(value[0]), float(value[1])]
    if not all(math.isfinite(coordinate) for coordinate in point):
        raise ValueError(f"Pattern {name} coordinates must be finite")
    return point


def _rounded_point(point: list[float]) -> list[float]:
    result = [round(float(coordinate), 6) for coordinate in point]
    return [0.0 if abs(coordinate) < 5e-7 else coordinate for coordinate in result]


def _points_close(first: Any, second: Any) -> bool:
    return (
        isinstance(first, (list, tuple))
        and isinstance(second, (list, tuple))
        and len(first) == len(second) == 2
        and all(
            abs(float(left) - float(right)) <= PATTERN_POSITION_TOLERANCE
            for left, right in zip(first, second)
        )
    )
