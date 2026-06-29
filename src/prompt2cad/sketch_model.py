"""Normalized sketch representation for editable CAD features.

The JSON operation format is convenient for generation, but editable CAD needs
a more explicit sketch model.  This module converts supported profiles into
named sketch entities that can later map to CAD-system sketches, dimensions,
constraints, and feature-tree rebuilds.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from math import cos, pi, sin


Point2D = tuple[float, float]


@dataclass(frozen=True)
class SketchEntity:
    """One entity inside a 2D sketch."""

    id: str
    type: str
    data: dict


@dataclass(frozen=True)
class SketchDimension:
    """A named dimension that controls sketch geometry."""

    id: str
    type: str
    value: float | int
    target: str


@dataclass(frozen=True)
class SketchDefinition:
    """A normalized, editable sketch attached to a feature operation."""

    profile: str
    plane: str | None = None
    target: str | None = None
    positions: list[Point2D] = field(default_factory=list)
    entities: list[SketchEntity] = field(default_factory=list)
    dimensions: list[SketchDimension] = field(default_factory=list)
    closed: bool = True
    source_operation: dict = field(default_factory=dict)

    def entity(self, entity_id: str) -> SketchEntity | None:
        """Return a sketch entity by id, if it exists."""
        for sketch_entity in self.entities:
            if sketch_entity.id == entity_id:
                return sketch_entity

        return None


def operation_to_sketch(operation: dict) -> SketchDefinition:
    """Convert a CAD operation profile into a normalized sketch definition."""
    profile = operation["profile"]
    positions = normalize_positions(operation)

    if profile == "rectangle":
        entities, dimensions = rectangle_to_entities(operation)
    elif profile == "circle":
        entities, dimensions = circle_to_entities(operation)
    elif profile == "polygon":
        entities, dimensions = polygon_to_entities(operation)
    elif profile == "polyline":
        entities, dimensions = polyline_to_entities(operation)
    elif profile == "sketch":
        entities, dimensions = sketch_segments_to_entities(operation)
    else:
        raise ValueError(f"Unsupported sketch profile: {profile}")

    return SketchDefinition(
        profile=profile,
        plane=operation.get("plane"),
        target=operation.get("target"),
        positions=positions,
        entities=entities,
        dimensions=dimensions,
        closed=operation.get("close", True),
        source_operation=deepcopy(operation),
    )


def normalize_positions(operation: dict) -> list[Point2D]:
    """Return feature placement positions in sketch-local coordinates."""
    positions = operation.get("positions", [[0, 0]])
    return [(position[0], position[1]) for position in positions]


def rectangle_to_entities(
    operation: dict,
) -> tuple[list[SketchEntity], list[SketchDimension]]:
    """Represent a rectangle as four named corner points and four lines."""
    width = operation["width"]
    height = operation["height"]
    half_width = width / 2
    half_height = height / 2
    corners = [
        ("bottom_left", (-half_width, -half_height)),
        ("bottom_right", (half_width, -half_height)),
        ("top_right", (half_width, half_height)),
        ("top_left", (-half_width, half_height)),
    ]

    entities = [
        SketchEntity(
            id=f"point_{corner_name}",
            type="point",
            data={"point": point},
        )
        for corner_name, point in corners
    ]
    entities.extend(
        [
            SketchEntity(
                id="line_bottom",
                type="line",
                data={
                    "start": "point_bottom_left",
                    "end": "point_bottom_right",
                },
            ),
            SketchEntity(
                id="line_right",
                type="line",
                data={
                    "start": "point_bottom_right",
                    "end": "point_top_right",
                },
            ),
            SketchEntity(
                id="line_top",
                type="line",
                data={
                    "start": "point_top_right",
                    "end": "point_top_left",
                },
            ),
            SketchEntity(
                id="line_left",
                type="line",
                data={
                    "start": "point_top_left",
                    "end": "point_bottom_left",
                },
            ),
        ]
    )
    dimensions = [
        SketchDimension(
            id="width",
            type="linear",
            value=width,
            target="line_bottom",
        ),
        SketchDimension(
            id="height",
            type="linear",
            value=height,
            target="line_right",
        ),
    ]
    return entities, dimensions


def circle_to_entities(
    operation: dict,
) -> tuple[list[SketchEntity], list[SketchDimension]]:
    """Represent a circle by center point and circular entity."""
    diameter = operation["diameter"]
    entities = [
        SketchEntity(
            id="point_center",
            type="point",
            data={"point": (0, 0)},
        ),
        SketchEntity(
            id="circle_outer",
            type="circle",
            data={
                "center": "point_center",
                "radius": diameter / 2,
            },
        ),
    ]
    dimensions = [
        SketchDimension(
            id="diameter",
            type="diameter",
            value=diameter,
            target="circle_outer",
        )
    ]
    return entities, dimensions


def polygon_to_entities(
    operation: dict,
) -> tuple[list[SketchEntity], list[SketchDimension]]:
    """Represent a regular polygon as generated points and edge lines."""
    sides = operation["sides"]
    diameter = operation["diameter"]
    radius = diameter / 2
    points = []

    for index in range(sides):
        angle = (2 * pi * index / sides) + (pi / 2)
        points.append((radius * cos(angle), radius * sin(angle)))

    entities = [
        SketchEntity(
            id=f"point_{index + 1}",
            type="point",
            data={"point": point},
        )
        for index, point in enumerate(points)
    ]
    entities.extend(make_line_loop_entities("line", len(points)))
    dimensions = [
        SketchDimension(
            id="diameter",
            type="diameter",
            value=diameter,
            target="construction_circumcircle",
        ),
        SketchDimension(
            id="sides",
            type="count",
            value=sides,
            target="polygon",
        ),
    ]
    return entities, dimensions


def polyline_to_entities(
    operation: dict,
) -> tuple[list[SketchEntity], list[SketchDimension]]:
    """Represent a closed polyline as points and connecting lines."""
    points = operation["points"]
    entities = [
        SketchEntity(
            id=f"point_{index + 1}",
            type="point",
            data={"point": (point[0], point[1])},
        )
        for index, point in enumerate(points)
    ]
    entities.extend(make_line_loop_entities("line", len(points)))
    return entities, []


def sketch_segments_to_entities(
    operation: dict,
) -> tuple[list[SketchEntity], list[SketchDimension]]:
    """Represent explicit sketch line/arc segments."""
    start = operation["start"]
    entities = [
        SketchEntity(
            id="point_1",
            type="point",
            data={"point": (start[0], start[1])},
        )
    ]
    current_point_id = "point_1"
    next_point_number = 2

    for index, segment in enumerate(operation["segments"], start=1):
        endpoint = segment["to"]
        endpoint_id = f"point_{next_point_number}"
        entities.append(
            SketchEntity(
                id=endpoint_id,
                type="point",
                data={"point": (endpoint[0], endpoint[1])},
            )
        )
        next_point_number += 1

        if segment["type"] == "line":
            entities.append(
                SketchEntity(
                    id=f"segment_{index}",
                    type="line",
                    data={
                        "start": current_point_id,
                        "end": endpoint_id,
                    },
                )
            )
        elif segment["type"] == "arc":
            through = segment["through"]
            through_point_id = f"point_{next_point_number}"
            entities.append(
                SketchEntity(
                    id=through_point_id,
                    type="point",
                    data={"point": (through[0], through[1])},
                )
            )
            next_point_number += 1
            entities.append(
                SketchEntity(
                    id=f"segment_{index}",
                    type="arc",
                    data={
                        "start": current_point_id,
                        "through": through_point_id,
                        "end": endpoint_id,
                    },
                )
            )
        else:
            raise ValueError(f"Unsupported sketch segment type: {segment['type']}")

        current_point_id = endpoint_id

    return entities, []


def make_line_loop_entities(prefix: str, point_count: int) -> list[SketchEntity]:
    """Create line entities connecting point_1 through point_n as a loop."""
    return [
        SketchEntity(
            id=f"{prefix}_{index + 1}",
            type="line",
            data={
                "start": f"point_{index + 1}",
                "end": f"point_{((index + 1) % point_count) + 1}",
            },
        )
        for index in range(point_count)
    ]
