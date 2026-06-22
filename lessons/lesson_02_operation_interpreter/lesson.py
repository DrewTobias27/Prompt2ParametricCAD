import cadquery as cq
import json

with open("operations.json", "r") as file:
    model_data = json.load(file)

model_name = model_data["name"]
operations = model_data["operations"]
print(model_name)
print(operations)

part = None
output_filename = model_name + ".step"

try:
    for operation in operations:
        operation_type = operation["type"]
        print(operation_type)
        print(operation)

        if operation_type == "extrude":
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
                part = cq.Workplane(plane)
                part = part.rect(width, height)
                part = part.extrude(distance)
            else:
                raise ValueError(f"Unsupported profile for extrude: {profile}")

        elif operation_type == "cut":
            if part is None:
                raise ValueError("Cannot cut before a solid has been created")

            target_face = operation["target_face"]
            profile = operation["profile"]
            diameter = operation["diameter"]
            x = operation["x"]
            y = operation["y"]
            depth = operation["depth"]

            if diameter <= 0:
                raise ValueError("Diameter must be greater than zero")

            if profile != "circle":
                raise ValueError(f"Unsupported profile for cut: {profile}")

            if depth == "through":
                part = part.faces(target_face)
                part = part.workplane()
                part = part.center(x, y)
                part = part.hole(diameter)
            else:
                raise ValueError(f"Unsupported cut depth: {depth}")
        elif operation_type == "add_extrude":
            if part is None:
                raise ValueError("Cannot add before a solid has been created")

            target_face = operation["target_face"]
            profile = operation["profile"]
            x = operation["x"]
            y = operation["y"]
            width = operation["width"]
            height = operation["height"]
            distance = operation["distance"]

            if width <= 0:
                raise ValueError("Width must be greater than zero")
            if height <= 0:
                raise ValueError("Height must be greater than zero")
            if distance <= 0:
                raise ValueError("Distance must be greater than zero")

            if profile != "rectangle":
                raise ValueError(f"Unsupported profile for add_extrude: {profile}")

            part = part.faces(target_face)
            part = part.workplane()
            part = part.center(x, y)
            part = part.rect(width, height)
            part = part.extrude(distance)

        else:
            raise ValueError(f"Unsupported operation type: {operation_type}")

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
