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
    assert graph.validation_warnings[0].message.startswith(
        "Target 'base.top' is not a registered feature reference"
    )


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


def test_feature_graph_rejects_target_before_parent_is_built():
    graph = FeatureGraph()

    with pytest.raises(
        ValueError,
        match="target parent feature 'missing' has not been built",
    ):
        graph.add_feature(
            {
                "type": "cut",
                "target": "missing.top",
                "profile": "circle",
                "diameter": 10,
                "depth": "through",
            },
            operation_number=1,
        )


def test_feature_graph_rejects_malformed_target():
    graph = FeatureGraph()

    with pytest.raises(
        ValueError,
        match="target 'base' must use the format 'feature.reference'",
    ):
        graph.add_feature(
            {
                "type": "cut",
                "target": "base",
                "profile": "circle",
                "diameter": 10,
                "depth": "through",
            },
            operation_number=1,
        )


def test_build_model_rejects_target_before_parent_feature_exists():
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
                "type": "cut",
                "target": "feature_99.top",
                "profile": "circle",
                "positions": [[0, 0]],
                "depth": "through",
                "diameter": 4,
            },
        ]
    }

    with pytest.raises(
        ValueError,
        match="target parent feature 'feature_99' has not been built",
    ):
        build_model_with_graph(model_data)


def test_feature_graph_records_multi_instance_references():
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
                "positions": [[-10, 0], [10, 0]],
                "distance": 5,
                "width": 8,
                "height": 8,
            },
        ]
    }

    _, graph = build_model_with_graph(model_data)

    created_references = graph.get_feature("feature_1").created_references
    assert "feature_1.inst001.face.f001" in created_references
    assert "feature_1.inst001.edge.e001" in created_references
    assert "feature_1.inst001.vertex.v001" in created_references
    assert "feature_1.inst002.face.f001" in created_references
    assert "feature_1.inst002.edge.e001" in created_references
    assert "feature_1.inst002.vertex.v001" in created_references
    assert len(created_references) == 52
    assert graph.registry.get_plane("feature_1.inst001.top") is not None
    assert graph.registry.get_plane("feature_1.inst002.top") is not None
    assert graph.registry.get_reference_group(
        "feature_1.inst001.top_outer_edges"
    ) is not None
    assert graph.validation_warnings == []


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
    assert "base.face.f001" in base.created_references
    assert "base.edge.e001" in base.created_references
    assert "base.vertex.v001" in base.created_references
    assert len(base.created_references) == 26
    assert "feature_1.face.f005" in boss.created_references
    assert "feature_1.edge.e001" in boss.created_references
    assert "feature_1.vertex.v001" in boss.created_references
    assert graph.registry.resolve_reference_name("base.top") == "base.face.f001"
    assert graph.registry.resolve_reference_group_name("base.top_outer_edges") == (
        "base.edge_group.top_outer_edges"
    )
    assert (
        graph.registry.resolve_reference_name("feature_1.right")
        == "feature_1.face.f005"
    )
    assert base.sketch.profile == "rectangle"
    assert base.sketch.entity("top_right_corner").data["point"] == (40, 25)
    assert boss.sketch.target == "base.top"
    assert boss.sketch.positions == [(20, 0)]
    assert cut.sketch.profile == "circle"
    assert cut.parent_feature_id == "feature_1"
    assert graph.children_of("feature_1") == [cut]
    assert graph.validation_warnings == []


def test_feature_graph_debug_tree_exports_build_history():
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
        ]
    }

    _, graph = build_model_with_graph(model_data)
    debug_tree = graph.to_debug_tree()

    assert debug_tree["build_order"] == ["base", "feature_1"]
    assert debug_tree["features"][0]["children"] == ["feature_1"]
    assert debug_tree["features"][1]["canonical_target"] == "base.face.f001"
    assert debug_tree["features"][0]["sketch"]["entities"][0]["id"] == "p001"
    assert debug_tree["registry"]["aliases"]["base.top"] == "base.face.f001"
