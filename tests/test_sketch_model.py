import pytest

from prompt2cad.sketch_model import operation_to_sketch


def test_rectangle_operation_becomes_editable_sketch_entities():
    sketch = operation_to_sketch(
        {
            "type": "extrude",
            "id": "base",
            "plane": "XY",
            "profile": "rectangle",
            "width": 80,
            "height": 50,
            "distance": 6,
        }
    )

    assert sketch.profile == "rectangle"
    assert sketch.plane == "XY"
    assert sketch.positions == [(0, 0)]
    assert len(sketch.entities) == 8
    assert sketch.entity("p001").data["point"] == (-40, -25)
    assert sketch.entity("bottom_left_corner").id == "p001"
    assert sketch.entity("l002").data == {
        "start": "p002",
        "end": "p003",
    }
    assert [dimension.id for dimension in sketch.dimensions] == [
        "d001",
        "d002",
    ]
    assert sketch.dimensions[0].aliases == ["width"]


def test_circle_operation_becomes_center_and_circle_entity():
    sketch = operation_to_sketch(
        {
            "type": "cut",
            "target": "base.top",
            "profile": "circle",
            "positions": [[10, 5]],
            "diameter": 12,
            "depth": "through",
        }
    )

    assert sketch.target == "base.top"
    assert sketch.positions == [(10, 5)]
    assert sketch.entity("p001").data["point"] == (0, 0)
    assert sketch.entity("center").id == "p001"
    assert sketch.entity("c001").data == {
        "center": "p001",
        "radius": 6,
        "construction": False,
    }
    assert sketch.dimensions[0].type == "diameter"


def test_polygon_operation_becomes_points_and_lines():
    sketch = operation_to_sketch(
        {
            "type": "extrude",
            "id": "base",
            "plane": "XY",
            "profile": "polygon",
            "sides": 6,
            "diameter": 30,
            "distance": 5,
        }
    )

    points = [
        entity for entity in sketch.entities
        if entity.type == "point"
    ]
    lines = [
        entity for entity in sketch.entities
        if entity.type == "line"
    ]

    assert len(points) == 7
    assert len(lines) == 6
    assert sketch.entity("l006").data == {
        "start": "p007",
        "end": "p002",
    }
    assert sketch.entity("center").id == "p001"
    assert sketch.entity("construction_circumcircle").id == "c001"


def test_polyline_operation_preserves_input_points():
    sketch = operation_to_sketch(
        {
            "type": "extrude",
            "id": "base",
            "plane": "XY",
            "profile": "polyline",
            "points": [[0, 0], [20, 0], [10, 15]],
            "distance": 5,
        }
    )

    assert sketch.entity("p001").data["point"] == (0, 0)
    assert sketch.entity("p002").data["point"] == (20, 0)
    assert sketch.entity("p003").data["point"] == (10, 15)
    assert sketch.entity("l003").data == {
        "start": "p003",
        "end": "p001",
    }


def test_explicit_sketch_operation_preserves_arc_entities():
    sketch = operation_to_sketch(
        {
            "type": "extrude",
            "id": "base",
            "plane": "XY",
            "profile": "sketch",
            "start": [0, 0],
            "segments": [
                {
                    "type": "line",
                    "to": [20, 0],
                },
                {
                    "type": "arc",
                    "through": [25, 10],
                    "to": [20, 20],
                },
                {
                    "type": "line",
                    "to": [0, 0],
                },
            ],
            "close": True,
            "distance": 5,
        }
    )

    arc = sketch.entity("segment_2")

    assert sketch.profile == "sketch"
    assert sketch.closed is True
    assert arc.type == "arc"
    assert arc.data == {
        "start": "p002",
        "through": "p004",
        "end": "p003",
    }


def test_unsupported_profile_raises_clear_error():
    with pytest.raises(ValueError, match="Unsupported sketch profile: spline"):
        operation_to_sketch(
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "spline",
            }
        )
