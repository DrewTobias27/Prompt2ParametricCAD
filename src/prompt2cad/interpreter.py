"""Interpret structured CAD operations and build a CadQuery model."""

import cadquery as cq


def build_base_extrusion(
    operation: dict,
    operation_number: int,
) -> cq.Workplane:
    """Build the initial rectangular solid and tag its top workplane."""
    feature_id = operation["id"]
    plane = operation["plane"]
    profile = operation["profile"]
    width = operation["width"]
    height = operation["height"]
    distance = operation["distance"]

    if width <= 0:
        raise ValueError("Width must be greater than zero")
    if height <= 0:
        raise ValueError("Height must be greater than zero")
    if distance <= 0:
        raise ValueError("Distance must be greater than zero")

    if profile == "rectangle":
        part = cq.Workplane(plane).rect(width, height).extrude(distance)
    else:
        raise ValueError(
            f"Operation {operation_number}: "
            f"unsupported profile for extrude: {profile}"
        )

    part = part.faces(">Z").workplane().tag(f"{feature_id}.top")
    return part.end().end()


def get_positions(operation: dict) -> list:
    """Return and validate one or more profile positions."""
    if "positions" in operation:
        positions = operation["positions"]
    else:
        positions = [[operation["x"], operation["y"]]]

    if len(positions) == 0:
        raise ValueError("At least one profile position must be defined")

    for position in positions:
        if len(position) != 2:
            raise ValueError(
                "Each profile position must contain exactly x and y"
            )

        x = position[0]
        y = position[1]
        if not isinstance(x, (int, float)):
            raise ValueError("Profile x position must be an integer or float")
        if not isinstance(y, (int, float)):
            raise ValueError("Profile y position must be an integer or float")
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
    """Apply one circular or rectangular cut to an existing model."""
    if part is None:
        raise ValueError("Cannot cut before a solid has been created")

    target = operation["target"]
    depth = operation["depth"]

    positions = get_positions(operation)

    target_workplane = part.workplaneFromTagged(target)
    workplane = target_workplane.pushPoints(positions)
    workplane = create_profile(workplane, operation, operation_number)

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
    positions = get_positions(operation)

    if distance <= 0:
        raise ValueError("Distance must be greater than zero")

    target_workplane = part.workplaneFromTagged(target)
    workplane = target_workplane.pushPoints(positions)
    workplane = create_profile(workplane, operation, operation_number)

    return workplane.extrude(distance)


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


def build_model(model_data: dict) -> cq.Workplane:
    """Process an ordered operation list and return the completed CAD model."""
    operations = model_data["operations"]
    part = None

    for operation_number, operation in enumerate(operations, start=1):
        operation_type = operation["type"]

        if operation_type == "extrude":
            part = build_base_extrusion(operation, operation_number)
        elif operation_type == "cut":
            part = apply_cut_operation(part, operation, operation_number)
        elif operation_type == "add_extrude":
            part = apply_add_extrusion(part, operation, operation_number)
        else:
            raise ValueError(
                f"Operation {operation_number}: "
                f"unsupported operation type: {operation_type}"
            )

    if part is None:
        raise ValueError("No valid operations were processed to create a part.")

    validate_final_model(part)

    return part
