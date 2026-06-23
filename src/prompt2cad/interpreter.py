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


def apply_cut_operation(
    part: cq.Workplane,
    operation: dict,
    operation_number: int,
) -> cq.Workplane:
    """Apply one circular or rectangular cut to an existing model."""
    if part is None:
        raise ValueError("Cannot cut before a solid has been created")

    target = operation["target"]
    profile = operation["profile"]
    depth = operation["depth"]

    if profile == "circle":
        diameter = operation["diameter"]
        positions = operation["positions"]

        if len(positions) == 0:
            raise ValueError("Hole positions must be defined")

        for position in positions:
            if len(position) != 2:
                raise ValueError(
                    "Each hole position must contain exactly x and y"
                )

            x = position[0]
            y = position[1]
            if not isinstance(x, (int, float)):
                raise ValueError("Hole x position must be an integer or float")
            if not isinstance(y, (int, float)):
                raise ValueError("Hole y position must be an integer or float")

        if diameter <= 0:
            raise ValueError("Diameter must be greater than zero")

        part = part.workplaneFromTagged(target)
        part = part.pushPoints(positions)

        if depth == "through":
            part = part.hole(diameter)
        elif isinstance(depth, (int, float)):
            if depth <= 0:
                raise ValueError("Depth must be greater than zero")
            part = part.circle(diameter / 2)
            part = part.cutBlind(-depth)
        else:
            raise ValueError(
                f"Operation {operation_number}: "
                f"unsupported circular cut depth: {depth}"
            )

    elif profile == "rectangle":
        width = operation["width"]
        height = operation["height"]
        x = operation["x"]
        y = operation["y"]

        if width <= 0:
            raise ValueError("Width must be greater than zero")
        if height <= 0:
            raise ValueError("Height must be greater than zero")

        part = part.workplaneFromTagged(target)
        part = part.center(x, y)
        part = part.rect(width, height)

        if depth == "through":
            part = part.cutThruAll()
        elif isinstance(depth, (int, float)):
            if depth <= 0:
                raise ValueError("Depth must be greater than zero")
            part = part.cutBlind(-depth)
        else:
            raise ValueError(
                f"Operation {operation_number}: "
                f"unsupported rectangular cut depth: {depth}"
            )

    else:
        raise ValueError(
            f"Operation {operation_number}: "
            f"unsupported profile for cut: {profile}"
        )

    return part


def apply_add_extrusion(
    part: cq.Workplane,
    operation: dict,
    operation_number: int,
) -> cq.Workplane:
    """Add one circular or rectangular extrusion to an existing model."""
    if part is None:
        raise ValueError("Cannot add before a solid has been created")

    target = operation["target"]
    profile = operation["profile"]
    x = operation["x"]
    y = operation["y"]
    distance = operation["distance"]

    if distance <= 0:
        raise ValueError("Distance must be greater than zero")

    part = part.workplaneFromTagged(target)
    part = part.center(x, y)

    if profile == "rectangle":
        width = operation["width"]
        height = operation["height"]

        if width <= 0:
            raise ValueError("Width must be greater than zero")
        if height <= 0:
            raise ValueError("Height must be greater than zero")

        part = part.rect(width, height)

    elif profile == "circle":
        diameter = operation["diameter"]

        if diameter <= 0:
            raise ValueError("Diameter must be greater than zero")

        part = part.circle(diameter / 2)

    else:
        raise ValueError(
            f"Operation {operation_number}: "
            f"unsupported profile for add_extrude: {profile}"
        )

    return part.extrude(distance)


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
