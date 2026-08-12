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


def test_side_extrusion_exposes_global_top_face_alias():
    registry = FeatureRegistry()
    side_plane = cq.Plane(
        origin=(50, 0, 4),
        xDir=(0, 1, 0),
        normal=(1, 0, 0),
    )

    registry.register_rectangular_prism_faces(
        feature_id="side_tab",
        target_plane=side_plane,
        width=18,
        height=8,
        distance=10,
        position=[0, 0],
    )

    global_top = registry.get_plane("side_tab.global_top")

    assert global_top is not None
    assert global_top.origin.toTuple() == pytest.approx((55, 0, 8))
    assert global_top.zDir.toTuple() == pytest.approx((0, 0, 1))
    assert registry.resolve_reference_name("side_tab.global_top") == (
        "side_tab.face.f003"
    )


def test_arbitrary_extrusion_registers_stable_directional_planes():
    registry = FeatureRegistry()
    target_plane = cq.Plane.XY()
    solid = cq.Workplane("XY").circle(35).extrude(8).val()

    registry.register_extruded_solid_references(
        feature_id="base",
        reference_scope="base",
        target_plane=target_plane,
        solid=solid,
        distance=8,
        position=[0, 0],
    )

    right = registry.get_plane("base.right")
    global_top = registry.get_plane("base.global_top")

    assert right is not None
    assert right.origin.toTuple() == pytest.approx((35, 0, 4))
    assert right.zDir.toTuple() == pytest.approx((1, 0, 0))
    assert global_top.origin.toTuple() == pytest.approx((0, 0, 8))


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
