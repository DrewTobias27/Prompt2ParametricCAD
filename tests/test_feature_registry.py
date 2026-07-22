import cadquery as cq
import pytest

from prompt2cad.feature_registry import FeatureRegistry
from prompt2cad.feature_registry import ReferenceFrame


def test_register_rectangular_prism_right_face_frame():
    registry = FeatureRegistry()
    target_plane = cq.Plane.XY()

    registry.register_rectangular_prism_faces(
        feature_id="feature_1",
        target_plane=target_plane,
        width=20,
        height=12,
        distance=10,
        position=[20, 0],
    )

    right_plane = registry.get_plane("feature_1.face.f005")

    assert right_plane is not None
    assert right_plane.origin.toTuple() == (30.0, 0.0, 5.0)
    assert right_plane.xDir.toTuple() == (0.0, 1.0, 0.0)
    assert right_plane.zDir.toTuple() == (1.0, 0.0, 0.0)
    assert registry.resolve_reference_name("feature_1.right") == (
        "feature_1.face.f005"
    )
    assert registry.get_plane("feature_1.right").origin.toTuple() == (
        30.0,
        0.0,
        5.0,
    )
    assert registry.resolve_reference_name("feature_1.top_front_edge") == (
        "feature_1.edge.e001"
    )
    assert registry.resolve_reference_group_name("feature_1.top_outer_edges") == (
        "feature_1.edge_group.top_outer_edges"
    )
    top_edges = registry.get_reference_group("feature_1.top_outer_edges")
    assert [reference.name for reference in top_edges] == [
        "feature_1.edge.e001",
        "feature_1.edge.e002",
        "feature_1.edge.e003",
        "feature_1.edge.e004",
    ]
    assert registry.get_reference("feature_1.top_front_left").kind == "vertex"


def test_register_rectangular_prism_instance_references():
    registry = FeatureRegistry()
    target_plane = cq.Plane.XY()

    registry.register_rectangular_prism_faces(
        feature_id="feature_1",
        target_plane=target_plane,
        width=20,
        height=12,
        distance=10,
        position=[20, 0],
        instance_name="inst001",
        semantic_aliases=False,
    )

    assert registry.resolve_reference_name("feature_1.inst001.right") == (
        "feature_1.inst001.face.f005"
    )
    assert registry.resolve_reference_group_name(
        "feature_1.inst001.top_outer_edges"
    ) == "feature_1.inst001.edge_group.top_outer_edges"
    assert registry.resolve_reference_name("feature_1.right") is None


def test_pattern_planes_keep_shared_parent_origin():
    registry = FeatureRegistry()
    target_plane = cq.Plane.XY(origin=(10, 20, 8))

    registry.register_pattern_planes(
        feature_id="bosses",
        target_plane=target_plane,
        distance=6,
        instance_count=4,
    )

    top_plane = registry.get_plane("bosses.top")
    assert top_plane.origin.toTuple() == (10.0, 20.0, 14.0)
    assert registry.get_reference("bosses.top").metadata["instance_count"] == 4


def test_unknown_reference_returns_none():
    registry = FeatureRegistry()

    assert registry.get_plane("missing.face") is None


def test_registry_supports_non_planar_reference_scaffolds():
    registry = FeatureRegistry()
    frame = ReferenceFrame.from_plane(cq.Plane.XY())

    registry.register_surface(
        "shaft.surface.s001",
        frame,
        source_feature_id="shaft",
        aliases=["shaft.outer_surface"],
        metadata={
            "surface_family": "revolved",
            "surface_type": "cylindrical_or_conical",
            "coordinates": "surface_uv",
        },
    )
    registry.register_edge(
        "base.edge.e001",
        frame,
        source_feature_id="base",
        aliases=["base.outer_edge_001"],
        metadata={"edge_family": "intersection"},
    )
    registry.register_vertex(
        "base.vertex.v001",
        frame,
        source_feature_id="base",
        aliases=["base.corner_001"],
        metadata={"vertex_family": "edge_intersection"},
    )

    assert registry.get_reference("shaft.outer_surface").kind == "surface"
    assert registry.get_reference("base.outer_edge_001").kind == "edge"
    assert registry.get_reference("base.corner_001").kind == "vertex"


def test_registry_rejects_unknown_reference_kind():
    registry = FeatureRegistry()
    frame = ReferenceFrame.from_plane(cq.Plane.XY())

    with pytest.raises(ValueError, match="Unsupported reference kind: mystery"):
        registry.register_reference("base.mystery001", "mystery", frame)
