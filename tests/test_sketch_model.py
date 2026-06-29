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
    assert sketch.entity("point_bottom_left").data["point"] == (-40, -25)
    assert sketch.entity("line_right").data == {
        "start": "point_bottom_right",
        "end": "point_top_right",
    }
    assert [dimension.id for dimension in sketch.dimensions] == [
        "width",
        "height",
    ]


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
    assert sketch.entity("point_center").data["point"] == (0, 0)
    assert sketch.entity("circle_outer").data == {
        "center": "point_center",
        "radius": 6,
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

    assert len(points) == 6
    assert len(lines) == 6
    assert sketch.entity("line_6").data == {
        "start": "point_6",
        "end": "point_1",
    }


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

    assert sketch.entity("point_1").data["point"] == (0, 0)
    assert sketch.entity("point_2").data["point"] == (20, 0)
    assert sketch.entity("point_3").data["point"] == (10, 15)
    assert sketch.entity("line_3").data == {
        "start": "point_3",
        "end": "point_1",
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
        "start": "point_2",
        "through": "point_4",
        "end": "point_3",
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
