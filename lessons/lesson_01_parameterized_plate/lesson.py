import cadquery as cq
import json

with open("plate_parameters.json", "r") as file:
	plate_parameters = json.load(file)

plate_name = plate_parameters.pop("name")


small_plate_parameters = {
    "length": 50,
    "width": 40,
    "thickness": 4,
    "hole_dia": 6,
    "hole_x_spc": 30,
    "hole_y_spc": 20,
}



def build_plate(length, width, thickness, hole_dia, hole_x_spc, hole_y_spc):
    hole_rad = hole_dia / 2

    if hole_dia <= 0:
        raise ValueError("hole dia is less than or equal to 0")
    if hole_x_spc / 2 + hole_rad >= length / 2:
        raise ValueError("Holes extend beyond the X plate edge")
    if hole_y_spc / 2 + hole_rad >= width / 2:
        raise ValueError("Holes extend beyond the Y plate edge")

    part = cq.Workplane("XY")
    part = part.rect(length, width)
    part = part.extrude(thickness)

    part = part.faces(">Z")
    part = part.workplane()
    hole_positions = [
        (-hole_x_spc / 2, hole_y_spc / 2),
        (hole_x_spc / 2, hole_y_spc / 2),
        (hole_x_spc / 2, -hole_y_spc / 2),
        (-hole_x_spc / 2, -hole_y_spc / 2),
    ]
    part = part.pushPoints(hole_positions)
    part = part.hole(hole_dia)

    return part


part = build_plate(**plate_parameters)
cq.exporters.export(part, plate_name + ".step")

small_plate = build_plate(**small_plate_parameters)
cq.exporters.export(small_plate, "small_plate.step")


def report_part(part, name):
    print("Part name:", name)
    solid = part.val()
    print("Valid shape:", solid.isValid())
    print("Volume:", solid.Volume())
    box = solid.BoundingBox()
    print("x length:", box.xlen)
    print("y length:", box.ylen)
    print("z length:", box.zlen)


report_part(part, plate_name)
report_part(small_plate, "small plate")


