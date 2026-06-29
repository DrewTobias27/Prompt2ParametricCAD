"""Feature reference storage for placing later CAD operations.

This module is the foundation for moving from a flat operation list toward a
feature graph.  The interpreter can ask the registry for a target reference
frame like ``feature_1.right`` without needing to rediscover that face from the
final fused shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cadquery as cq


SUPPORTED_REFERENCE_KINDS = {
    "plane",
    "surface",
    "edge",
    "vertex",
    "axis",
    "point",
    "sketch_entity",
}


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

    def to_debug_dict(self) -> dict:
        """Return a JSON-friendly frame description."""
        return {
            "origin": self.origin,
            "x_axis": self.x_axis,
            "normal": self.normal,
        }


@dataclass(frozen=True)
class FeatureReference:
    """A named geometric reference created by a feature."""

    name: str
    kind: str
    frame: ReferenceFrame
    source_feature_id: str | None = None
    aliases: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_debug_dict(self) -> dict:
        """Return a JSON-friendly reference description."""
        return {
            "name": self.name,
            "kind": self.kind,
            "source_feature_id": self.source_feature_id,
            "aliases": self.aliases,
            "frame": self.frame.to_debug_dict(),
            "metadata": self.metadata,
        }


class FeatureRegistry:
    """Store feature-created references for future operation targets."""

    def __init__(self) -> None:
        self.references: dict[str, FeatureReference] = {}
        self.aliases: dict[str, str] = {}

    def register_reference(
        self,
        name: str,
        kind: str,
        frame: ReferenceFrame,
        source_feature_id: str | None = None,
        aliases: list[str] | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Register a named feature reference."""
        if kind not in SUPPORTED_REFERENCE_KINDS:
            raise ValueError(f"Unsupported reference kind: {kind}")

        aliases = list(dict.fromkeys(aliases or []))
        self.references[name] = FeatureReference(
            name=name,
            kind=kind,
            frame=frame,
            source_feature_id=source_feature_id,
            aliases=aliases,
            metadata=metadata or {},
        )
        for alias in aliases:
            self.aliases[alias] = name

    def register_plane(
        self,
        name: str,
        frame: ReferenceFrame,
        source_feature_id: str | None = None,
        aliases: list[str] | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Register a planar face reference."""
        self.register_reference(
            name=name,
            kind="plane",
            frame=frame,
            source_feature_id=source_feature_id,
            aliases=aliases,
            metadata=metadata,
        )

    def get_plane(self, name: str, inset: float = 0) -> cq.Plane | None:
        """Return a registered planar target as a CadQuery plane."""
        reference = self.get_reference(name)
        if reference is None or reference.kind != "plane":
            return None

        return reference.frame.to_plane(inset=inset)

    def get_reference(self, name: str) -> FeatureReference | None:
        """Return a reference by canonical name or alias."""
        canonical_name = self.resolve_reference_name(name)
        if canonical_name is None:
            return None

        return self.references[canonical_name]

    def resolve_reference_name(self, name: str) -> str | None:
        """Resolve a canonical reference name or alias."""
        if name in self.references:
            return name

        return self.aliases.get(name)

    def has_reference(self, name: str) -> bool:
        """Return whether a canonical reference or alias is registered."""
        return self.resolve_reference_name(name) is not None

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
        instance_name: str | None = None,
        semantic_aliases: bool = True,
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

        faces = [
            (
                "top",
                parent_frame.child_frame(
                (x, y, distance),
                parent_plane.xDir,
                parent_plane.zDir,
            ),
            ),
            (
                "bottom",
                parent_frame.child_frame(
                (x, y, 0),
                parent_plane.xDir,
                parent_plane.zDir.multiply(-1),
            ),
            ),
            (
                "front",
                parent_frame.child_frame(
                (x, y + half_height, half_distance),
                parent_plane.xDir,
                parent_plane.yDir,
            ),
            ),
            (
                "back",
                parent_frame.child_frame(
                (x, y - half_height, half_distance),
                parent_plane.xDir,
                parent_plane.yDir.multiply(-1),
            ),
            ),
            (
                "right",
                parent_frame.child_frame(
                (x + half_width, y, half_distance),
                parent_plane.yDir,
                parent_plane.xDir,
            ),
            ),
            (
                "left",
                parent_frame.child_frame(
                (x - half_width, y, half_distance),
                parent_plane.yDir,
                parent_plane.xDir.multiply(-1),
            ),
            ),
        ]

        reference_scope = feature_id
        if instance_name is not None:
            reference_scope = f"{feature_id}.{instance_name}"

        for index, (face_name, frame) in enumerate(faces, start=1):
            canonical_name = f"{reference_scope}.face.f{index:03d}"
            aliases = [f"{reference_scope}.{face_name}"]
            if semantic_aliases and instance_name is None:
                aliases.extend(
                    [
                        f"{feature_id}.{face_name}",
                        f"{feature_id}.face.{face_name}",
                    ]
                )

            self.register_plane(
                canonical_name,
                frame,
                source_feature_id=feature_id,
                aliases=aliases,
                metadata={
                    "profile": "rectangle",
                    "semantic_label": face_name,
                    "width": width,
                    "height": height,
                    "distance": distance,
                    "position": position,
                    "instance_name": instance_name,
                },
            )

    def register_surface(
        self,
        name: str,
        frame: ReferenceFrame,
        source_feature_id: str | None = None,
        aliases: list[str] | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Register a non-planar surface reference scaffold."""
        self.register_reference(
            name=name,
            kind="surface",
            frame=frame,
            source_feature_id=source_feature_id,
            aliases=aliases,
            metadata=metadata,
        )

    def register_edge(
        self,
        name: str,
        frame: ReferenceFrame,
        source_feature_id: str | None = None,
        aliases: list[str] | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Register an edge reference scaffold."""
        self.register_reference(
            name=name,
            kind="edge",
            frame=frame,
            source_feature_id=source_feature_id,
            aliases=aliases,
            metadata=metadata,
        )

    def register_vertex(
        self,
        name: str,
        frame: ReferenceFrame,
        source_feature_id: str | None = None,
        aliases: list[str] | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Register a vertex/corner reference scaffold."""
        self.register_reference(
            name=name,
            kind="vertex",
            frame=frame,
            source_feature_id=source_feature_id,
            aliases=aliases,
            metadata=metadata,
        )

    def to_debug_dict(self) -> dict:
        """Return a JSON-friendly registry description."""
        return {
            "references": [
                reference.to_debug_dict()
                for reference in self.references.values()
            ],
            "aliases": self.aliases,
        }
