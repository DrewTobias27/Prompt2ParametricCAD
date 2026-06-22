import cadquery as cq
import json

with open("part_operations_4.json", "r") as file:
    model_data = json.load(file)

model_name = model_data["name"]
operations = model_data["operations"]
print(model_name)
print(operations)

part = None
output_filename = model_name + ".step"

try:
    for operation_number, operation in enumerate(operations, start=1):
        operation_type = operation["type"]
        print(f"Processing operation {operation_number}: {operation_type}")
        print(operation)

        if operation_type == "extrude":
            plane = operation["plane"]
            profile = operation["profile"]
            width = operation["width"]
            height = operation["height"]
            distance = operation["distance"]
            feature_id = operation["id"]
            
            if width <= 0:
                raise ValueError("Width must be greater than zero")
            if height <= 0:
                raise ValueError("Height must be greater than zero")
            if distance <= 0:
                raise ValueError("Distance must be greater than zero")

            if profile == "rectangle":
                part = cq.Workplane(plane)
                part = part.rect(width, height)
                part = part.extrude(distance)
            else:
                raise ValueError(
                    f"Operation {operation_number}: "
                    f"unsupported profile for extrude: {profile}"
                )
            part = part.faces(">Z")
            part = part.workplane()
            part = part.tag(f"{feature_id}.top")
        elif operation_type == "cut":
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
                        raise ValueError(
                            "Hole x position must be an integer or float"
                        )
                    if not isinstance(y, (int, float)):
                        raise ValueError(
                            "Hole y position must be an integer or float"
                        )

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
        elif operation_type == "add_extrude":
            if part is None:
                raise ValueError("Cannot add before a solid has been created")
            target = operation["target"]
            profile = operation["profile"]
            x = operation["x"]
            y = operation["y"]
            distance = operation["distance"]
            part = part.workplaneFromTagged(target)
            part = part.center(x, y)
            if distance <= 0:
                raise ValueError("Distance must be greater than zero")
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
            part = part.extrude(distance)
        else:
            raise ValueError(
                f"Operation {operation_number}: "
                f"unsupported operation type: {operation_type}"
            )

    if part is None:
        raise ValueError("No solid has been created")

    solids = part.solids().vals()
    solid_count = len(solids)
    if solid_count != 1:
        raise ValueError(
            f"Expected one connected solid, but generated {solid_count}"
        )

    solid = part.val()
    if not solid.isValid():
        raise ValueError("Generated geometry is invalid")

    cq.exporters.export(part, output_filename)

except Exception as error:
    print("Generation failed:", error)
