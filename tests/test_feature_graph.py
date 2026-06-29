import pytest

from prompt2cad.feature_graph import FeatureGraph
from prompt2cad.interpreter import build_model_with_graph


def test_feature_graph_tracks_build_order_and_children():
    graph = FeatureGraph()

    base = graph.add_feature(
        {
            "type": "extrude",
            "id": "base",
        },
        operation_number=1,
    )
    boss = graph.add_feature(
        {
            "type": "add_extrude",
            "id": "feature_1",
            "target": "base.top",
        },
        operation_number=2,
    )

    assert graph.build_order == ["base", "feature_1"]
    assert boss.parent_feature_id == "base"
    assert base.sketch is None
    assert graph.children_of("base") == [boss]
    assert graph.get_feature("base") == base


def test_feature_graph_rejects_duplicate_feature_ids():
    graph = FeatureGraph()

    graph.add_feature(
        {
            "type": "extrude",
            "id": "base",
        },
        operation_number=1,
    )

    with pytest.raises(ValueError, match="duplicate feature id 'base'"):
        graph.add_feature(
            {
                "type": "add_extrude",
                "id": "base",
                "target": "base.top",
            },
            operation_number=2,
        )


def test_build_model_with_graph_records_created_references():
    model_data = {
        "operations": [
            {
                "type": "extrude",
                "id": "base",
                "plane": "XY",
                "profile": "rectangle",
                "distance": 8,
                "width": 80,
                "height": 50,
            },
            {
                "type": "add_extrude",
                "id": "feature_1",
                "target": "base.top",
                "profile": "rectangle",
                "positions": [[20, 0]],
                "distance": 10,
                "width": 20,
                "height": 12,
            },
            {
                "type": "cut",
                "target": "feature_1.right",
                "profile": "circle",
                "positions": [[0, 0]],
                "depth": "through",
                "diameter": 4,
            },
        ]
    }

    part, graph = build_model_with_graph(model_data)
    base = graph.get_feature("base")
    boss = graph.get_feature("feature_1")
    cut = graph.get_feature("cut_3")

    assert len(part.solids().vals()) == 1
    assert base.created_references == [
        "base.back",
        "base.bottom",
        "base.front",
        "base.left",
        "base.right",
        "base.top",
    ]
    assert "feature_1.right" in boss.created_references
    assert base.sketch.profile == "rectangle"
    assert base.sketch.entity("point_top_right").data["point"] == (40, 25)
    assert boss.sketch.target == "base.top"
    assert boss.sketch.positions == [(20, 0)]
    assert cut.sketch.profile == "circle"
    assert cut.parent_feature_id == "feature_1"
    assert graph.children_of("feature_1") == [cut]
