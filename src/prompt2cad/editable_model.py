"""Versioned editable-model representation and transactional parameter rebuilds.

The operation JSON remains Prompt2ParametricCAD's execution contract.  This
module adds a stable, UI- and exporter-facing view of those operations without
changing the working interpreter.  Every editable parameter points back to an
exact source path, so an edit can be applied to a copy, validated, and rebuilt
before it replaces a known-good model.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from math import isfinite
from typing import Any, TypeAlias

from prompt2cad.feature_graph import FeatureGraph
from prompt2cad.feature_graph import FeatureNode
from prompt2cad.interpreter import build_model_with_graph
from prompt2cad.operation_effects import evaluate_operation_effects
from prompt2cad.schema import validate_model_data


PathStep: TypeAlias = str | int
ParameterValue: TypeAlias = float | int | str | bool

EDITABLE_MODEL_FORMAT = "prompt2cad.editable-model"
EDITABLE_MODEL_VERSION = 1


@dataclass(frozen=True)
class EditableParameter:
    """One named driving value linked to an exact operation-JSON path."""

    id: str
    name: str
    role: str
    value_type: str
    value: ParameterValue
    unit: str | None
    source_path: tuple[PathStep, ...]
    aliases: tuple[str, ...] = field(default_factory=tuple)
    driving: bool = True

    def to_dict(self) -> dict:
        """Return a JSON-friendly parameter record."""
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "value_type": self.value_type,
            "value": self.value,
            "unit": self.unit,
            "source_path": list(self.source_path),
            "aliases": list(self.aliases),
            "driving": self.driving,
        }


@dataclass(frozen=True)
class EditableFeatureDefinition:
    """One ordered feature plus its editable and dependency information."""

    id: str
    operation_type: str
    operation_number: int
    build_predecessor_id: str | None
    parent_feature_ids: tuple[str, ...]
    target: str | None
    canonical_target: str | None
    support_reference: dict | None
    sketch: dict | None
    parameters: tuple[EditableParameter, ...]
    created_references: tuple[str, ...]
    representation_notes: tuple[str, ...]
    source_operation: dict

    @property
    def parameterization_complete(self) -> bool:
        """Return whether the feature has no known representation gaps."""
        return not self.representation_notes

    def to_dict(self) -> dict:
        """Return a JSON-friendly feature record."""
        return {
            "id": self.id,
            "operation_type": self.operation_type,
            "operation_number": self.operation_number,
            "build_predecessor_id": self.build_predecessor_id,
            "parent_feature_ids": list(self.parent_feature_ids),
            "target": self.target,
            "canonical_target": self.canonical_target,
            "support_reference": deepcopy(self.support_reference),
            "sketch": deepcopy(self.sketch),
            "parameters": [parameter.to_dict() for parameter in self.parameters],
            "created_references": list(self.created_references),
            "parameterization_complete": self.parameterization_complete,
            "representation_notes": list(self.representation_notes),
            "source_operation": deepcopy(self.source_operation),
        }


@dataclass(frozen=True)
class EditableModelDocument:
    """A versioned, rebuildable representation of one CAD feature history."""

    source_model_data: dict
    build_order: tuple[str, ...]
    features: tuple[EditableFeatureDefinition, ...]
    relationships: tuple[dict, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    format_name: str = EDITABLE_MODEL_FORMAT
    format_version: int = EDITABLE_MODEL_VERSION
    length_unit: str = "mm"
    angle_unit: str = "deg"

    @property
    def parameterization_complete(self) -> bool:
        """Return whether every feature has a fully explicit representation."""
        return all(feature.parameterization_complete for feature in self.features)

    def parameter(self, parameter_id: str) -> EditableParameter | None:
        """Return a parameter by its stable document ID."""
        for feature in self.features:
            for parameter in feature.parameters:
                if parameter.id == parameter_id:
                    return parameter

        return None

    def to_dict(self) -> dict:
        """Return a JSON-friendly editable document."""
        return {
            "format": self.format_name,
            "version": self.format_version,
            "units": {
                "length": self.length_unit,
                "angle": self.angle_unit,
            },
            "build_order": list(self.build_order),
            "features": [feature.to_dict() for feature in self.features],
            "relationships": deepcopy(list(self.relationships)),
            "warnings": list(self.warnings),
            "native_replay": {
                "parameterization_complete": self.parameterization_complete,
                "exporter_implemented": True,
                "adapter_status": "prototype",
                "eligibility_requires_replay_planning": True,
            },
            "source_model_data": deepcopy(self.source_model_data),
        }


def model_data_to_editable_document(model_data: dict) -> EditableModelDocument:
    """Validate and build model data, then return its editable document."""
    validate_model_data(model_data)
    _, feature_graph = build_model_with_graph(model_data)
    return _document_from_graph(model_data, feature_graph)


def rebuild_with_parameter_updates(
    document: EditableModelDocument,
    updates: dict[str, ParameterValue],
) -> tuple[Any, EditableModelDocument]:
    """Apply parameter updates transactionally and rebuild the CAD model.

    The source document is never mutated.  Validation or geometry failures are
    raised to the caller, leaving the previous document available as the last
    known-good revision.
    """
    updated_model_data = deepcopy(document.source_model_data)

    for parameter_id, value in updates.items():
        parameter = document.parameter(parameter_id)
        if parameter is None:
            raise ValueError(f"Unknown editable parameter: {parameter_id}")

        _validate_parameter_value(parameter, value)
        _set_source_value(updated_model_data, parameter.source_path, value)

    validate_model_data(updated_model_data)
    part, feature_graph = build_model_with_graph(updated_model_data)
    operation_effects = evaluate_operation_effects(updated_model_data)
    if not operation_effects["passed"]:
        raise ValueError(
            "Edited model failed operation-effect validation: "
            + " | ".join(operation_effects["failures"])
        )
    updated_document = _document_from_graph(updated_model_data, feature_graph)

    if updated_document.build_order != document.build_order:
        raise ValueError("Parameter update unexpectedly changed feature build order")

    return part, updated_document


def _document_from_graph(
    model_data: dict,
    feature_graph: FeatureGraph,
) -> EditableModelDocument:
    features: list[EditableFeatureDefinition] = []
    warnings: list[str] = []

    for build_index, feature_id in enumerate(feature_graph.build_order):
        feature_node = feature_graph.features[feature_id]
        canonical_target, support_reference = _support_reference_snapshot(
            feature_graph,
            feature_node,
        )
        notes = _representation_notes(feature_node, support_reference)
        warnings.extend(f"{feature_id}: {note}" for note in notes)

        parent_feature_ids = ()
        if feature_node.parent_feature_id is not None:
            parent_feature_ids = (feature_node.parent_feature_id,)

        sketch = None
        if feature_node.sketch is not None:
            sketch = feature_node.sketch.to_debug_dict()
            sketch["constraints"] = []

        features.append(
            EditableFeatureDefinition(
                id=feature_id,
                operation_type=feature_node.operation_type,
                operation_number=feature_node.operation_number,
                build_predecessor_id=(
                    feature_graph.build_order[build_index - 1]
                    if build_index > 0
                    else None
                ),
                parent_feature_ids=parent_feature_ids,
                target=feature_node.target,
                canonical_target=canonical_target,
                support_reference=support_reference,
                sketch=sketch,
                parameters=tuple(_editable_parameters(feature_node)),
                created_references=tuple(feature_node.created_references),
                representation_notes=tuple(notes),
                source_operation=deepcopy(feature_node.operation),
            )
        )

    warnings.extend(
        f"operation {warning.operation_number}: {warning.message}"
        for warning in feature_graph.validation_warnings
    )

    return EditableModelDocument(
        source_model_data=deepcopy(model_data),
        build_order=tuple(feature_graph.build_order),
        features=tuple(features),
        relationships=tuple(deepcopy(model_data.get("relationships", []))),
        warnings=tuple(warnings),
    )


def _support_reference_snapshot(
    feature_graph: FeatureGraph,
    feature_node: FeatureNode,
) -> tuple[str | None, dict | None]:
    target = feature_node.target
    if target is None:
        plane = feature_node.operation.get("plane")
        if plane is None:
            return None, None

        return None, {
            "kind": "datum_plane",
            "name": plane,
        }

    canonical_reference = feature_graph.registry.resolve_reference_name(target)
    if canonical_reference is not None:
        reference = feature_graph.registry.get_reference(canonical_reference)
        return canonical_reference, {
            "kind": "reference",
            "requested_name": target,
            "reference": reference.to_debug_dict(),
        }

    canonical_group = feature_graph.registry.resolve_reference_group_name(target)
    if canonical_group is not None:
        references = feature_graph.registry.get_reference_group(canonical_group) or []
        return canonical_group, {
            "kind": "reference_group",
            "requested_name": target,
            "canonical_name": canonical_group,
            "members": [reference.to_debug_dict() for reference in references],
        }

    return target, {
        "kind": "unresolved_reference",
        "requested_name": target,
    }


def _representation_notes(
    feature_node: FeatureNode,
    support_reference: dict | None,
) -> list[str]:
    notes: list[str] = []
    operation = feature_node.operation

    if not operation.get("id"):
        notes.append(
            "feature ID was generated from build order; assign an explicit ID "
            "before persistent editing or native replay"
        )

    profile = operation.get("profile")
    if profile in {"polyline", "sketch"}:
        notes.append(
            "sketch is coordinate-driven; geometric constraints are not yet "
            "represented"
        )

    positions = operation.get("positions", [])
    if len(positions) > 1 and not operation.get("pattern"):
        notes.append(
            "multiple instances are stored in one operation; native replay "
            "should separate the seed feature from its pattern"
        )

    if support_reference and support_reference.get("kind") == "unresolved_reference":
        notes.append(
            "target reference was not resolved to a registered semantic "
            "selection"
        )

    return notes


def _editable_parameters(feature_node: FeatureNode) -> list[EditableParameter]:
    operation = feature_node.operation
    operation_index = feature_node.operation_number - 1
    base_path: tuple[PathStep, ...] = ("operations", operation_index)
    parameters: list[EditableParameter] = []
    used_paths: set[tuple[PathStep, ...]] = set()

    def add_parameter(
        *,
        suffix: str,
        name: str,
        role: str,
        value_type: str,
        value: ParameterValue,
        unit: str | None,
        relative_path: tuple[PathStep, ...],
        aliases: tuple[str, ...] = (),
    ) -> None:
        source_path = base_path + relative_path
        if source_path in used_paths:
            return

        used_paths.add(source_path)
        parameters.append(
            EditableParameter(
                id=f"{feature_node.id}.{suffix}",
                name=name,
                role=role,
                value_type=value_type,
                value=value,
                unit=unit,
                source_path=source_path,
                aliases=aliases,
            )
        )

    if feature_node.sketch is not None:
        for dimension in feature_node.sketch.dimensions:
            source_field = next(
                (
                    alias
                    for alias in dimension.aliases
                    if alias in operation
                ),
                None,
            )
            if source_field is None:
                continue

            value_type = "count" if source_field == "sides" else "length"
            add_parameter(
                suffix=f"sketch.{source_field}",
                name=_display_name(source_field),
                role="sketch_dimension",
                value_type=value_type,
                value=operation[source_field],
                unit=None if value_type == "count" else "mm",
                relative_path=(source_field,),
                aliases=tuple(dimension.aliases),
            )

    _add_coordinate_geometry_parameters(operation, add_parameter)

    for field_name in (
        "distance",
        "attachment_depth",
        "depth",
        "angle",
        "radius",
    ):
        if field_name not in operation:
            continue

        value_type = {
            "distance": "length",
            "attachment_depth": "length",
            "depth": "end_condition",
            "angle": "angle",
            "radius": "length",
        }[field_name]
        unit = "deg" if value_type == "angle" else "mm"
        add_parameter(
            suffix=f"feature.{field_name}",
            name=_feature_control_name(feature_node.operation_type, field_name),
            role="feature_control",
            value_type=value_type,
            value=operation[field_name],
            unit=unit,
            relative_path=(field_name,),
        )

    for field_name in ("diameter", "countersink_diameter"):
        if field_name not in operation:
            continue

        add_parameter(
            suffix=f"feature.{field_name}",
            name=_display_name(field_name),
            role="feature_control",
            value_type="length",
            value=operation[field_name],
            unit="mm",
            relative_path=(field_name,),
        )

    for position_index, position in enumerate(operation.get("positions", [])):
        for coordinate_index, axis_name in enumerate(("x", "y")):
            add_parameter(
                suffix=(
                    f"placement.inst{position_index + 1:03d}.{axis_name}"
                ),
                name=(
                    f"Instance {position_index + 1} position "
                    f"{axis_name.upper()}"
                ),
                role="placement",
                value_type="coordinate",
                value=position[coordinate_index],
                unit="mm",
                relative_path=("positions", position_index, coordinate_index),
            )

    for axis_field in ("axis_start", "axis_end"):
        if axis_field not in operation:
            continue

        for coordinate_index, axis_name in enumerate(("x", "y")):
            add_parameter(
                suffix=f"reference.{axis_field}.{axis_name}",
                name=f"{_display_name(axis_field)} {axis_name.upper()}",
                role="reference_geometry",
                value_type="coordinate",
                value=operation[axis_field][coordinate_index],
                unit="mm",
                relative_path=(axis_field, coordinate_index),
            )

    return parameters


def _add_coordinate_geometry_parameters(operation: dict, add_parameter) -> None:
    for point_index, point in enumerate(operation.get("points", [])):
        for coordinate_index, axis_name in enumerate(("x", "y")):
            add_parameter(
                suffix=f"sketch.point{point_index + 1:03d}.{axis_name}",
                name=f"Profile point {point_index + 1} {axis_name.upper()}",
                role="sketch_coordinate",
                value_type="coordinate",
                value=point[coordinate_index],
                unit="mm",
                relative_path=("points", point_index, coordinate_index),
            )

    if "start" in operation:
        for coordinate_index, axis_name in enumerate(("x", "y")):
            add_parameter(
                suffix=f"sketch.start.{axis_name}",
                name=f"Sketch start {axis_name.upper()}",
                role="sketch_coordinate",
                value_type="coordinate",
                value=operation["start"][coordinate_index],
                unit="mm",
                relative_path=("start", coordinate_index),
            )

    for segment_index, segment in enumerate(operation.get("segments", [])):
        for point_name in ("through", "to"):
            if point_name not in segment:
                continue

            for coordinate_index, axis_name in enumerate(("x", "y")):
                add_parameter(
                    suffix=(
                        f"sketch.segment{segment_index + 1:03d}."
                        f"{point_name}.{axis_name}"
                    ),
                    name=(
                        f"Segment {segment_index + 1} "
                        f"{_display_name(point_name)} {axis_name.upper()}"
                    ),
                    role="sketch_coordinate",
                    value_type="coordinate",
                    value=segment[point_name][coordinate_index],
                    unit="mm",
                    relative_path=(
                        "segments",
                        segment_index,
                        point_name,
                        coordinate_index,
                    ),
                )


def _feature_control_name(operation_type: str, field_name: str) -> str:
    names = {
        ("extrude", "distance"): "Extrusion distance",
        ("add_extrude", "distance"): "Extrusion distance",
        ("add_extrude", "attachment_depth"): "Attachment depth",
        ("cut", "depth"): "Cut depth",
        ("countersink", "depth"): "Hole depth",
        ("revolve", "angle"): "Revolve angle",
        ("add_revolve", "angle"): "Revolve angle",
        ("cut_revolve", "angle"): "Revolved cut angle",
        ("countersink", "angle"): "Countersink angle",
        ("fillet", "radius"): "Fillet radius",
        ("chamfer", "distance"): "Chamfer distance",
    }
    return names.get((operation_type, field_name), _display_name(field_name))


def _display_name(field_name: str) -> str:
    return field_name.replace("_", " ").title()


def _validate_parameter_value(
    parameter: EditableParameter,
    value: ParameterValue,
) -> None:
    value_type = parameter.value_type

    if value_type == "end_condition":
        if value == "through":
            return
        _require_positive_number(parameter, value)
        return

    if value_type in {"length", "angle"}:
        _require_positive_number(parameter, value)
        return

    if value_type == "coordinate":
        _require_finite_number(parameter, value)
        return

    if value_type == "count":
        if isinstance(value, bool) or not isinstance(value, int) or value < 3:
            raise ValueError(
                f"Parameter '{parameter.id}' must be an integer of at least 3"
            )


def _require_positive_number(
    parameter: EditableParameter,
    value: ParameterValue,
) -> None:
    _require_finite_number(parameter, value)
    if value <= 0:
        raise ValueError(f"Parameter '{parameter.id}' must be greater than zero")


def _require_finite_number(
    parameter: EditableParameter,
    value: ParameterValue,
) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Parameter '{parameter.id}' must be a number")
    if not isfinite(float(value)):
        raise ValueError(f"Parameter '{parameter.id}' must be finite")


def _set_source_value(
    model_data: dict,
    source_path: tuple[PathStep, ...],
    value: ParameterValue,
) -> None:
    cursor: Any = model_data
    try:
        for step in source_path[:-1]:
            cursor = cursor[step]
        cursor[source_path[-1]] = value
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError(
            "Editable parameter source path no longer matches the model: "
            + "/".join(str(step) for step in source_path)
        ) from error
