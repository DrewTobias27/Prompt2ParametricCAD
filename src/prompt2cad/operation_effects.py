"""Trace whether each CAD operation makes the physical change it claims to make.

Final-solid validation can miss a semantically absent feature.  For example, a
cut that misses the body or an extrusion fully buried inside existing material
can still leave one valid solid.  These checks rebuild operation prefixes only
for evaluation runs, then compare measurable geometry before and after every
operation.  Normal web generation does not pay this extra cost.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from prompt2cad.interpreter import build_model
from prompt2cad.quality import summarize_geometry


ADDITIVE_TYPES = {"add_extrude", "add_revolve"}
SUBTRACTIVE_TYPES = {"cut", "cut_revolve"}
EDGE_TREATMENT_TYPES = {"chamfer", "fillet"}


def evaluate_operation_effects(model_data: dict[str, Any]) -> dict[str, Any]:
    """Return a per-operation geometry trace and actionable effect failures."""
    operations = model_data.get("operations", [])
    trace: list[dict[str, Any]] = []
    failures: list[str] = []
    warnings: list[str] = []
    previous_summary: dict[str, Any] | None = None

    for operation_number, operation in enumerate(operations, start=1):
        prefix = {
            "operations": operations[:operation_number],
            **(
                {"relationships": model_data.get("relationships", [])}
                if model_data.get("relationships")
                else {}
            ),
        }
        part = build_model(prefix)
        summary = summarize_geometry(part)
        entry = operation_trace_entry(
            operation,
            operation_number,
            previous_summary,
            summary,
        )
        target_parent = target_parent_operation(operation, operations[:operation_number - 1])
        entry["target_parent_operation_type"] = (
            target_parent.get("type") if target_parent else None
        )
        entry["target_parent_profile"] = (
            target_parent.get("profile") if target_parent else None
        )
        entry["instance_effects"] = evaluate_positioned_instances(
            model_data,
            operation_number,
            previous_summary,
        )
        trace.append(entry)
        failures.extend(operation_effect_failures(entry))
        failures.extend(instance_effect_failures(entry))
        warnings.extend(operation_pattern_warnings(operation, operation_number))
        previous_summary = summary

    return {
        "passed": not failures,
        "failures": failures,
        "warnings": warnings,
        "trace": trace,
    }


def operation_trace_entry(
    operation: dict[str, Any],
    operation_number: int,
    before: dict[str, Any] | None,
    after: dict[str, Any],
) -> dict[str, Any]:
    """Return compact before/after facts for one operation."""
    before_volume = before.get("volume") if before else None
    after_volume = after.get("volume")
    volume_delta = (
        round(float(after_volume) - float(before_volume), 6)
        if before_volume is not None and after_volume is not None
        else None
    )
    positions = operation.get("positions")
    return {
        "operation_number": operation_number,
        "operation_id": operation.get("id"),
        "operation_type": operation.get("type"),
        "target": operation.get("target"),
        "positions": positions if isinstance(positions, list) else None,
        "instance_count": len(positions) if isinstance(positions, list) else 1,
        "volume_before": before_volume,
        "volume_after": after_volume,
        "volume_delta": volume_delta,
        "solid_count_after": after.get("solid_count"),
        "face_count_before": before.get("face_count") if before else None,
        "face_count_after": after.get("face_count"),
        "edge_count_before": before.get("edge_count") if before else None,
        "edge_count_after": after.get("edge_count"),
        "bounding_box_before": before.get("bounding_box") if before else None,
        "bounding_box_after": after.get("bounding_box"),
    }


def operation_effect_failures(entry: dict[str, Any]) -> list[str]:
    """Return failures when an operation has no measurable physical effect."""
    operation_number = entry["operation_number"]
    operation_id = entry.get("operation_id") or f"operation_{operation_number}"
    operation_type = entry.get("operation_type")
    volume_before = entry.get("volume_before")
    volume_delta = entry.get("volume_delta")
    if volume_before is None or volume_delta is None:
        return []

    tolerance = max(1e-6, abs(float(volume_before)) * 1e-8)
    label = f"Operation {operation_number} ({operation_id}, {operation_type})"

    if operation_type in ADDITIVE_TYPES and volume_delta <= tolerance:
        return [
            f"{label} did not add measurable material (volume delta "
            f"{volume_delta}). {no_effect_suggestion(entry)}"
        ]

    if operation_type in SUBTRACTIVE_TYPES and volume_delta >= -tolerance:
        return [
            f"{label} did not remove measurable material (volume delta "
            f"{volume_delta}). {no_effect_suggestion(entry)}"
        ]

    if operation_type in EDGE_TREATMENT_TYPES and abs(volume_delta) <= tolerance:
        topology_changed = (
            entry.get("face_count_before") != entry.get("face_count_after")
            or entry.get("edge_count_before") != entry.get("edge_count_after")
        )
        if not topology_changed:
            return [
                f"{label} did not measurably change volume or topology. "
                "Its edge selector may not identify the intended edges."
            ]

    return []


def evaluate_positioned_instances(
    model_data: dict[str, Any],
    operation_number: int,
    before_summary: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Measure each repeated face-feature instance independently."""
    operation = model_data["operations"][operation_number - 1]
    positions = operation.get("positions")
    if (
        before_summary is None
        or operation.get("type") not in ADDITIVE_TYPES | SUBTRACTIVE_TYPES
        or not isinstance(positions, list)
        or len(positions) < 2
        or operation.get("type") in {"add_revolve", "cut_revolve"}
    ):
        return []

    instance_effects = []
    for instance_number, position in enumerate(positions, start=1):
        isolated_operation = deepcopy(operation)
        isolated_operation["positions"] = [position]
        isolated_model = {
            "operations": [
                *deepcopy(model_data["operations"][: operation_number - 1]),
                isolated_operation,
            ]
        }
        try:
            part = build_model(isolated_model)
            after_summary = summarize_geometry(part)
            volume_delta = round(
                float(after_summary["volume"]) - float(before_summary["volume"]),
                6,
            )
            tolerance = max(
                1e-6,
                abs(float(before_summary["volume"])) * 1e-8,
            )
            if operation.get("type") in ADDITIVE_TYPES:
                affected = volume_delta > tolerance
            else:
                affected = volume_delta < -tolerance
            instance_effects.append({
                "instance_number": instance_number,
                "position": position,
                "affected_model": affected,
                "volume_delta": volume_delta,
            })
        except Exception as error:  # noqa: BLE001 - diagnostics preserve each failure.
            instance_effects.append({
                "instance_number": instance_number,
                "position": position,
                "affected_model": False,
                "error": str(error),
            })

    return instance_effects


def instance_effect_failures(entry: dict[str, Any]) -> list[str]:
    """Report partially effective patterns with exact failed instances."""
    instance_effects = entry.get("instance_effects", [])
    if not instance_effects:
        return []

    ineffective = [
        instance for instance in instance_effects if not instance["affected_model"]
    ]
    if not ineffective or len(ineffective) == len(instance_effects):
        return []

    failed_locations = ", ".join(
        f"#{instance['instance_number']} at {instance['position']}"
        for instance in ineffective
    )
    return [
        f"Operation {entry['operation_number']} ({entry.get('operation_id')}) "
        f"only affected {len(instance_effects) - len(ineffective)} of "
        f"{len(instance_effects)} requested instances; missed {failed_locations}. "
        f"{no_effect_suggestion(entry)}"
    ]


def no_effect_suggestion(entry: dict[str, Any]) -> str:
    """Return target-aware guidance for an operation that changed nothing."""
    target = str(entry.get("target") or "")
    if entry.get("target_parent_operation_type") in {"revolve", "add_revolve"}:
        return (
            "Verify whether the target is a planar end face or a curved/tangent "
            "surface, then check positions in that face's local coordinates."
        )
    if entry.get("instance_count", 1) > 1:
        return (
            "Check that every pattern position lies inside the actual target "
            "profile, not only inside its rectangular bounding box."
        )
    return "Check its target, local position, dimensions, and overlap with the body."


def target_parent_operation(
    operation: dict[str, Any],
    previous_operations: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Return the earlier operation that owns this operation's target."""
    target = operation.get("target")
    if not target:
        return None
    owner_id = str(target).split(".", 1)[0]
    return next(
        (
            candidate
            for candidate in reversed(previous_operations)
            if candidate.get("id") == owner_id
        ),
        None,
    )


def operation_pattern_warnings(
    operation: dict[str, Any],
    operation_number: int,
) -> list[str]:
    """Warn about repeated instances that collapse onto duplicate positions."""
    positions = operation.get("positions")
    if not isinstance(positions, list) or len(positions) < 2:
        return []

    normalized = [tuple(round(float(value), 6) for value in point) for point in positions]
    duplicate_count = len(normalized) - len(set(normalized))
    if duplicate_count == 0:
        return []

    return [
        f"Operation {operation_number} contains {duplicate_count} duplicate "
        "instance position(s), so the requested pattern may have fewer physical "
        "instances than intended."
    ]
