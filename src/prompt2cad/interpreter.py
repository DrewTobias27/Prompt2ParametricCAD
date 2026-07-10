"""Interpret structured CAD operations and build a CadQuery model."""

import cadquery as cq

from prompt2cad.feature_graph import FeatureGraph
from prompt2cad.feature_registry import FeatureReference


BASE_OPERATION_TYPES = {"extrude", "revolve"}
SIDE_FACE_NAMES = {"front", "back", "left", "right"}
VIRTUAL_TARGET_POSITION_FACTORS = (1, 0.75, 0.5, 0.25, 0)
ADD_REVOLVE_POSITION_FACTORS = (1, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.25)
GEOMETRY_TOLERANCE = 1e-9
EDGE_MATCH_TOLERANCE = 1e-6


def apply_face_tags(
    part: cq.Workplane,
    feature_id: str,
    face_tags: dict,
) -> cq.Workplane:
    """Tag named faces on a feature for later operations."""
    for tag_name, selector in face_tags.items():
        if not isinstance(tag_name, str):
            raise ValueError("Face tag names must be strings")
        if not isinstance(selector, str):
            raise ValueError("Face tag selectors must be strings")

        workplane_options = {}
        if selector in {">X", "<X", ">Y", "<Y"}:
            workplane_options["centerOption"] = "CenterOfBoundBox"

        part = (
            part.faces(selector)
            .workplane(**workplane_options)
            .tag(f"{feature_id}.{tag_name}")
            .end()
            .end()
        )

    return part


def get_available_tags(part: cq.Workplane) -> list:
    """Return the currently known CadQuery tag names."""
    context = getattr(part, "ctx", None)
    tags = getattr(context, "tags", {})
    return sorted(tags.keys())


def get_tagged_workplane(
    part: cq.Workplane,
    target: str,
    operation_number: int,
) -> cq.Workplane:
    """Return a tagged workplane or raise a clear target error."""
    try:
        return part.workplaneFromTagged(target)
    except Exception as error:
        available_tags = get_available_tags(part)
        tag_message = ""
        if available_tags:
            tag_message = f" Available tags: {', '.join(available_tags)}."

        raise ValueError(
            f"Operation {operation_number}: target '{target}' was not found."
            f"{tag_message}"
        ) from error


def get_virtual_target_plane(
    part: cq.Workplane,
    target: str,
    operation_number: int,
    inset: float = 0,
) -> cq.Plane:
    """Create a fallback workplane from the part bounding box."""
    if "." not in target:
        raise ValueError(
            f"Operation {operation_number}: target '{target}' must use "
            "the format 'feature.face', such as 'base.top'"
        )

    _, face_name = target.split(".", 1)
    bounding_box = part.val().BoundingBox()

    center_x = (bounding_box.xmin + bounding_box.xmax) / 2
    center_y = (bounding_box.ymin + bounding_box.ymax) / 2
    center_z = (bounding_box.zmin + bounding_box.zmax) / 2

    virtual_faces = {
        "top": {
            "origin": (center_x, center_y, bounding_box.zmax),
            "xDir": (1, 0, 0),
            "normal": (0, 0, 1),
        },
        "bottom": {
            "origin": (center_x, center_y, bounding_box.zmin),
            "xDir": (1, 0, 0),
            "normal": (0, 0, -1),
        },
        "front": {
            "origin": (center_x, bounding_box.ymax, center_z),
            "xDir": (1, 0, 0),
            "normal": (0, 1, 0),
        },
        "back": {
            "origin": (center_x, bounding_box.ymin, center_z),
            "xDir": (1, 0, 0),
            "normal": (0, -1, 0),
        },
        "right": {
            "origin": (bounding_box.xmax, center_y, center_z),
            "xDir": (0, 1, 0),
            "normal": (1, 0, 0),
        },
        "left": {
            "origin": (bounding_box.xmin, center_y, center_z),
            "xDir": (0, 1, 0),
            "normal": (-1, 0, 0),
        },
    }

    if face_name not in virtual_faces:
        supported_faces = ", ".join(sorted(virtual_faces))
        raise ValueError(
            f"Operation {operation_number}: target '{target}' was not found "
            f"and cannot be used as a virtual target. Supported virtual "
            f"faces: {supported_faces}."
        )

    face = virtual_faces[face_name]
    origin = face["origin"]
    normal = face["normal"]
    if inset:
        origin = tuple(
            origin[index] - normal[index] * inset
            for index in range(3)
        )

    return cq.Plane(
        origin=origin,
        xDir=face["xDir"],
        normal=normal,
    )


def get_target_face_name(target: str) -> str | None:
    """Return the face name from a target like 'base.front'."""
    if "." not in target:
        return None

    return target.split(".", 1)[1]


def is_side_target(target: str) -> bool:
    """Return whether a target points to a side face."""
    return get_target_face_name(target) in SIDE_FACE_NAMES


def clamp(value: float, lower_limit: float, upper_limit: float) -> float:
    """Clamp a numeric value into an inclusive range."""
    return max(lower_limit, min(value, upper_limit))


def is_number(value: object) -> bool:
    """Return whether a value is a CAD-safe int or float, excluding booleans."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_positive_number(value: object, value_name: str) -> None:
    """Validate that a dimension is a positive int or float."""
    if not is_number(value):
        raise ValueError(f"{value_name} must be an integer or float")

    if value <= 0:
        raise ValueError(f"{value_name} must be greater than zero")


def points_match(first_point: cq.Vector, second_point: cq.Vector) -> bool:
    """Return whether two vectors are effectively the same point."""
    return first_point.sub(second_point).Length <= GEOMETRY_TOLERANCE


def points_are_collinear(
    first_point: cq.Vector,
    second_point: cq.Vector,
    third_point: cq.Vector,
) -> bool:
    """Return whether three 2D vectors are effectively collinear."""
    first_vector = second_point.sub(first_point)
    second_vector = third_point.sub(first_point)
    cross_z = first_vector.x * second_vector.y - first_vector.y * second_vector.x
    return abs(cross_z) <= GEOMETRY_TOLERANCE


def get_target_workplane(
    part: cq.Workplane,
    target: str,
    operation_number: int,
    inset: float = 0,
    prefer_virtual_side: bool = False,
    feature_graph: FeatureGraph | None = None,
) -> tuple[cq.Workplane, bool]:
    """Return a target workplane and whether it is a virtual fallback."""
    if feature_graph is not None:
        target_plane = feature_graph.registry.get_plane(target, inset=inset)
        if target_plane is not None:
            return cq.Workplane(target_plane), True

    if prefer_virtual_side and is_side_target(target):
        virtual_plane = get_virtual_target_plane(
            part,
            target,
            operation_number,
            inset,
        )
        return cq.Workplane(virtual_plane), True

    try:
        return get_tagged_workplane(part, target, operation_number), False
    except ValueError:
        virtual_plane = get_virtual_target_plane(
            part,
            target,
            operation_number,
            inset,
        )
        return cq.Workplane(virtual_plane), True


def build_base_extrusion(
    operation: dict,
    operation_number: int,
    feature_graph: FeatureGraph | None = None,
) -> cq.Workplane:
    """Build the initial solid and tag its top workplane."""
    feature_id = operation["id"]
    plane = operation["plane"]
    distance = operation["distance"]

    validate_positive_number(distance, "Distance")

    workplane = cq.Workplane(plane)
    workplane = create_profile(workplane, operation, operation_number)
    part = workplane.extrude(distance)

    default_face_tags = {
        "top": ">Z",
        "bottom": "<Z",
    }
    if operation["profile"] == "rectangle":
        default_face_tags.update(
            {
                "front": ">Y",
                "back": "<Y",
                "right": ">X",
                "left": "<X",
            }
        )

    face_tags = operation.get("face_tags", default_face_tags)
    if operation["profile"] == "rectangle" and feature_graph is not None:
        feature_graph.registry.register_rectangular_prism_faces(
            feature_id,
            cq.Plane.named(plane),
            operation["width"],
            operation["height"],
            distance,
            [0, 0],
        )
    elif feature_graph is not None:
        feature_graph.registry.register_extruded_solid_references(
            feature_id=feature_id,
            reference_scope=feature_id,
            target_plane=cq.Plane.named(plane),
            solid=part.val(),
            distance=distance,
            position=[0, 0],
        )

    return apply_face_tags(part, feature_id, face_tags)


def get_positions(operation: dict, operation_number: int) -> list:
    """Return and validate one or more profile positions."""
    if "positions" not in operation:
        raise ValueError(
            f"Operation {operation_number}: positions is required. "
            "Use positions like [[0, 0]] instead of x and y."
        )

    positions = operation["positions"]

    if len(positions) == 0:
        raise ValueError(
            f"Operation {operation_number}: "
            "at least one profile position must be defined"
        )

    for position in positions:
        if len(position) != 2:
            raise ValueError(
                f"Operation {operation_number}: "
                "each profile position must contain exactly x and y"
            )

        x = position[0]
        y = position[1]
        if not is_number(x):
            raise ValueError(
                f"Operation {operation_number}: "
                "profile x position must be an integer or float"
            )
        if not is_number(y):
            raise ValueError(
                f"Operation {operation_number}: "
                "profile y position must be an integer or float"
            )
    return positions


def normalize_side_target_positions(
    part: cq.Workplane,
    target: str,
    positions: list,
) -> list:
    """Move obviously misplaced side-target positions back onto the side face."""
    if not is_side_target(target):
        return positions

    bounding_box = part.val().BoundingBox()
    face_name = get_target_face_name(target)
    if face_name in {"front", "back"}:
        first_limit = bounding_box.xlen / 2
    else:
        first_limit = bounding_box.ylen / 2
    vertical_limit = bounding_box.zlen / 2
    normalized_positions = []

    for position in positions:
        first_coordinate = position[0]
        vertical_coordinate = position[1]

        if (
            abs(vertical_coordinate) > vertical_limit
            and abs(first_coordinate) <= vertical_limit
        ):
            normalized_positions.append(
                [vertical_coordinate, first_coordinate]
            )
        elif abs(vertical_coordinate) > vertical_limit:
            normalized_positions.append([first_coordinate, 0])
        else:
            normalized_positions.append(position)

    clamped_positions = []
    for first_coordinate, vertical_coordinate in normalized_positions:
        clamped_positions.append(
            [
                clamp(first_coordinate, -first_limit, first_limit),
                clamp(vertical_coordinate, -vertical_limit, vertical_limit),
            ]
        )

    return clamped_positions


def scale_positions_toward_origin(positions: list, factor: float) -> list:
    """Scale 2D positions toward the target workplane origin."""
    return [
        [
            position[0] * factor,
            position[1] * factor,
        ]
        for position in positions
    ]


def create_profile(
    workplane: cq.Workplane,
    operation: dict,
    operation_number: int,
) -> cq.Workplane:
    """Create a sketch profile on the given workplane."""
    profile = operation["profile"]
    if profile == "rectangle":
        width = operation["width"]
        height = operation["height"]

        validate_positive_number(width, "Width")
        validate_positive_number(height, "Height")

        workplane = workplane.rect(width, height)
    elif profile == "circle":
        diameter = operation["diameter"]

        validate_positive_number(diameter, "Diameter")

        workplane = workplane.circle(diameter / 2)
    elif profile == "polygon":
        sides = operation["sides"]
        diameter = operation["diameter"]

        if not isinstance(sides, int) or isinstance(sides, bool):
            raise ValueError("Polygon sides must be an integer")
        if sides < 3:
            raise ValueError("Polygon must have at least three sides")
        validate_positive_number(diameter, "Diameter")

        workplane = workplane.polygon(sides, diameter)

    elif profile == "polyline":
        points = operation["points"]

        if len(points) < 3:
            raise ValueError("Polyline must have at least three points")

        for point in points:
            if len(point) != 2:
                raise ValueError(
                    "Each polyline point must contain exactly x and y"
                )

            x = point[0]
            y = point[1]
            if not is_number(x):
                raise ValueError(
                    "Polyline x coordinate must be an integer or float"
                )
            if not is_number(y):
                raise ValueError(
                    "Polyline y coordinate must be an integer or float"
                )

        vectors = [cq.Vector(x, y, 0) for x, y in points]
        wire = cq.Wire.makePolygon(vectors, close=True)
        workplane = workplane.eachpoint(
            wire,
            useLocalCoordinates=True,
        )
    elif profile == "sketch":
        start = operation["start"]

        if len(start) != 2:
            raise ValueError(
                "Sketch start point must contain exactly x and y"
            )

        start_x = start[0]
        start_y = start[1]
        if not is_number(start_x):
            raise ValueError(
                "Sketch start x coordinate must be an integer or float"
            )
        if not is_number(start_y):
            raise ValueError(
                "Sketch start y coordinate must be an integer or float"
            )

        segments = operation["segments"]
        if len(segments) == 0:
            raise ValueError("Sketch must contain at least one segment")

        close = operation.get("close", True)
        if close is not True:
            raise ValueError("Sketch must be closed")
        start_vector = cq.Vector(start_x, start_y, 0)
        current = start_vector
        edges = []
        for segment in segments:
            if "type" not in segment:
                raise ValueError("Sketch segment must have a type")
            if segment["type"] == "line":
                end = segment["to"]
                if len(end) != 2:
                    raise ValueError(
                        "Sketch line end point must contain exactly x and y"
                    )
                end_x = end[0]
                end_y = end[1]
                if not is_number(end_x):
                    raise ValueError(
                        "Sketch arc end x coordinate must be an integer or float"
                    )
                if not is_number(end_y):
                    raise ValueError(
                        "Sketch arc end y coordinate must be an integer or float"
                    )
                endpoint = cq.Vector(end_x, end_y, 0)
                if not points_match(current, endpoint):
                    edge = cq.Edge.makeLine(current, endpoint)
                    edges.append(edge)
                current = endpoint

            elif segment["type"] == "arc":
                through = segment["through"]
                end = segment["to"]

                if len(through) != 2:
                    raise ValueError(
                        "Sketch arc through point must contain exactly x and y"
                    )

                if len(end) != 2:
                    raise ValueError(
                        "Sketch arc end point must contain exactly x and y"
                    )
                through_x = through[0]
                through_y = through[1]
                end_x = end[0]
                end_y = end[1]
                if not is_number(end_x):
                    raise ValueError(
                        "Sketch arc end x coordinate must be an integer or float"
                    )
                if not is_number(end_y):
                    raise ValueError(
                        "Sketch arc end y coordinate must be an integer or float"
                    )
                if not is_number(through_x):
                    raise ValueError(
                        "Sketch arc through x coordinate must be an integer or float"
                    )
                if not is_number(through_y):
                    raise ValueError(
                        "Sketch arc through y coordinate must be an integer or float"
                    )
                through_vector = cq.Vector(through_x, through_y, 0)
                endpoint = cq.Vector(end_x, end_y, 0)

                if points_match(current, endpoint):
                    current = endpoint
                    continue

                if (
                    points_match(current, through_vector)
                    or points_match(through_vector, endpoint)
                    or points_are_collinear(current, through_vector, endpoint)
                ):
                    edge = cq.Edge.makeLine(current, endpoint)
                else:
                    edge = cq.Edge.makeThreePointArc(
                        current,
                        through_vector,
                        endpoint,
                    )

                edges.append(edge)
                current = endpoint

            else:
                raise ValueError(
                    f"Unsupported sketch segment type: {segment['type']}"
                )

        if current != start_vector:
            closing_edge = cq.Edge.makeLine(current, start_vector)
            edges.append(closing_edge)

        if len(edges) < 2:
            raise ValueError("Sketch must contain at least two valid edges")

        wire = cq.Wire.assembleEdges(edges)
        workplane = workplane.eachpoint(
            wire,
            useLocalCoordinates=True,
        )

    else:
        raise ValueError(
            f"Operation {operation_number}: "
            f"unsupported profile: {profile}"
        )
    return workplane


def keep_largest_connected_solid(part: cq.Workplane) -> cq.Workplane:
    """Discard loose cut leftovers and keep the main connected body."""
    solids = part.solids().vals()

    if len(solids) <= 1:
        return part

    largest_solid = max(solids, key=lambda solid: solid.Volume())
    return part.newObject([largest_solid])


def edge_touches_outer_box(edge, bounding_box) -> bool:
    """Return whether an edge lies on the outside boundary of the model box."""
    edge_box = edge.BoundingBox()
    return (
        abs(edge_box.xmin - bounding_box.xmin) <= GEOMETRY_TOLERANCE
        or abs(edge_box.xmax - bounding_box.xmax) <= GEOMETRY_TOLERANCE
        or abs(edge_box.ymin - bounding_box.ymin) <= GEOMETRY_TOLERANCE
        or abs(edge_box.ymax - bounding_box.ymax) <= GEOMETRY_TOLERANCE
    )


def values_are_close(first_value: float, second_value: float, tolerance: float) -> bool:
    """Return whether two float values are within tolerance."""
    return abs(first_value - second_value) <= tolerance


def edge_matches_reference(edge, reference: FeatureReference) -> bool:
    """Return whether a live CadQuery edge matches a saved edge reference."""
    metadata = reference.metadata
    expected_center = metadata.get("center")
    expected_box = metadata.get("bounding_box")
    if expected_center is None or expected_box is None:
        return False

    center = edge.Center()
    edge_box = edge.BoundingBox()
    return (
        values_are_close(center.x, expected_center[0], EDGE_MATCH_TOLERANCE)
        and values_are_close(center.y, expected_center[1], EDGE_MATCH_TOLERANCE)
        and values_are_close(center.z, expected_center[2], EDGE_MATCH_TOLERANCE)
        and values_are_close(edge_box.xmin, expected_box["xmin"], EDGE_MATCH_TOLERANCE)
        and values_are_close(edge_box.xmax, expected_box["xmax"], EDGE_MATCH_TOLERANCE)
        and values_are_close(edge_box.ymin, expected_box["ymin"], EDGE_MATCH_TOLERANCE)
        and values_are_close(edge_box.ymax, expected_box["ymax"], EDGE_MATCH_TOLERANCE)
        and values_are_close(edge_box.zmin, expected_box["zmin"], EDGE_MATCH_TOLERANCE)
        and values_are_close(edge_box.zmax, expected_box["zmax"], EDGE_MATCH_TOLERANCE)
    )


def select_registered_edges(
    part: cq.Workplane,
    references: list[FeatureReference],
    target: str,
    operation_number: int,
) -> list:
    """Select live model edges matching saved feature edge references."""
    live_edges = part.val().Edges()
    selected_edges = []
    selected_edge_ids = set()
    missing_references = []

    for reference in references:
        matching_edge = None
        for edge in live_edges:
            if id(edge) in selected_edge_ids:
                continue
            if edge_matches_reference(edge, reference):
                matching_edge = edge
                break

        if matching_edge is None:
            missing_references.append(reference.name)
        else:
            selected_edge_ids.add(id(matching_edge))
            selected_edges.append(matching_edge)

    if missing_references:
        raise ValueError(
            f"Operation {operation_number}: target '{target}' references "
            "saved feature edges that are no longer present in the current "
            "solid: "
            + ", ".join(missing_references)
        )

    return selected_edges


def select_edges_for_target(
    part: cq.Workplane,
    target: str,
    operation_number: int,
    feature_graph: FeatureGraph | None = None,
) -> list:
    """Resolve a feature edge target into concrete CadQuery edge objects."""
    if feature_graph is not None:
        reference_group = feature_graph.registry.get_reference_group(target)
        if reference_group is not None:
            return select_registered_edges(
                part,
                reference_group,
                target,
                operation_number,
            )

    if "." not in target:
        raise ValueError(
            f"Operation {operation_number}: edge target '{target}' must use "
            "the format 'feature.edge_selector', such as "
            "'base.top_outer_edges'"
        )

    _, edge_selector = target.split(".", 1)
    solid = part.val()
    bounding_box = solid.BoundingBox()
    edges = solid.Edges()

    if edge_selector == "all_edges":
        return list(edges)

    selected_edges = []
    for edge in edges:
        edge_box = edge.BoundingBox()
        center = edge.Center()
        edge_z_length = edge_box.zmax - edge_box.zmin

        if edge_selector == "top_outer_edges":
            if (
                abs(center.z - bounding_box.zmax) <= GEOMETRY_TOLERANCE
                and edge_touches_outer_box(edge, bounding_box)
            ):
                selected_edges.append(edge)
        elif edge_selector == "bottom_outer_edges":
            if (
                abs(center.z - bounding_box.zmin) <= GEOMETRY_TOLERANCE
                and edge_touches_outer_box(edge, bounding_box)
            ):
                selected_edges.append(edge)
        elif edge_selector == "vertical_edges":
            if (
                edge_z_length > GEOMETRY_TOLERANCE
                and edge_touches_outer_box(edge, bounding_box)
            ):
                selected_edges.append(edge)
        else:
            supported_targets = (
                "top_outer_edges, bottom_outer_edges, "
                "vertical_edges, all_edges"
            )
            raise ValueError(
                f"Operation {operation_number}: unsupported edge selector "
                f"'{edge_selector}'. Supported selectors: {supported_targets}."
            )

    if not selected_edges:
        raise ValueError(
            f"Operation {operation_number}: edge target '{target}' did not "
            "match any model edges"
        )

    return selected_edges


def apply_edge_treatment(
    part: cq.Workplane,
    operation: dict,
    operation_number: int,
    feature_graph: FeatureGraph | None = None,
) -> cq.Workplane:
    """Apply a real chamfer or fillet feature to selected model edges."""
    if part is None:
        raise ValueError("Cannot apply an edge treatment before a solid exists")

    operation_type = operation["type"]
    edges = select_edges_for_target(
        part,
        operation["target"],
        operation_number,
        feature_graph=feature_graph,
    )
    edge_workplane = part.newObject(edges)

    if operation_type == "chamfer":
        distance = operation["distance"]
        validate_positive_number(distance, "Chamfer distance")
        return edge_workplane.chamfer(distance)

    if operation_type == "fillet":
        radius = operation["radius"]
        validate_positive_number(radius, "Fillet radius")
        return edge_workplane.fillet(radius)

    raise ValueError(
        f"Operation {operation_number}: unsupported edge treatment "
        f"'{operation_type}'"
    )


def apply_add_extrusion_face_tags(
    part: cq.Workplane,
    operation: dict,
) -> cq.Workplane:
    """Tag faces on an added extrusion when the operation has an id."""
    feature_id = operation.get("id")
    if not feature_id:
        return part

    default_face_tags = {
        "top": ">Z",
        "bottom": "<Z",
    }
    if operation["profile"] == "rectangle":
        default_face_tags.update(
            {
                "front": ">Y",
                "back": "<Y",
                "right": ">X",
                "left": "<X",
            }
        )

    face_tags = operation.get("face_tags", default_face_tags)
    return apply_face_tags(part, feature_id, face_tags)


def register_add_extrusion_references(
    feature_graph: FeatureGraph | None,
    part: cq.Workplane,
    operation: dict,
    target: str,
    operation_number: int,
    positions: list,
) -> None:
    """Remember feature references for a single added extrusion."""
    if feature_graph is None or not operation.get("id"):
        return

    target_workplane, _ = get_target_workplane(
        part,
        target,
        operation_number,
        prefer_virtual_side=True,
        feature_graph=feature_graph,
    )

    use_instances = len(positions) > 1
    for index, position in enumerate(positions, start=1):
        instance_name = None
        if use_instances:
            instance_name = f"inst{index:03d}"

        if operation.get("profile") == "rectangle":
            feature_graph.registry.register_rectangular_prism_faces(
                operation["id"],
                target_workplane.plane,
                operation["width"],
                operation["height"],
                operation["distance"],
                position,
                instance_name=instance_name,
                semantic_aliases=not use_instances,
            )
        else:
            reference_scope = operation["id"]
            if instance_name is not None:
                reference_scope = f"{operation['id']}.{instance_name}"

            reference_workplane = cq.Workplane(target_workplane.plane).pushPoints(
                [position]
            )
            reference_workplane = create_profile(
                reference_workplane,
                operation,
                operation_number,
            )
            reference_solid = reference_workplane.extrude(operation["distance"])
            feature_graph.registry.register_extruded_solid_references(
                feature_id=operation["id"],
                reference_scope=reference_scope,
                target_plane=target_workplane.plane,
                solid=reference_solid.val(),
                distance=operation["distance"],
                position=position,
                instance_name=instance_name,
                semantic_aliases=not use_instances,
            )


def apply_cut_operation(
    part: cq.Workplane,
    operation: dict,
    operation_number: int,
    feature_graph: FeatureGraph | None = None,
) -> cq.Workplane:
    """Apply a profile cut to an existing model."""
    if part is None:
        raise ValueError("Cannot cut before a solid has been created")

    target = operation["target"]
    depth = operation["depth"]

    positions = get_positions(operation, operation_number)
    positions = normalize_side_target_positions(part, target, positions)

    target_workplane, is_virtual_target = get_target_workplane(
        part,
        target,
        operation_number,
        feature_graph=feature_graph,
    )
    workplane = target_workplane.pushPoints(positions)
    workplane = create_profile(workplane, operation, operation_number)

    if is_virtual_target:
        bounding_box = part.val().BoundingBox()
        if depth == "through":
            tool_depth = max(
                bounding_box.xlen,
                bounding_box.ylen,
                bounding_box.zlen,
            ) * 2
        elif is_number(depth):
            validate_positive_number(depth, "Depth")
            tool_depth = depth
        else:
            raise ValueError(
                f"Operation {operation_number}: "
                f"unsupported cut depth: {depth}"
            )

        cutting_tool = workplane.extrude(-tool_depth)
        return keep_largest_connected_solid(part.cut(cutting_tool))

    if depth == "through":
        part = workplane.cutThruAll()
    elif is_number(depth):
        validate_positive_number(depth, "Depth")
        part = workplane.cutBlind(-depth)
    else:
        raise ValueError(
            f"Operation {operation_number}: "
            f"unsupported cut depth: {depth}"
        )

    return keep_largest_connected_solid(part)


def apply_add_extrusion(
    part: cq.Workplane,
    operation: dict,
    operation_number: int,
    feature_graph: FeatureGraph | None = None,
) -> cq.Workplane:
    """Add an extrusion of a sketch to an existing model."""
    if part is None:
        raise ValueError("Cannot add before a solid has been created")

    target = operation["target"]
    distance = operation["distance"]
    positions = get_positions(operation, operation_number)
    positions = normalize_side_target_positions(part, target, positions)

    validate_positive_number(distance, "Distance")
    target_workplane, is_virtual_target = get_target_workplane(
        part,
        target,
        operation_number,
        prefer_virtual_side=True,
        feature_graph=feature_graph,
    )

    if is_virtual_target:
        last_result = part
        for position_factor in VIRTUAL_TARGET_POSITION_FACTORS:
            retry_positions = scale_positions_toward_origin(
                positions,
                position_factor,
            )
            target_workplane, _ = get_target_workplane(
                part,
                target,
                operation_number,
                prefer_virtual_side=True,
                feature_graph=feature_graph,
            )
            workplane = target_workplane.pushPoints(retry_positions)
            workplane = create_profile(
                workplane,
                operation,
                operation_number,
            )
            extrusion_tool = workplane.extrude(distance)
            result = part.union(extrusion_tool)

            if len(result.solids().vals()) == 1:
                register_add_extrusion_references(
                    feature_graph,
                    part,
                    operation,
                    target,
                    operation_number,
                    retry_positions,
                )
                return apply_add_extrusion_face_tags(result, operation)

            last_result = result

        return apply_add_extrusion_face_tags(last_result, operation)

    workplane = target_workplane.pushPoints(positions)
    workplane = create_profile(workplane, operation, operation_number)

    result = workplane.extrude(distance)
    register_add_extrusion_references(
        feature_graph,
        part,
        operation,
        target,
        operation_number,
        positions,
    )
    return apply_add_extrusion_face_tags(result, operation)


def validate_axis_point(axis_point: list, point_name: str) -> tuple:
    """Validate a 2D or 3D axis point and return it as a 3D tuple."""
    if len(axis_point) not in (2, 3):
        raise ValueError(f"{point_name} must contain two or three numbers")

    for coordinate in axis_point:
        if not is_number(coordinate):
            raise ValueError(
                f"{point_name} coordinates must be integers or floats"
            )

    if len(axis_point) == 2:
        return (axis_point[0], axis_point[1], 0)

    return tuple(axis_point)


def project_2d_point_to_axis(point: list, axis_start: tuple, axis_end: tuple) -> list:
    """Project a 2D point onto the 2D revolve axis line."""
    point_x = point[0]
    point_y = point[1]
    start_x = axis_start[0]
    start_y = axis_start[1]
    axis_x = axis_end[0] - start_x
    axis_y = axis_end[1] - start_y
    axis_length_squared = axis_x**2 + axis_y**2

    if axis_length_squared == 0:
        raise ValueError("Revolve axis start and end cannot be the same")

    point_axis_x = point_x - start_x
    point_axis_y = point_y - start_y
    axis_fraction = (
        point_axis_x * axis_x + point_axis_y * axis_y
    ) / axis_length_squared

    return [
        start_x + axis_fraction * axis_x,
        start_y + axis_fraction * axis_y,
    ]


def scale_revolve_positions_toward_axis(
    positions: list,
    axis_start: tuple,
    axis_end: tuple,
    factor: float,
) -> list:
    """Move revolve feature positions toward the revolve axis."""
    scaled_positions = []

    for position in positions:
        projected_position = project_2d_point_to_axis(
            position,
            axis_start,
            axis_end,
        )
        scaled_positions.append(
            [
                projected_position[0]
                + (position[0] - projected_position[0]) * factor,
                projected_position[1]
                + (position[1] - projected_position[1]) * factor,
            ]
        )

    return scaled_positions


def build_revolve_tool(
    operation: dict,
    operation_number: int,
) -> cq.Workplane:
    """Build a temporary solid by revolving a profile around an axis."""
    plane = operation["plane"]
    angle = operation["angle"]
    axis_start = validate_axis_point(operation["axis_start"], "Axis start")
    axis_end = validate_axis_point(operation["axis_end"], "Axis end")
    positions = get_positions(operation, operation_number)

    validate_positive_number(angle, "Revolve angle")
    if angle > 360:
        raise ValueError("Revolve angle cannot be greater than 360")
    if axis_start == axis_end:
        raise ValueError("Revolve axis start and end cannot be the same")

    workplane = cq.Workplane(plane).pushPoints(positions)
    workplane = create_profile(workplane, operation, operation_number)
    return workplane.revolve(
        angleDegrees=angle,
        axisStart=axis_start,
        axisEnd=axis_end,
    )


def register_revolve_references(
    feature_graph: FeatureGraph | None,
    operation: dict,
    revolve_tool: cq.Workplane,
) -> None:
    """Remember feature references created by a revolved operation."""
    feature_id = operation.get("id")
    if feature_graph is None or not feature_id:
        return

    axis_start = validate_axis_point(operation["axis_start"], "Axis start")
    axis_end = validate_axis_point(operation["axis_end"], "Axis end")
    feature_graph.registry.register_revolved_solid_references(
        feature_id=feature_id,
        reference_scope=feature_id,
        workplane=cq.Plane.named(operation["plane"]),
        solid=revolve_tool.val(),
        axis_start=axis_start,
        axis_end=axis_end,
        angle=operation["angle"],
    )


def build_revolve(
    operation: dict,
    operation_number: int,
    feature_graph: FeatureGraph | None = None,
) -> cq.Workplane:
    """Build a solid by revolving a profile around an axis."""
    feature_id = operation["id"]
    part = build_revolve_tool(operation, operation_number)
    register_revolve_references(feature_graph, operation, part)

    default_face_tags = {}
    if operation["profile"] == "rectangle":
        default_face_tags = {
            "front": ">Y",
            "back": "<Y",
        }

    face_tags = operation.get("face_tags", default_face_tags)
    return apply_face_tags(part, feature_id, face_tags)


def apply_add_revolve(
    part: cq.Workplane,
    operation: dict,
    operation_number: int,
    feature_graph: FeatureGraph | None = None,
) -> cq.Workplane:
    """Add a revolve of a sketch to an existing model."""
    if part is None:
        raise ValueError("Cannot add before a solid has been created")

    axis_start = validate_axis_point(operation["axis_start"], "Axis start")
    axis_end = validate_axis_point(operation["axis_end"], "Axis end")
    positions = get_positions(operation, operation_number)
    last_result = part

    for position_factor in ADD_REVOLVE_POSITION_FACTORS:
        retry_operation = operation.copy()
        retry_operation["positions"] = scale_revolve_positions_toward_axis(
            positions,
            axis_start,
            axis_end,
            position_factor,
        )

        revolve_tool = build_revolve_tool(retry_operation, operation_number)
        result = part.union(revolve_tool)

        if len(result.solids().vals()) == 1:
            register_revolve_references(
                feature_graph,
                retry_operation,
                revolve_tool,
            )
            return result

        last_result = result

    return last_result


def apply_cut_revolve(
    part: cq.Workplane,
    operation: dict,
    operation_number: int,
) -> cq.Workplane:
    """Cut a revolve of a sketch from an existing model."""
    if part is None:
        raise ValueError("Cannot cut before a solid has been created")

    revolve_tool = build_revolve_tool(operation, operation_number)
    return keep_largest_connected_solid(part.cut(revolve_tool))


def validate_final_model(part: cq.Workplane) -> None:
    """Require one connected, geometrically valid solid."""
    solids = part.solids().vals()
    solid_count = len(solids)

    if solid_count != 1:
        raise ValueError(
            f"Expected one connected solid, but generated {solid_count}"
        )

    solid = solids[0]
    if not solid.isValid():
        raise ValueError("Generated geometry is invalid")


def validate_operation_order(operations: list) -> None:
    """Require exactly one base operation, and require it to be first."""
    if len(operations) == 0:
        raise ValueError("At least one operation is required")

    first_operation_type = operations[0].get("type")
    if first_operation_type not in BASE_OPERATION_TYPES:
        raise ValueError(
            "Operation 1 must create the base solid using type "
            "'extrude' or 'revolve'"
        )

    base_operation_numbers = [
        operation_number
        for operation_number, operation in enumerate(operations, start=1)
        if operation.get("type") in BASE_OPERATION_TYPES
    ]

    if len(base_operation_numbers) > 1:
        extra_base_operation = base_operation_numbers[1]
        raise ValueError(
            f"Operation {extra_base_operation}: only one base operation "
            "is allowed"
        )


def build_model_with_graph(model_data: dict) -> tuple[cq.Workplane, FeatureGraph]:
    """Build a CAD model and return its editable feature graph."""
    operations = model_data["operations"]
    validate_operation_order(operations)

    part = None
    feature_graph = FeatureGraph()

    for operation_number, operation in enumerate(operations, start=1):
        operation_type = operation["type"]
        feature_node = feature_graph.add_feature(
            operation,
            operation_number,
        )

        if operation_type == "extrude":
            part = build_base_extrusion(
                operation,
                operation_number,
                feature_graph=feature_graph,
            )
        elif operation_type == "revolve":
            part = build_revolve(
                operation,
                operation_number,
                feature_graph=feature_graph,
            )
        elif operation_type == "cut":
            part = apply_cut_operation(
                part,
                operation,
                operation_number,
                feature_graph=feature_graph,
            )
        elif operation_type == "add_extrude":
            part = apply_add_extrusion(
                part,
                operation,
                operation_number,
                feature_graph=feature_graph,
            )
        elif operation_type == "add_revolve":
            part = apply_add_revolve(
                part,
                operation,
                operation_number,
                feature_graph=feature_graph,
            )
        elif operation_type == "cut_revolve":
            part = apply_cut_revolve(part, operation, operation_number)
        elif operation_type in {"chamfer", "fillet"}:
            part = apply_edge_treatment(
                part,
                operation,
                operation_number,
                feature_graph=feature_graph,
            )
        else:
            raise ValueError(
                f"Operation {operation_number}: "
                f"unsupported operation type: {operation_type}"
            )

        feature_graph.refresh_created_references(feature_node.id)

    if part is None:
        raise ValueError("No valid operations were processed to create a part.")

    validate_final_model(part)

    return part, feature_graph


def build_model(model_data: dict) -> cq.Workplane:
    """Process an ordered operation list and return the completed CAD model."""
    part, _ = build_model_with_graph(model_data)
    return part
