"""Feature reference storage for placing later CAD operations.

This module is the foundation for moving from a flat operation list toward a
feature graph.  The interpreter can ask the registry for a target reference
frame like ``feature_1.right`` without needing to rediscover that face from the
final fused shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cadquery as cq


def vector_to_tuple(vector: cq.Vector) -> tuple[float, float, float]:
    """Convert a CadQuery vector to a plain xyz tuple."""
    return (vector.x, vector.y, vector.z)


@dataclass(frozen=True)
class ReferenceFrame:
    """A local coordinate system used to place sketches and features."""

    origin: tuple[float, float, float]
    x_axis: tuple[float, float, float]
    normal: tuple[float, float, float]

    @classmethod
    def from_plane(cls, plane: cq.Plane) -> "ReferenceFrame":
        """Create a reference frame from a CadQuery plane."""
        return cls(
            origin=vector_to_tuple(plane.origin),
            x_axis=vector_to_tuple(plane.xDir),
            normal=vector_to_tuple(plane.zDir),
        )

    def to_plane(self, inset: float = 0) -> cq.Plane:
        """Convert the reference frame back to a CadQuery plane."""
        plane = cq.Plane(
            origin=self.origin,
            xDir=self.x_axis,
            normal=self.normal,
        )
        if not inset:
            return plane

        inset_origin = plane.origin.sub(plane.zDir.multiply(inset))
        return cq.Plane(
            origin=vector_to_tuple(inset_origin),
            xDir=self.x_axis,
            normal=self.normal,
        )

    def local_point(self, point: tuple[float, float, float]) -> cq.Vector:
        """Convert a local xyz point into world coordinates."""
        return self.to_plane().toWorldCoords(point)

    def child_frame(
        self,
        origin: tuple[float, float, float],
        x_axis: cq.Vector,
        normal: cq.Vector,
    ) -> "ReferenceFrame":
        """Create a child frame from a local point and world-space axes."""
        return ReferenceFrame(
            origin=vector_to_tuple(self.local_point(origin)),
            x_axis=vector_to_tuple(x_axis),
            normal=vector_to_tuple(normal),
        )


@dataclass(frozen=True)
class FeatureReference:
    """A named geometric reference created by a feature."""

    name: str
    kind: str
    frame: ReferenceFrame
    source_feature_id: str | None = None
    metadata: dict = field(default_factory=dict)


class FeatureRegistry:
    """Store feature-created references for future operation targets."""

    def __init__(self) -> None:
        self.references: dict[str, FeatureReference] = {}

    def register_reference(
        self,
        name: str,
        kind: str,
        frame: ReferenceFrame,
        source_feature_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Register a named feature reference."""
        self.references[name] = FeatureReference(
            name=name,
            kind=kind,
            frame=frame,
            source_feature_id=source_feature_id,
            metadata=metadata or {},
        )

    def register_plane(
        self,
        name: str,
        frame: ReferenceFrame,
        source_feature_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Register a planar face reference."""
        self.register_reference(
            name=name,
            kind="plane",
            frame=frame,
            source_feature_id=source_feature_id,
            metadata=metadata,
        )

    def get_plane(self, name: str, inset: float = 0) -> cq.Plane | None:
        """Return a registered planar target as a CadQuery plane."""
        reference = self.references.get(name)
        if reference is None or reference.kind != "plane":
            return None

        return reference.frame.to_plane(inset=inset)

    def reference_names_for_feature(self, feature_id: str) -> list[str]:
        """Return sorted reference names created by a feature."""
        return sorted(
            reference.name
            for reference in self.references.values()
            if reference.source_feature_id == feature_id
        )

    def register_rectangular_prism_faces(
        self,
        feature_id: str | None,
        target_plane: cq.Plane,
        width: float,
        height: float,
        distance: float,
        position: list,
    ) -> None:
        """Register face frames created by a rectangular extrusion."""
        if not feature_id:
            return

        parent_frame = ReferenceFrame.from_plane(target_plane)
        parent_plane = parent_frame.to_plane()
        x = position[0]
        y = position[1]
        half_width = width / 2
        half_height = height / 2
        half_distance = distance / 2

        faces = {
            "top": parent_frame.child_frame(
                (x, y, distance),
                parent_plane.xDir,
                parent_plane.zDir,
            ),
            "bottom": parent_frame.child_frame(
                (x, y, 0),
                parent_plane.xDir,
                parent_plane.zDir.multiply(-1),
            ),
            "front": parent_frame.child_frame(
                (x, y + half_height, half_distance),
                parent_plane.xDir,
                parent_plane.yDir,
            ),
            "back": parent_frame.child_frame(
                (x, y - half_height, half_distance),
                parent_plane.xDir,
                parent_plane.yDir.multiply(-1),
            ),
            "right": parent_frame.child_frame(
                (x + half_width, y, half_distance),
                parent_plane.yDir,
                parent_plane.xDir,
            ),
            "left": parent_frame.child_frame(
                (x - half_width, y, half_distance),
                parent_plane.yDir,
                parent_plane.xDir.multiply(-1),
            ),
        }

        for face_name, frame in faces.items():
            self.register_plane(
                f"{feature_id}.{face_name}",
                frame,
                source_feature_id=feature_id,
                metadata={
                    "profile": "rectangle",
                    "width": width,
                    "height": height,
                    "distance": distance,
                    "position": position,
                },
            )
