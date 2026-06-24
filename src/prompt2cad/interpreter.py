"""Interpret structured CAD operations and build a CadQuery model."""

import cadquery as cq


BASE_OPERATION_TYPES = {"extrude", "revolve"}


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
    return cq.Plane(
        origin=face["origin"],
        xDir=face["xDir"],
        normal=face["normal"],
    )


def get_target_workplane(
    part: cq.Workplane,
    target: str,
    operation_number: int,
) -> tuple[cq.Workplane, bool]:
    """Return a target workplane and whether it is a virtual fallback."""
    try:
        return get_tagged_workplane(part, target, operation_number), False
    except ValueError:
        virtual_plane = get_virtual_target_plane(
            part,
            target,
            operation_number,
        )
        return cq.Workplane(virtual_plane), True


def build_base_extrusion(
    operation: dict,
    operation_number: int,
) -> cq.Workplane:
    """Build the initial solid and tag its top workplane."""
    feature_id = operation["id"]
    plane = operation["plane"]
    distance = operation["distance"]

    if distance <= 0:
        raise ValueError("Distance must be greater than zero")

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
        if not isinstance(x, (int, float)):
            raise ValueError(
                f"Operation {operation_number}: "
                "profile x position must be an integer or float"
            )
        if not isinstance(y, (int, float)):
            raise ValueError(
                f"Operation {operation_number}: "
                "profile y position must be an integer or float"
            )
    return positions


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

        if width <= 0:
            raise ValueError("Width must be greater than zero")
        if height <= 0:
            raise ValueError("Height must be greater than zero")

        workplane = workplane.rect(width, height)
    elif profile == "circle":
        diameter = operation["diameter"]

        if diameter <= 0:
            raise ValueError("Diameter must be greater than zero")

        workplane = workplane.circle(diameter / 2)
    elif profile == "polygon":
        sides = operation["sides"]
        diameter = operation["diameter"]

        if not isinstance(sides, int) or isinstance(sides, bool):
            raise ValueError("Polygon sides must be an integer")
        if sides < 3:
            raise ValueError("Polygon must have at least three sides")
        if diameter <= 0:
            raise ValueError("Diameter must be greater than zero")

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
            if not isinstance(x, (int, float)):
                raise ValueError(
                    "Polyline x coordinate must be an integer or float"
                )
            if not isinstance(y, (int, float)):
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
        if not isinstance(start_x, (int, float)):
            raise ValueError(
                "Sketch start x coordinate must be an integer or float"
            )
        if not isinstance(start_y, (int, float)):
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
                if not isinstance(end_x, (int, float)):
                    raise ValueError(
                        "Sketch arc end x coordinate must be an integer or float"
                    )
                if not isinstance(end_y, (int, float)):
                    raise ValueError(
                        "Sketch arc end y coordinate must be an integer or float"
                    )
                endpoint = cq.Vector(end_x, end_y, 0)
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
                if not isinstance(end_x, (int, float)):
                    raise ValueError(
                        "Sketch arc end x coordinate must be an integer or float"
                    )
                if not isinstance(end_y, (int, float)):
                    raise ValueError(
                        "Sketch arc end y coordinate must be an integer or float"
                    )
                if not isinstance(through_x, (int, float)):
                    raise ValueError(
                        "Sketch arc through x coordinate must be an integer or float"
                    )
                if not isinstance(through_y, (int, float)):
                    raise ValueError(
                        "Sketch arc through y coordinate must be an integer or float"
                    )
                through_vector = cq.Vector(through_x, through_y, 0)
                endpoint = cq.Vector(end_x, end_y, 0)
                edge = cq.Edge.makeThreePointArc(current, through_vector, endpoint)
                edges.append(edge)
                current = endpoint

            else:
                raise ValueError(
                    f"Unsupported sketch segment type: {segment['type']}"
                )

        if current != start_vector:
            closing_edge = cq.Edge.makeLine(current, start_vector)
            edges.append(closing_edge)

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


def apply_cut_operation(
    part: cq.Workplane,
    operation: dict,
    operation_number: int,
) -> cq.Workplane:
    """Apply a profile cut to an existing model."""
    if part is None:
        raise ValueError("Cannot cut before a solid has been created")

    target = operation["target"]
    depth = operation["depth"]

    positions = get_positions(operation, operation_number)

    target_workplane, is_virtual_target = get_target_workplane(
        part,
        target,
        operation_number,
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
        elif isinstance(depth, (int, float)):
            if depth <= 0:
                raise ValueError("Depth must be greater than zero")
            tool_depth = depth
        else:
            raise ValueError(
                f"Operation {operation_number}: "
                f"unsupported cut depth: {depth}"
            )

        cutting_tool = workplane.extrude(-tool_depth)
        return part.cut(cutting_tool)

    if depth == "through":
        part = workplane.cutThruAll()
    elif isinstance(depth, (int, float)):
        if depth <= 0:
            raise ValueError("Depth must be greater than zero")
        part = workplane.cutBlind(-depth)
    else:
        raise ValueError(
            f"Operation {operation_number}: "
            f"unsupported cut depth: {depth}"
        )

    return part


def apply_add_extrusion(
    part: cq.Workplane,
    operation: dict,
    operation_number: int,
) -> cq.Workplane:
    """Add an extrusion of a sketch to an existing model."""
    if part is None:
        raise ValueError("Cannot add before a solid has been created")

    target = operation["target"]
    distance = operation["distance"]
    positions = get_positions(operation, operation_number)

    if distance <= 0:
        raise ValueError("Distance must be greater than zero")
    target_workplane, is_virtual_target = get_target_workplane(
        part,
        target,
        operation_number,
    )
    workplane = target_workplane.pushPoints(positions)
    workplane = create_profile(workplane, operation, operation_number)

    if is_virtual_target:
        extrusion_tool = workplane.extrude(distance)
        return part.union(extrusion_tool)

    return workplane.extrude(distance)


def validate_axis_point(axis_point: list, point_name: str) -> tuple:
    """Validate a 2D or 3D axis point and return it as a 3D tuple."""
    if len(axis_point) not in (2, 3):
        raise ValueError(f"{point_name} must contain two or three numbers")

    for coordinate in axis_point:
        if not isinstance(coordinate, (int, float)):
            raise ValueError(
                f"{point_name} coordinates must be integers or floats"
            )

    if len(axis_point) == 2:
        return (axis_point[0], axis_point[1], 0)

    return tuple(axis_point)


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

    if not isinstance(angle, (int, float)):
        raise ValueError("Revolve angle must be an integer or float")
    if angle <= 0:
        raise ValueError("Revolve angle must be greater than zero")
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


def build_revolve(
    operation: dict,
    operation_number: int,
) -> cq.Workplane:
    """Build a solid by revolving a profile around an axis."""
    feature_id = operation["id"]
    part = build_revolve_tool(operation, operation_number)

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
) -> cq.Workplane:
    """Add a revolve of a sketch to an existing model."""
    if part is None:
        raise ValueError("Cannot add before a solid has been created")

    revolve_tool = build_revolve_tool(operation, operation_number)
    return part.union(revolve_tool)


def apply_cut_revolve(
    part: cq.Workplane,
    operation: dict,
    operation_number: int,
) -> cq.Workplane:
    """Cut a revolve of a sketch from an existing model."""
    if part is None:
        raise ValueError("Cannot cut before a solid has been created")

    revolve_tool = build_revolve_tool(operation, operation_number)
    return part.cut(revolve_tool)


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


def build_model(model_data: dict) -> cq.Workplane:
    """Process an ordered operation list and return the completed CAD model."""
    operations = model_data["operations"]
    validate_operation_order(operations)

    part = None

    for operation_number, operation in enumerate(operations, start=1):
        operation_type = operation["type"]

        if operation_type == "extrude":
            part = build_base_extrusion(operation, operation_number)
        elif operation_type == "revolve":
            part = build_revolve(operation, operation_number)
        elif operation_type == "cut":
            part = apply_cut_operation(part, operation, operation_number)
        elif operation_type == "add_extrude":
            part = apply_add_extrusion(part, operation, operation_number)
        elif operation_type == "add_revolve":
            part = apply_add_revolve(part, operation, operation_number)
        elif operation_type == "cut_revolve":
            part = apply_cut_revolve(part, operation, operation_number)
        else:
            raise ValueError(
                f"Operation {operation_number}: "
                f"unsupported operation type: {operation_type}"
            )

    if part is None:
        raise ValueError("No valid operations were processed to create a part.")

    validate_final_model(part)

    return part
