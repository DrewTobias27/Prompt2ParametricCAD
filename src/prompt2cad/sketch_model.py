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
SUPPORTED_PROFILE_TYPES = {"rectangle", "circle", "polygon", "polyline", "sketch"}
SUPPORTED_SKETCH_ENTITY_TYPES = {
    "point",
    "line",
    "arc",
    "circle",
    "ellipse",
    "spline",
    "slot",
    "construction_line",
    "construction_axis",
}
PROFILE_ENTITY_SCAFFOLD = {
    "rectangle": {"point", "line"},
    "circle": {"point", "circle"},
    "polygon": {"point", "line", "circle"},
    "polyline": {"point", "line"},
    "sketch": {"point", "line", "arc"},
}
FUTURE_PROFILE_SCAFFOLD = {
    "ellipse": {"point", "ellipse"},
    "slot": {"point", "line", "arc"},
    "spline": {"point", "spline"},
}


@dataclass(frozen=True)
class SketchEntity:
    """One entity inside a 2D sketch."""

    id: str
    type: str
    data: dict
    aliases: list[str] = field(default_factory=list)

    def to_debug_dict(self) -> dict:
        """Return a JSON-friendly view of the entity."""
        return {
            "id": self.id,
            "type": self.type,
            "aliases": self.aliases,
            "data": self.data,
        }


@dataclass(frozen=True)
class SketchDimension:
    """A named dimension that controls sketch geometry."""

    id: str
    type: str
    value: float | int
    target: str
    aliases: list[str] = field(default_factory=list)

    def to_debug_dict(self) -> dict:
        """Return a JSON-friendly view of the dimension."""
        return {
            "id": self.id,
            "type": self.type,
            "value": self.value,
            "target": self.target,
            "aliases": self.aliases,
        }


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
        """Return a sketch entity by id or alias, if it exists."""
        for sketch_entity in self.entities:
            if entity_id == sketch_entity.id or entity_id in sketch_entity.aliases:
                return sketch_entity

        return None

    def to_debug_dict(self) -> dict:
        """Return a JSON-friendly sketch description."""
        return {
            "profile": self.profile,
            "plane": self.plane,
            "target": self.target,
            "positions": self.positions,
            "closed": self.closed,
            "entities": [
                sketch_entity.to_debug_dict()
                for sketch_entity in self.entities
            ],
            "dimensions": [
                dimension.to_debug_dict()
                for dimension in self.dimensions
            ],
        }


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


def numbered_id(prefix: str, index: int) -> str:
    """Return a stable structural entity id such as p001 or l002."""
    return f"{prefix}{index:03d}"


def point_entity(index: int, point: Point2D, aliases: list[str] | None = None) -> SketchEntity:
    """Create a structurally named point entity."""
    return SketchEntity(
        id=numbered_id("p", index),
        type="point",
        data={"point": point},
        aliases=aliases or [],
    )


def line_entity(
    index: int,
    start: str,
    end: str,
    aliases: list[str] | None = None,
) -> SketchEntity:
    """Create a structurally named line entity."""
    return SketchEntity(
        id=numbered_id("l", index),
        type="line",
        data={
            "start": start,
            "end": end,
        },
        aliases=aliases or [],
    )


def arc_entity(
    index: int,
    start: str,
    through: str,
    end: str,
    aliases: list[str] | None = None,
) -> SketchEntity:
    """Create a structurally named arc entity."""
    return SketchEntity(
        id=numbered_id("a", index),
        type="arc",
        data={
            "start": start,
            "through": through,
            "end": end,
        },
        aliases=aliases or [],
    )


def circle_entity(
    index: int,
    center: str,
    radius: float,
    aliases: list[str] | None = None,
    construction: bool = False,
) -> SketchEntity:
    """Create a structurally named circle entity."""
    return SketchEntity(
        id=numbered_id("c", index),
        type="circle",
        data={
            "center": center,
            "radius": radius,
            "construction": construction,
        },
        aliases=aliases or [],
    )


def dimension_entity(
    index: int,
    dimension_type: str,
    value: float | int,
    target: str,
    aliases: list[str] | None = None,
) -> SketchDimension:
    """Create a structurally named dimension."""
    return SketchDimension(
        id=numbered_id("d", index),
        type=dimension_type,
        value=value,
        target=target,
        aliases=aliases or [],
    )


def rectangle_to_entities(
    operation: dict,
) -> tuple[list[SketchEntity], list[SketchDimension]]:
    """Represent a rectangle as structural points and lines."""
    width = operation["width"]
    height = operation["height"]
    half_width = width / 2
    half_height = height / 2
    corners = [
        ((-half_width, -half_height), ["bottom_left_corner"]),
        ((half_width, -half_height), ["bottom_right_corner"]),
        ((half_width, half_height), ["top_right_corner"]),
        ((-half_width, half_height), ["top_left_corner"]),
    ]

    entities = [
        point_entity(
            index=index,
            point=point,
            aliases=aliases,
        )
        for index, (point, aliases) in enumerate(corners, start=1)
    ]
    entities.extend(
        [
            line_entity(
                index=1,
                start="p001",
                end="p002",
                aliases=["bottom_edge"],
            ),
            line_entity(
                index=2,
                start="p002",
                end="p003",
                aliases=["right_edge"],
            ),
            line_entity(
                index=3,
                start="p003",
                end="p004",
                aliases=["top_edge"],
            ),
            line_entity(
                index=4,
                start="p004",
                end="p001",
                aliases=["left_edge"],
            ),
        ]
    )
    dimensions = [
        dimension_entity(
            index=1,
            dimension_type="linear",
            value=width,
            target="l001",
            aliases=["width"],
        ),
        dimension_entity(
            index=2,
            dimension_type="linear",
            value=height,
            target="l002",
            aliases=["height"],
        ),
    ]
    return entities, dimensions


def circle_to_entities(
    operation: dict,
) -> tuple[list[SketchEntity], list[SketchDimension]]:
    """Represent a circle by center point and circular entity."""
    diameter = operation["diameter"]
    entities = [
        point_entity(
            index=1,
            point=(0, 0),
            aliases=["center"],
        ),
        circle_entity(
            index=1,
            center="p001",
            radius=diameter / 2,
            aliases=["outer_circle"],
        ),
    ]
    dimensions = [
        dimension_entity(
            index=1,
            dimension_type="diameter",
            value=diameter,
            target="c001",
            aliases=["diameter"],
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
        point_entity(
            index=1,
            point=(0, 0),
            aliases=["center"],
        ),
    ]
    entities.extend(
        [
        point_entity(
            index=index,
            point=point,
        )
        for index, point in enumerate(points, start=2)
        ]
    )
    polygon_point_ids = [
        numbered_id("p", index)
        for index in range(2, sides + 2)
    ]
    entities.extend(make_line_loop_entities(polygon_point_ids))
    entities.append(
        circle_entity(
            index=1,
            center="p001",
            radius=radius,
            aliases=["construction_circumcircle"],
            construction=True,
        )
    )
    dimensions = [
        dimension_entity(
            index=1,
            dimension_type="diameter",
            value=diameter,
            target="c001",
            aliases=["diameter"],
        ),
        dimension_entity(
            index=2,
            dimension_type="count",
            value=sides,
            target="polygon",
            aliases=["sides"],
        ),
    ]
    return entities, dimensions


def polyline_to_entities(
    operation: dict,
) -> tuple[list[SketchEntity], list[SketchDimension]]:
    """Represent a closed polyline as points and connecting lines."""
    points = operation["points"]
    entities = [
        point_entity(
            index=index,
            point=(point[0], point[1]),
        )
        for index, point in enumerate(points, start=1)
    ]
    entities.extend(
        make_line_loop_entities(
            [numbered_id("p", index) for index in range(1, len(points) + 1)]
        )
    )
    return entities, []


def sketch_segments_to_entities(
    operation: dict,
) -> tuple[list[SketchEntity], list[SketchDimension]]:
    """Represent explicit sketch line/arc segments."""
    start = operation["start"]
    entities = [
        point_entity(
            index=1,
            point=(start[0], start[1]),
            aliases=["start_point"],
        )
    ]
    current_point_id = "p001"
    next_point_number = 2
    line_count = 0
    arc_count = 0

    for index, segment in enumerate(operation["segments"], start=1):
        endpoint = segment["to"]
        endpoint_point = (endpoint[0], endpoint[1])

        if endpoint_point == (start[0], start[1]):
            endpoint_id = "p001"
        else:
            endpoint_id = numbered_id("p", next_point_number)
            entities.append(
                point_entity(
                    index=next_point_number,
                    point=endpoint_point,
                )
            )
            next_point_number += 1

        if segment["type"] == "line":
            line_count += 1
            entities.append(
                line_entity(
                    index=line_count,
                    start=current_point_id,
                    end=endpoint_id,
                    aliases=[f"segment_{index}"],
                )
            )
        elif segment["type"] == "arc":
            through = segment["through"]
            through_point_id = numbered_id("p", next_point_number)
            entities.append(
                point_entity(
                    index=next_point_number,
                    point=(through[0], through[1]),
                    aliases=[f"arc_{index}_through_point"],
                )
            )
            next_point_number += 1
            arc_count += 1
            entities.append(
                arc_entity(
                    index=arc_count,
                    start=current_point_id,
                    through=through_point_id,
                    end=endpoint_id,
                    aliases=[f"segment_{index}"],
                )
            )
        else:
            raise ValueError(f"Unsupported sketch segment type: {segment['type']}")

        current_point_id = endpoint_id

    return entities, []


def make_line_loop_entities(point_ids: list[str]) -> list[SketchEntity]:
    """Create line entities connecting point ids as a loop."""
    point_count = len(point_ids)
    return [
        line_entity(
            index=index + 1,
            start=point_ids[index],
            end=point_ids[(index + 1) % point_count],
        )
        for index in range(point_count)
    ]
