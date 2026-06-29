import cadquery as cq

from prompt2cad.feature_registry import FeatureRegistry


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

    right_plane = registry.get_plane("feature_1.right")

    assert right_plane is not None
    assert right_plane.origin.toTuple() == (30.0, 0.0, 5.0)
    assert right_plane.xDir.toTuple() == (0.0, 1.0, 0.0)
    assert right_plane.zDir.toTuple() == (1.0, 0.0, 0.0)


def test_unknown_reference_returns_none():
    registry = FeatureRegistry()

    assert registry.get_plane("missing.face") is None
