"""Report native SolidWorks controls for editable-model parameters."""

from prompt2cad.editable_model import EditableModelDocument
from prompt2cad.editable_model import EditableParameter
from prompt2cad.editable_model import model_data_to_editable_document
from prompt2cad.solidworks_replay import SolidWorksReplayPlan


def native_parameter_coverage(
    model_data: dict,
    plan: SolidWorksReplayPlan,
    *,
    document: EditableModelDocument | None = None,
) -> dict:
    """Classify native controls for every numeric source parameter.

    Named bindings support stable automated mutation. Zero placement and sketch
    coordinates instead use geometric relations because CAD systems do not
    accept a useful zero-length driving dimension. Redundant reference geometry
    is retained by the native sketch but reported separately from controls.
    Remaining IDs are unsupported so new profile families cannot silently
    reduce coverage.
    """
    if document is None:
        document = model_data_to_editable_document(model_data)
    source_parameters = {
        parameter.id: parameter
        for feature in document.features
        for parameter in feature.parameters
        if parameter.driving
        and isinstance(parameter.value, (int, float))
        and not isinstance(parameter.value, bool)
    }
    source_parameter_ids = set(source_parameters)
    binding_ids = {
        binding["parameter_id"]
        for feature in plan.features
        for binding in feature.parameter_bindings
    }
    restricted_bindings = {
        binding["parameter_id"]: binding
        for feature in plan.features
        for binding in feature.parameter_bindings
        if binding.get("mutation_mode") == "absolute_same_side"
    }
    bound_source_ids = source_parameter_ids & binding_ids
    relation_controlled_ids = {
        parameter_id
        for parameter_id, parameter in source_parameters.items()
        if parameter.role in {"placement", "sketch_coordinate"}
        and abs(float(parameter.value)) <= 1e-12
        and parameter_id not in binding_ids
    }
    derived_geometry_ids = {
        parameter_id
        for parameter_id, parameter in source_parameters.items()
        if _is_derived_reference_geometry(parameter)
        and parameter_id not in binding_ids
    }
    unsupported_ids = (
        source_parameter_ids
        - binding_ids
        - relation_controlled_ids
        - derived_geometry_ids
    )
    unsupported_parameters = [
        {
            "parameter_id": parameter_id,
            "reason": _unsupported_parameter_reason(
                source_parameters[parameter_id]
            ),
        }
        for parameter_id in sorted(unsupported_ids)
    ]
    restricted_parameter_ids = sorted(
        source_parameter_ids & set(restricted_bindings)
    )
    restricted_parameters = [
        {
            "parameter_id": parameter_id,
            "reason": (
                "The native distance control can change this coordinate on "
                "its current side of the sketch origin. Crossing or landing "
                "on the origin requires regenerating the SolidWorks package."
            ),
        }
        for parameter_id in restricted_parameter_ids
    ]
    derived_geometry_parameters = [
        {
            "parameter_id": parameter_id,
            "reason": _derived_geometry_reason(source_parameters[parameter_id]),
        }
        for parameter_id in sorted(derived_geometry_ids)
    ]
    controlled_count = len(bound_source_ids) + len(relation_controlled_ids)
    represented_count = controlled_count + len(derived_geometry_ids)
    return {
        "numeric_source_count": len(source_parameter_ids),
        "bound_count": len(bound_source_ids),
        "coverage_ratio": (
            len(bound_source_ids) / len(source_parameter_ids)
            if source_parameter_ids
            else 1.0
        ),
        "relation_controlled_count": len(relation_controlled_ids),
        "controlled_count": controlled_count,
        "control_coverage_ratio": (
            controlled_count / len(source_parameter_ids)
            if source_parameter_ids
            else 1.0
        ),
        "derived_geometry_count": len(derived_geometry_ids),
        "derived_geometry_parameter_ids": sorted(derived_geometry_ids),
        "derived_geometry_parameters": derived_geometry_parameters,
        "represented_count": represented_count,
        "representation_coverage_ratio": (
            represented_count / len(source_parameter_ids)
            if source_parameter_ids
            else 1.0
        ),
        "unbound_parameter_ids": sorted(source_parameter_ids - binding_ids),
        "relation_controlled_parameter_ids": sorted(
            relation_controlled_ids
        ),
        "unsupported_parameter_ids": sorted(unsupported_ids),
        "unsupported_parameters": unsupported_parameters,
        "restricted_parameter_ids": restricted_parameter_ids,
        "restricted_parameters": restricted_parameters,
        "native_only_parameter_ids": sorted(binding_ids - source_parameter_ids),
    }


def _is_derived_reference_geometry(parameter: EditableParameter) -> bool:
    """Identify redundant revolve-axis endpoint coordinates."""
    return (
        parameter.role == "reference_geometry"
        and len(parameter.source_path) >= 2
        and parameter.source_path[-2] in {"axis_start", "axis_end"}
    )


def _derived_geometry_reason(parameter: EditableParameter) -> str:
    """Explain why retained reference geometry is not a driving control."""
    return (
        "The native construction axis retains this endpoint, but four endpoint "
        "coordinates redundantly encode one line. Edit the construction line "
        "manually or regenerate from a future canonical axis control."
    )


def _unsupported_parameter_reason(parameter: EditableParameter) -> str:
    """Explain a native mutation gap without implying lost CAD history."""
    if parameter.value_type == "count" and parameter.id.endswith(
        ".sketch.sides"
    ):
        return (
            "SolidWorks fixes regular-polygon topology when the sketch is "
            "created. Change the side count by editing or recreating that "
            "native polygon sketch."
        )
    if parameter.role == "placement":
        return (
            "The native sketch retains this placement, but no stable named "
            "automated mutation control is available for it yet."
        )
    if parameter.role == "sketch_coordinate":
        return (
            "The native sketch retains this coordinate, but no stable named "
            "automated mutation control is available for it yet."
        )
    return "No stable automated SolidWorks mutation binding is available yet."
