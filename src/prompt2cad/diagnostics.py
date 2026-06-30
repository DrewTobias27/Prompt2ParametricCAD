"""Diagnose generated CAD failures and suggest repair strategies."""

from prompt2cad.interpreter import build_model
from prompt2cad.relationships import check_relationships
from prompt2cad.schema import validate_model_data


GEOMETRY_TOLERANCE = 1e-6


def profile_bounds(operation: dict) -> tuple[float, float, float, float] | None:
    """Return local 2D bounding box for an operation profile."""
    profile = operation.get("profile")

    if profile == "rectangle":
        half_width = operation["width"] / 2
        half_height = operation["height"] / 2
        return (-half_width, -half_height, half_width, half_height)

    if profile == "circle":
        radius = operation["diameter"] / 2
        return (-radius, -radius, radius, radius)

    if profile == "polygon":
        radius = operation["diameter"] / 2
        return (-radius, -radius, radius, radius)

    if profile == "polyline":
        points = operation["points"]
        return points_bounds(points)

    if profile == "sketch":
        points = [operation["start"]]
        for segment in operation["segments"]:
            if segment["type"] == "line":
                points.append(segment["to"])
            elif segment["type"] == "arc":
                points.append(segment["through"])
                points.append(segment["to"])
        return points_bounds(points)

    return None


def points_bounds(points: list[list[float]]) -> tuple[float, float, float, float]:
    """Return bounding box around 2D points."""
    x_values = [point[0] for point in points]
    y_values = [point[1] for point in points]
    return (
        min(x_values),
        min(y_values),
        max(x_values),
        max(y_values),
    )


def translate_bounds(
    bounds: tuple[float, float, float, float],
    position: list[float],
) -> tuple[float, float, float, float]:
    """Move a local bounding box to an operation position."""
    min_x, min_y, max_x, max_y = bounds
    position_x, position_y = position
    return (
        min_x + position_x,
        min_y + position_y,
        max_x + position_x,
        max_y + position_y,
    )


def bounds_inside(
    inner_bounds: tuple[float, float, float, float],
    outer_bounds: tuple[float, float, float, float],
) -> bool:
    """Return whether one 2D bounding box is fully inside another."""
    inner_min_x, inner_min_y, inner_max_x, inner_max_y = inner_bounds
    outer_min_x, outer_min_y, outer_max_x, outer_max_y = outer_bounds
    return (
        inner_min_x >= outer_min_x - GEOMETRY_TOLERANCE
        and inner_min_y >= outer_min_y - GEOMETRY_TOLERANCE
        and inner_max_x <= outer_max_x + GEOMETRY_TOLERANCE
        and inner_max_y <= outer_max_y + GEOMETRY_TOLERANCE
    )


def operation_position_bounds(operation: dict) -> list[tuple[float, float, float, float]]:
    """Return global 2D bounds for every positioned instance of an operation."""
    bounds = profile_bounds(operation)
    if bounds is None:
        return []

    positions = operation.get("positions", [[0, 0]])
    return [translate_bounds(bounds, position) for position in positions]


def find_features_inside_through_cut(model_data: dict) -> dict | None:
    """Find later added features that sit fully inside an earlier through cut."""
    operations = model_data.get("operations", [])

    for cut_index, cut_operation in enumerate(operations):
        if (
            cut_operation.get("type") != "cut"
            or cut_operation.get("target") != "base.top"
            or cut_operation.get("depth") != "through"
        ):
            continue

        cut_bounds_list = operation_position_bounds(cut_operation)
        if not cut_bounds_list:
            continue

        for add_index, add_operation in enumerate(
            operations[cut_index + 1 :],
            start=cut_index + 1,
        ):
            if (
                add_operation.get("type") != "add_extrude"
                or add_operation.get("target") != "base.top"
            ):
                continue

            add_bounds_list = operation_position_bounds(add_operation)
            for cut_bounds in cut_bounds_list:
                for add_bounds in add_bounds_list:
                    if bounds_inside(add_bounds, cut_bounds):
                        return {
                            "cut_operation_number": cut_index + 1,
                            "added_operation_number": add_index + 1,
                            "cut_bounds": list(cut_bounds),
                            "added_bounds": list(add_bounds),
                        }

    return None


def diagnose_failure(model_data: dict | None, error_message: str) -> dict:
    """Return actionable repair guidance for a generated model failure."""
    if model_data is None:
        return {
            "passed": False,
            "failure_type": "generation_failed",
            "reason": error_message,
            "suggested_fixes": [
                "Generate a simpler CAD operation sequence.",
                "Prefer a single base feature followed by connected cuts or additions.",
            ],
        }

    if "Expected one connected solid" in error_message:
        disconnected_detail = find_features_inside_through_cut(model_data)
        if disconnected_detail is not None:
            return {
                "passed": False,
                "failure_type": "disconnected_solids_inside_through_cut",
                "reason": (
                    "A through cut created an opening, and a later added "
                    "feature is fully inside that removed region. The added "
                    "feature does not overlap the remaining base, so the model "
                    "becomes separate solids."
                ),
                "details": disconnected_detail,
                "suggested_fixes": [
                    "Add bridge tabs connecting the inner feature to the frame.",
                    "Use a shallow pocket or recess instead of a through cut.",
                    "Make the inner feature overlap the remaining frame if that matches the design intent.",
                ],
            }

        return {
            "passed": False,
            "failure_type": "disconnected_solids",
            "reason": (
                "The generated operations produced more than one separate "
                "solid. At least one added feature is floating, merely "
                "touching, or not sufficiently overlapping the existing part."
            ),
            "suggested_fixes": [
                "Move added features so they overlap existing solid material.",
                "Add connecting ribs, tabs, or bridges between separated regions.",
                "Use pockets or blind cuts instead of through cuts when adding material inside an opening.",
            ],
        }

    if "target" in error_message and "not found" in error_message:
        return {
            "passed": False,
            "failure_type": "missing_target_reference",
            "reason": (
                "An operation targets a face or feature reference that was not "
                "created earlier in the build sequence."
            ),
            "suggested_fixes": [
                "Use an existing target such as base.top, base.front, base.right, or a prior feature face.",
                "Create the parent feature before targeting one of its faces.",
            ],
        }

    if "Sketch" in error_message or "arc" in error_message:
        return {
            "passed": False,
            "failure_type": "invalid_sketch",
            "reason": (
                "A sketch profile could not be built into a valid closed "
                "profile, or one of its arc/line segments is geometrically invalid."
            ),
            "suggested_fixes": [
                "Use fewer sketch segments and keep the profile simple.",
                "Make sure the sketch forms one closed outline.",
                "Replace fragile arcs with simpler line segments when exact curvature is not necessary.",
            ],
        }

    return {
        "passed": False,
        "failure_type": "unknown_build_failure",
        "reason": error_message,
        "suggested_fixes": [
            "Simplify the operation sequence.",
            "Keep added features connected to existing solid material.",
            "Use conservative dimensions and positions that stay inside target faces.",
        ],
    }


def check_model_data(model_data: dict) -> dict:
    """Validate and build a model, returning pass/fail diagnostics."""
    try:
        validate_model_data(model_data)
        relationship_result = check_relationships(model_data)
        if not relationship_result["passed"]:
            return relationship_result

        build_model(model_data)
    except Exception as error:
        return diagnose_failure(model_data, str(error))

    return {
        "passed": True,
        "failure_type": None,
        "reason": "Model data validated and built successfully.",
        "suggested_fixes": [],
    }
