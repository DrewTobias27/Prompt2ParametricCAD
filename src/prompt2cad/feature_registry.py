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


def vector_dot(first: cq.Vector, second: cq.Vector) -> float:
    """Return the dot product of two CadQuery vectors."""
    return first.x * second.x + first.y * second.y + first.z * second.z


def normalized_vector(vector: cq.Vector) -> cq.Vector:
    """Return a unit vector in the same direction."""
    length = vector.Length
    if length == 0:
        raise ValueError("Cannot normalize a zero-length vector")

    return vector.multiply(1 / length)


def box_metadata_from_points(
    points: list[tuple[float, float, float]],
) -> dict[str, float]:
    """Return bounding-box metadata for a list of xyz points."""
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    zs = [point[2] for point in points]
    return {
        "xmin": min(xs),
        "xmax": max(xs),
        "ymin": min(ys),
        "ymax": max(ys),
        "zmin": min(zs),
        "zmax": max(zs),
    }


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
        self.reference_groups: dict[str, list[str]] = {}
        self.group_aliases: dict[str, str] = {}

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

        self.register_rectangular_prism_edges_and_vertices(
            feature_id=feature_id,
            reference_scope=reference_scope,
            parent_frame=parent_frame,
            target_plane=parent_plane,
            width=width,
            height=height,
            distance=distance,
            position=position,
            instance_name=instance_name,
            semantic_aliases=semantic_aliases,
        )

    def register_rectangular_prism_edges_and_vertices(
        self,
        feature_id: str,
        reference_scope: str,
        parent_frame: ReferenceFrame,
        target_plane: cq.Plane,
        width: float,
        height: float,
        distance: float,
        position: list,
        instance_name: str | None,
        semantic_aliases: bool,
    ) -> None:
        """Register edge and vertex frames created by a rectangular extrusion."""
        x = position[0]
        y = position[1]
        half_width = width / 2
        half_height = height / 2

        local_points = {
            "top_front_left": (x - half_width, y + half_height, distance),
            "top_front_right": (x + half_width, y + half_height, distance),
            "top_back_right": (x + half_width, y - half_height, distance),
            "top_back_left": (x - half_width, y - half_height, distance),
            "bottom_front_left": (x - half_width, y + half_height, 0),
            "bottom_front_right": (x + half_width, y + half_height, 0),
            "bottom_back_right": (x + half_width, y - half_height, 0),
            "bottom_back_left": (x - half_width, y - half_height, 0),
        }
        world_points = {
            label: vector_to_tuple(parent_frame.local_point(point))
            for label, point in local_points.items()
        }

        edge_specs = [
            ("top_front", "top_front_left", "top_front_right"),
            ("top_right", "top_front_right", "top_back_right"),
            ("top_back", "top_back_right", "top_back_left"),
            ("top_left", "top_back_left", "top_front_left"),
            ("bottom_front", "bottom_front_left", "bottom_front_right"),
            ("bottom_right", "bottom_front_right", "bottom_back_right"),
            ("bottom_back", "bottom_back_right", "bottom_back_left"),
            ("bottom_left", "bottom_back_left", "bottom_front_left"),
            ("front_left", "bottom_front_left", "top_front_left"),
            ("front_right", "bottom_front_right", "top_front_right"),
            ("back_right", "bottom_back_right", "top_back_right"),
            ("back_left", "bottom_back_left", "top_back_left"),
        ]
        edge_names_by_label = {}
        for index, (edge_label, start_label, end_label) in enumerate(
            edge_specs,
            start=1,
        ):
            canonical_name = f"{reference_scope}.edge.e{index:03d}"
            edge_names_by_label[edge_label] = canonical_name
            start_point = world_points[start_label]
            end_point = world_points[end_label]
            frame = self.edge_frame(
                start_point=start_point,
                end_point=end_point,
                target_plane=target_plane,
            )
            aliases = [
                f"{reference_scope}.{edge_label}_edge",
                f"{reference_scope}.edge.{edge_label}",
            ]
            if semantic_aliases and instance_name is None:
                aliases.extend(
                    [
                        f"{feature_id}.{edge_label}_edge",
                        f"{feature_id}.edge.{edge_label}",
                    ]
                )

            self.register_edge(
                canonical_name,
                frame,
                source_feature_id=feature_id,
                aliases=aliases,
                metadata={
                    "profile": "rectangle",
                    "semantic_label": edge_label,
                    "start_vertex": start_label,
                    "end_vertex": end_label,
                    "start_point": start_point,
                    "end_point": end_point,
                    "center": frame.origin,
                    "bounding_box": box_metadata_from_points(
                        [start_point, end_point]
                    ),
                    "width": width,
                    "height": height,
                    "distance": distance,
                    "position": position,
                    "instance_name": instance_name,
                },
            )

        for index, (vertex_label, world_point) in enumerate(
            world_points.items(),
            start=1,
        ):
            canonical_name = f"{reference_scope}.vertex.v{index:03d}"
            aliases = [
                f"{reference_scope}.{vertex_label}",
                f"{reference_scope}.vertex.{vertex_label}",
            ]
            if semantic_aliases and instance_name is None:
                aliases.extend(
                    [
                        f"{feature_id}.{vertex_label}",
                        f"{feature_id}.vertex.{vertex_label}",
                    ]
                )

            self.register_vertex(
                canonical_name,
                ReferenceFrame(
                    origin=world_point,
                    x_axis=vector_to_tuple(target_plane.xDir),
                    normal=vector_to_tuple(target_plane.zDir),
                ),
                source_feature_id=feature_id,
                aliases=aliases,
                metadata={
                    "profile": "rectangle",
                    "semantic_label": vertex_label,
                    "point": world_point,
                    "instance_name": instance_name,
                },
            )

        self.register_rectangular_prism_edge_groups(
            reference_scope,
            edge_names_by_label,
            semantic_aliases=semantic_aliases,
            feature_id=feature_id,
            instance_name=instance_name,
        )

    def register_rectangular_prism_edge_groups(
        self,
        reference_scope: str,
        edge_names_by_label: dict[str, str],
        semantic_aliases: bool,
        feature_id: str,
        instance_name: str | None,
    ) -> None:
        """Register useful edge groups for a rectangular prism."""
        groups = {
            "top_outer_edges": [
                "top_front",
                "top_right",
                "top_back",
                "top_left",
            ],
            "bottom_outer_edges": [
                "bottom_front",
                "bottom_right",
                "bottom_back",
                "bottom_left",
            ],
            "vertical_edges": [
                "front_left",
                "front_right",
                "back_right",
                "back_left",
            ],
            "all_edges": list(edge_names_by_label),
        }

        for group_label, edge_labels in groups.items():
            canonical_name = f"{reference_scope}.edge_group.{group_label}"
            aliases = [
                f"{reference_scope}.{group_label}",
                f"{reference_scope}.edge.{group_label}",
            ]
            if semantic_aliases and instance_name is None:
                aliases.extend(
                    [
                        f"{feature_id}.{group_label}",
                        f"{feature_id}.edge.{group_label}",
                    ]
                )

            self.register_reference_group(
                canonical_name,
                [edge_names_by_label[edge_label] for edge_label in edge_labels],
                aliases=aliases,
            )

    @staticmethod
    def edge_frame(
        start_point: tuple[float, float, float],
        end_point: tuple[float, float, float],
        target_plane: cq.Plane,
    ) -> ReferenceFrame:
        """Create a stable reference frame for a linear edge."""
        start_vector = cq.Vector(*start_point)
        end_vector = cq.Vector(*end_point)
        edge_direction = normalized_vector(end_vector.sub(start_vector))
        normal = target_plane.zDir
        if abs(vector_dot(edge_direction, normal)) > 0.99:
            normal = target_plane.xDir
        if abs(vector_dot(edge_direction, normal)) > 0.99:
            normal = target_plane.yDir

        midpoint = start_vector.add(end_vector).multiply(0.5)
        return ReferenceFrame(
            origin=vector_to_tuple(midpoint),
            x_axis=vector_to_tuple(edge_direction),
            normal=vector_to_tuple(normal),
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

    def register_reference_group(
        self,
        name: str,
        reference_names: list[str],
        aliases: list[str] | None = None,
    ) -> None:
        """Register a named group of references."""
        missing_references = [
            reference_name
            for reference_name in reference_names
            if reference_name not in self.references
        ]
        if missing_references:
            raise ValueError(
                "Cannot register reference group with missing references: "
                + ", ".join(missing_references)
            )

        aliases = list(dict.fromkeys(aliases or []))
        self.reference_groups[name] = list(reference_names)
        for alias in aliases:
            self.group_aliases[alias] = name

    def resolve_reference_group_name(self, name: str) -> str | None:
        """Resolve a canonical reference group name or alias."""
        if name in self.reference_groups:
            return name

        return self.group_aliases.get(name)

    def get_reference_group(self, name: str) -> list[FeatureReference] | None:
        """Return references in a group by canonical name or alias."""
        canonical_name = self.resolve_reference_group_name(name)
        if canonical_name is None:
            return None

        return [
            self.references[reference_name]
            for reference_name in self.reference_groups[canonical_name]
        ]

    def has_reference_group(self, name: str) -> bool:
        """Return whether a reference group or group alias is registered."""
        return self.resolve_reference_group_name(name) is not None

    def to_debug_dict(self) -> dict:
        """Return a JSON-friendly registry description."""
        return {
            "references": [
                reference.to_debug_dict()
                for reference in self.references.values()
            ],
            "aliases": self.aliases,
            "reference_groups": self.reference_groups,
            "group_aliases": self.group_aliases,
        }
