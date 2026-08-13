"""Plan and execute a narrow native SOLIDWORKS feature replay.

The editable-model document remains the CAD-system-neutral source of truth.
This module lowers the first deliberately small subset of that document into
an explicit SOLIDWORKS replay plan.  Planning is pure Python and therefore
fully testable without starting SOLIDWORKS; execution is delegated to a
Windows PowerShell/COM runner only after every feature has been accepted.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace
from hashlib import sha1
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Callable

from prompt2cad.editable_model import EditableFeatureDefinition
from prompt2cad.editable_model import EditableModelDocument
from prompt2cad.pattern_geometry import pattern_positions


SOLIDWORKS_REPLAY_FORMAT = "prompt2cad.solidworks-replay-plan"
SOLIDWORKS_REPLAY_VERSION = 11
SOLIDWORKS_MUTATION_FORMAT = "prompt2cad.solidworks-mutations"
SOLIDWORKS_MUTATION_VERSION = 2
SUPPORTED_OPERATION_TYPES = {
    "extrude",
    "add_extrude",
    "cut",
    "revolve",
    "add_revolve",
    "cut_revolve",
    "countersink",
    "chamfer",
    "fillet",
}
SUPPORTED_PROFILE_TYPES = {
    "rectangle",
    "circle",
    "polygon",
    "polyline",
    "sketch",
}

SOLIDWORKS_PARITY_MATRIX = {
    "extrude": "native_boss_extrude",
    "add_extrude": "native_boss_extrude",
    "cut": "native_cut_extrude",
    "revolve": "native_boss_revolve",
    "add_revolve": "native_boss_revolve",
    "cut_revolve": "native_cut_revolve",
    "countersink": "native_hole_wizard",
    "chamfer": "native_edge_chamfer",
    "fillet": "native_edge_fillet",
}

DATUM_PLANE_SUPPORTS = {
    "XY": {
        "name": "Front Plane",
        "frame": {
            "origin_mm": [0.0, 0.0, 0.0],
            "x_axis": [1.0, 0.0, 0.0],
            "normal": [0.0, 0.0, 1.0],
        },
    },
    "XZ": {
        "name": "Top Plane",
        "frame": {
            "origin_mm": [0.0, 0.0, 0.0],
            "x_axis": [1.0, 0.0, 0.0],
            "normal": [0.0, -1.0, 0.0],
        },
    },
    "YZ": {
        "name": "Right Plane",
        "frame": {
            "origin_mm": [0.0, 0.0, 0.0],
            "x_axis": [0.0, 1.0, 0.0],
            "normal": [1.0, 0.0, 0.0],
        },
    },
}


class SolidWorksReplayError(ValueError):
    """Raised when a model cannot be replayed safely as native features."""


class SolidWorksExecutionError(RuntimeError):
    """Raised when the native SOLIDWORKS automation process fails."""


@dataclass(frozen=True)
class SolidWorksReplayFeature:
    """One native sketch and the feature created from it."""

    id: str
    operation_type: str
    feature_name: str
    sketch_name: str | None
    support: dict
    sketch: dict | None
    feature: dict
    pattern: dict | None = None
    parameter_bindings: tuple[dict, ...] = field(default_factory=tuple)
    publish_references: tuple[dict, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        """Return a JSON-friendly replay step."""
        return {
            "id": self.id,
            "operation_type": self.operation_type,
            "feature_name": self.feature_name,
            "sketch_name": self.sketch_name,
            "support": self.support,
            "sketch": self.sketch,
            "feature": self.feature,
            "pattern": self.pattern,
            "parameter_bindings": list(self.parameter_bindings),
            "publish_references": list(self.publish_references),
        }


@dataclass(frozen=True)
class SolidWorksReplayPlan:
    """A validated sequence that the SOLIDWORKS COM runner can replay."""

    features: tuple[SolidWorksReplayFeature, ...]
    source_build_order: tuple[str, ...]
    expected_geometry: dict | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)
    format_name: str = SOLIDWORKS_REPLAY_FORMAT
    format_version: int = SOLIDWORKS_REPLAY_VERSION

    def to_dict(self) -> dict:
        """Return the complete native replay manifest."""
        return {
            "format": self.format_name,
            "version": self.format_version,
            "units": {
                "source_length": "mm",
                "solidworks_system_length": "m",
            },
            "source_build_order": list(self.source_build_order),
            "expected_geometry": deepcopy(self.expected_geometry),
            "features": [feature.to_dict() for feature in self.features],
            "warnings": list(self.warnings),
            "capabilities": {
                "native_sketches": True,
                "named_driving_dimensions": True,
                "native_feature_history": True,
                "supported_operations": sorted(SUPPORTED_OPERATION_TYPES),
                "supported_profiles": sorted(SUPPORTED_PROFILE_TYPES),
                "supported_supports": [
                    "XY source datum plane",
                    "named planar feature faces",
                    "axis-aligned virtual offset planes",
                ],
                "multi_instance_sketches": True,
                "native_patterns": ["circular", "linear", "mirror"],
                "native_countersinks": True,
                "native_edge_treatments": ["chamfer", "fillet"],
                "step_operation_parity": SOLIDWORKS_PARITY_MATRIX,
                "arbitrary_sketch_placement": True,
                "native_freeform_coordinate_bindings": True,
                "canonical_revolve_axis_metadata": True,
                "generated_stable_feature_ids": True,
                "persistent_entity_reference_contract": True,
                "native_geometry_oracle": self.expected_geometry is not None,
            },
        }


def build_solidworks_replay_plan(
    document: EditableModelDocument,
    *,
    expected_geometry: dict | None = None,
) -> SolidWorksReplayPlan:
    """Lower a supported editable document into a native replay plan.

    The first native milestone favors a small, dependable subset over a broad
    but misleading export.  Every unsupported feature is reported before the
    external CAD application is opened.
    """
    if not document.features:
        raise SolidWorksReplayError("The editable model has no features to replay")

    errors: list[str] = []
    replay_features: list[SolidWorksReplayFeature] = []
    published_faces: dict[str, dict[str, str]] = {}
    native_feature_names: dict[str, str] = {}
    native_feature_frames: dict[str, dict] = {}
    published_face_planes: dict[tuple, str] = {}
    used_native_names: set[str] = set()

    for build_index, feature in enumerate(document.features):
        try:
            feature_name = _unique_feature_name(feature, used_native_names)
            replay_feature = _replay_feature(
                feature,
                build_index=build_index,
                feature_name=feature_name,
                published_faces=published_faces,
                native_feature_names=native_feature_names,
                native_feature_frames=native_feature_frames,
            )
        except SolidWorksReplayError as error:
            errors.append(f"{feature.id}: {error}")
            continue

        replay_feature, feature_face_map = _deduplicate_coplanar_face_references(
            feature,
            replay_feature,
            published_face_planes,
        )
        replay_features.append(replay_feature)
        used_native_names.update(
            name.casefold() for name in _owned_native_names(replay_feature)
        )
        native_feature_names[feature.id] = feature_name
        native_feature_frames[feature.id] = dict(replay_feature.support.get("frame", {}))
        published_faces[feature.id] = feature_face_map

    if errors:
        raise SolidWorksReplayError(
            "Native SOLIDWORKS replay is not available for this model: "
            + " | ".join(errors)
        )

    if tuple(feature.id for feature in replay_features) != document.build_order:
        raise SolidWorksReplayError(
            "Native replay feature order does not match the editable build order"
        )

    plan = SolidWorksReplayPlan(
        features=tuple(replay_features),
        source_build_order=document.build_order,
        expected_geometry=_normalize_expected_geometry(expected_geometry),
    )
    _validate_replay_plan_contract(plan)
    return plan


def _normalize_expected_geometry(value: dict | None) -> dict | None:
    """Validate and copy the kernel-independent native geometry oracle."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise SolidWorksReplayError("Expected geometry must be an object")

    required_keys = {
        "solid_body_count",
        "volume_mm3",
        "surface_area_mm2",
        "center_of_mass_mm",
        "bounding_box_mm",
    }
    if set(value) != required_keys:
        missing = sorted(required_keys - set(value))
        unexpected = sorted(set(value) - required_keys)
        raise SolidWorksReplayError(
            "Expected geometry has the wrong fields; "
            f"missing={missing}, unexpected={unexpected}"
        )

    body_count = value["solid_body_count"]
    if isinstance(body_count, bool) or not isinstance(body_count, int):
        raise SolidWorksReplayError(
            "Expected geometry solid_body_count must be an integer"
        )
    if body_count <= 0:
        raise SolidWorksReplayError(
            "Expected geometry solid_body_count must be positive"
        )

    volume = _positive_finite_geometry_value(
        value["volume_mm3"],
        "volume_mm3",
    )
    surface_area = _positive_finite_geometry_value(
        value["surface_area_mm2"],
        "surface_area_mm2",
    )
    center = _finite_geometry_vector(
        value["center_of_mass_mm"],
        length=3,
        label="center_of_mass_mm",
    )
    bounds = _finite_geometry_vector(
        value["bounding_box_mm"],
        length=6,
        label="bounding_box_mm",
    )
    if any(bounds[index + 3] <= bounds[index] for index in range(3)):
        raise SolidWorksReplayError(
            "Expected geometry bounding_box_mm must have positive spans"
        )

    return {
        "solid_body_count": body_count,
        "volume_mm3": volume,
        "surface_area_mm2": surface_area,
        "center_of_mass_mm": center,
        "bounding_box_mm": bounds,
    }


def _positive_finite_geometry_value(value, label: str) -> float:
    numeric = _finite_geometry_value(value, label)
    if numeric <= 0:
        raise SolidWorksReplayError(
            f"Expected geometry {label} must be positive"
        )
    return numeric


def _finite_geometry_vector(value, *, length: int, label: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != length:
        raise SolidWorksReplayError(
            f"Expected geometry {label} must contain {length} values"
        )
    return [
        _finite_geometry_value(item, f"{label}[{index}]")
        for index, item in enumerate(value)
    ]


def _finite_geometry_value(value, label: str) -> float:
    if isinstance(value, bool):
        raise SolidWorksReplayError(
            f"Expected geometry {label} must be numeric"
        )
    try:
        numeric = float(value)
    except (TypeError, ValueError) as error:
        raise SolidWorksReplayError(
            f"Expected geometry {label} must be numeric"
        ) from error
    if not math.isfinite(numeric):
        raise SolidWorksReplayError(
            f"Expected geometry {label} must be finite"
        )
    return numeric


def _deduplicate_coplanar_face_references(
    feature: EditableFeatureDefinition,
    replay_feature: SolidWorksReplayFeature,
    published_face_planes: dict[tuple, str],
) -> tuple[SolidWorksReplayFeature, dict[str, str]]:
    """Reuse one native name when merged features share a planar face.

    SOLIDWORKS allows one entity name per face.  A coplanar additive feature
    can merge its top or bottom into an already named plate face, so assigning
    a second feature-local name would fail even though both semantic
    references correctly describe the same support plane.  Plane keys are
    derived from the stable feature frame, not rediscovered from final
    topology.
    """
    unique_references: list[dict] = []
    face_map: dict[str, str] = {}
    for reference in replay_feature.publish_references:
        if reference.get("entity_type") != "face":
            unique_references.append(reference)
            continue

        semantic_name = reference["semantic_name"]
        plane_key = _published_reference_plane_key(
            feature,
            replay_feature.support,
            reference,
        )
        existing_name = (
            published_face_planes.get(plane_key)
            if plane_key is not None
            else None
        )
        if existing_name is not None:
            face_map[semantic_name] = existing_name
            continue

        entity_name = reference["entity_name"]
        unique_references.append(reference)
        face_map[semantic_name] = entity_name
        if plane_key is not None:
            published_face_planes[plane_key] = entity_name

    return (
        replace(
            replay_feature,
            publish_references=tuple(unique_references),
        ),
        face_map,
    )


def _published_reference_plane_key(
    feature: EditableFeatureDefinition,
    support: dict,
    reference: dict,
) -> tuple | None:
    selector = reference.get("selector", {})
    if selector.get("kind") != "planar_face_direction":
        return None
    origin = _published_face_origin(
        feature,
        support,
        reference["semantic_name"],
    )
    if origin is None:
        return None

    direction = _normalize(
        [float(value) for value in selector["direction"]]
    )
    stable_direction = tuple(
        0.0 if abs(value) <= 1e-9 else round(value, 6)
        for value in direction
    )
    return stable_direction + (round(_dot(origin, direction), 6),)


def _published_face_origin(
    feature: EditableFeatureDefinition,
    support: dict,
    semantic_name: str,
) -> list[float] | None:
    operation = feature.source_operation
    if feature.operation_type not in {"extrude", "add_extrude"}:
        return None

    frame = support.get("frame") or {}
    origin = [float(value) for value in frame.get("origin_mm", [])]
    normal = [float(value) for value in frame.get("normal", [])]
    x_axis = [float(value) for value in frame.get("x_axis", [])]
    if len(origin) != 3 or len(normal) != 3 or len(x_axis) != 3:
        return None
    normal = _normalize(normal)
    x_axis = _normalize(x_axis)
    y_axis = _normalize(_cross(normal, x_axis))

    if semantic_name == "top":
        return _add(origin, _scale(normal, float(operation["distance"])))
    if semantic_name == "bottom":
        return origin
    if operation.get("profile") != "rectangle":
        return None

    positions = operation.get("positions", [[0, 0]])
    if len(positions) != 1:
        return None
    center = _add(
        origin,
        _add(
            _scale(x_axis, float(positions[0][0])),
            _scale(y_axis, float(positions[0][1])),
        ),
    )
    offsets = {
        "right": (x_axis, float(operation["width"]) / 2),
        "left": (_scale(x_axis, -1), float(operation["width"]) / 2),
        "front": (y_axis, float(operation["height"]) / 2),
        "back": (_scale(y_axis, -1), float(operation["height"]) / 2),
    }
    offset = offsets.get(semantic_name)
    if offset is None:
        return None
    return _add(center, _scale(offset[0], offset[1]))


def export_solidworks_part(
    plan: SolidWorksReplayPlan,
    output_path: Path,
    *,
    visible: bool = False,
    template_path: Path | None = None,
    result_output_path: Path | None = None,
    powershell_executable: str = "powershell.exe",
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> Path:
    """Replay a validated plan into a native ``SLDPRT`` file on Windows."""
    _require_geometry_oracle_for_execution(plan)
    output_path = output_path.resolve()
    if output_path.suffix.lower() != ".sldprt":
        raise SolidWorksExecutionError("SOLIDWORKS output must use the .SLDPRT suffix")
    if output_path.exists():
        raise SolidWorksExecutionError(
            f"Refusing to overwrite existing SOLIDWORKS output: {output_path}"
        )

    replay_script = Path(__file__).with_name("solidworks_replay.ps1")
    replay_engine = Path(__file__).with_name("solidworks_replay_runner.cs")
    missing_assets = [
        path
        for path in (replay_script, replay_engine)
        if not path.is_file()
    ]
    if missing_assets:
        raise SolidWorksExecutionError(
            "SOLIDWORKS replay assets were not found: "
            + ", ".join(str(path) for path in missing_assets)
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="prompt2cad-solidworks-") as directory:
        plan_path = Path(directory) / "replay-plan.json"
        plan_path.write_text(
            json.dumps(plan.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )

        command = [
            powershell_executable,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(replay_script),
            "-PlanPath",
            str(plan_path),
            "-OutputPath",
            str(output_path),
        ]
        if visible:
            command.append("-Visible")
        if template_path is not None:
            command.extend(["-TemplatePath", str(template_path.resolve())])

        try:
            completed = runner(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as error:
            raise SolidWorksExecutionError(
                f"SOLIDWORKS replay process could not start: {error}"
            ) from error

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise SolidWorksExecutionError(
            "SOLIDWORKS replay failed"
            + (f": {detail}" if detail else " without diagnostic output")
        )
    if not output_path.is_file():
        raise SolidWorksExecutionError(
            f"SOLIDWORKS reported success but did not create {output_path}"
        )

    if result_output_path is not None:
        try:
            result = json.loads(completed.stdout.strip())
        except json.JSONDecodeError as error:
            raise SolidWorksExecutionError(
                "SOLIDWORKS returned an unreadable native replay result"
            ) from error
        result_output_path = result_output_path.resolve()
        result_output_path.parent.mkdir(parents=True, exist_ok=True)
        result_output_path.write_text(
            json.dumps(result, indent=2) + "\n",
            encoding="utf-8",
        )

    return output_path


def validate_solidworks_mutations(
    plan: SolidWorksReplayPlan,
    mutations: dict[str, float],
) -> dict:
    """Validate one native edit transaction without launching SolidWorks."""
    if not mutations:
        raise SolidWorksExecutionError(
            "Native mutation preflight requires at least one parameter change"
        )
    bindings = {
        binding["parameter_id"]: binding
        for feature in plan.features
        for binding in feature.parameter_bindings
    }
    unknown = sorted(set(mutations) - set(bindings))
    if unknown:
        raise SolidWorksExecutionError(
            "Unknown native parameter IDs: " + ", ".join(unknown)
        )
    native_mutations = {
        parameter_id: _validate_native_mutation(
            parameter_id,
            float(value),
            bindings[parameter_id],
        )
        for parameter_id, value in mutations.items()
    }
    _validate_native_mutation_set(plan, bindings, native_mutations)
    return {
        "mutation_count": len(mutations),
        "parameter_ids": sorted(mutations),
        "native_values": {
            parameter_id: native_mutations[parameter_id]
            for parameter_id in sorted(native_mutations)
        },
    }


def verify_solidworks_editability(
    plan: SolidWorksReplayPlan,
    source_path: Path,
    output_path: Path,
    mutations: dict[str, float],
    *,
    expected_geometry: dict | None = None,
    visible: bool = False,
    result_output_path: Path | None = None,
    powershell_executable: str = "powershell.exe",
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> Path:
    """Reopen, mutate, rebuild, save, and reopen one native part.

    Parameter IDs come from the CAD-neutral editable document.  The canonical
    replay bindings decide whether each value is changed through a named
    dimension or a native feature-data property, allowing this workflow to
    grow with new feature types without adding test-specific mutation code.
    """
    _require_geometry_oracle_for_execution(plan)
    source_path = source_path.resolve()
    output_path = output_path.resolve()
    if source_path.suffix.lower() != ".sldprt" or output_path.suffix.lower() != ".sldprt":
        raise SolidWorksExecutionError(
            "SOLIDWORKS editability verification requires .SLDPRT files"
        )
    if not source_path.is_file():
        raise SolidWorksExecutionError(
            f"SOLIDWORKS source part was not found: {source_path}"
        )
    if source_path == output_path:
        raise SolidWorksExecutionError(
            "Editability verification must save to a separate output part"
        )
    if output_path.exists():
        raise SolidWorksExecutionError(
            f"Refusing to overwrite existing SOLIDWORKS output: {output_path}"
        )
    validate_solidworks_mutations(plan, mutations)
    if expected_geometry is None:
        raise SolidWorksExecutionError(
            "SOLIDWORKS editability verification requires expected edited "
            "CadQuery geometry"
        )
    normalized_edited_geometry = _normalize_expected_geometry(expected_geometry)
    bindings = {
        binding["parameter_id"]: binding
        for feature in plan.features
        for binding in feature.parameter_bindings
    }
    mutation_document = {
        "format": SOLIDWORKS_MUTATION_FORMAT,
        "version": SOLIDWORKS_MUTATION_VERSION,
        "expected_geometry": normalized_edited_geometry,
        "mutations": [
            {
                "parameter_id": parameter_id,
                "value": float(value),
                "unit": bindings[parameter_id]["unit"],
            }
            for parameter_id, value in sorted(mutations.items())
        ],
    }

    replay_script = Path(__file__).with_name("solidworks_replay.ps1")
    replay_engine = Path(__file__).with_name("solidworks_replay_runner.cs")
    missing_assets = [
        path for path in (replay_script, replay_engine) if not path.is_file()
    ]
    if missing_assets:
        raise SolidWorksExecutionError(
            "SOLIDWORKS replay assets were not found: "
            + ", ".join(str(path) for path in missing_assets)
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="prompt2cad-solidworks-edit-") as directory:
        temporary_root = Path(directory)
        plan_path = temporary_root / "replay-plan.json"
        mutation_path = temporary_root / "mutations.json"
        plan_path.write_text(
            json.dumps(plan.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
        mutation_path.write_text(
            json.dumps(mutation_document, indent=2) + "\n",
            encoding="utf-8",
        )
        command = [
            powershell_executable,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(replay_script),
            "-PlanPath",
            str(plan_path),
            "-OutputPath",
            str(output_path),
            "-ExistingPartPath",
            str(source_path),
            "-MutationPath",
            str(mutation_path),
        ]
        if visible:
            command.append("-Visible")

        try:
            completed = runner(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as error:
            raise SolidWorksExecutionError(
                "SOLIDWORKS editability process could not start"
            ) from error
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip()
            raise SolidWorksExecutionError(
                "SOLIDWORKS editability verification failed"
                + (f": {message}" if message else "")
            )
        if not output_path.is_file():
            raise SolidWorksExecutionError(
                "SOLIDWORKS reported a successful edit but created no output part"
            )

        if result_output_path is not None:
            try:
                result = json.loads(completed.stdout.strip())
            except json.JSONDecodeError as error:
                raise SolidWorksExecutionError(
                    "SOLIDWORKS returned an unreadable editability result"
                ) from error
            result_output_path = result_output_path.resolve()
            result_output_path.parent.mkdir(parents=True, exist_ok=True)
            result_output_path.write_text(
                json.dumps(result, indent=2) + "\n",
                encoding="utf-8",
            )

    return output_path


def _require_geometry_oracle_for_execution(plan: SolidWorksReplayPlan) -> None:
    """Fail closed when executable native replay lacks a geometry contract."""
    if plan.expected_geometry is None:
        raise SolidWorksExecutionError(
            "Native SOLIDWORKS execution requires expected CadQuery geometry; "
            "regenerate the replay plan from the source model"
        )


def _replay_feature(
    feature: EditableFeatureDefinition,
    *,
    build_index: int,
    feature_name: str,
    published_faces: dict[str, dict[str, str]],
    native_feature_names: dict[str, str],
    native_feature_frames: dict[str, dict],
) -> SolidWorksReplayFeature:
    operation = feature.source_operation
    operation_type = feature.operation_type
    if operation_type not in SUPPORTED_OPERATION_TYPES:
        raise SolidWorksReplayError(
            f"operation '{operation_type}' is not supported by native replay"
        )

    profile = operation.get("profile")
    profile_operation_types = SUPPORTED_OPERATION_TYPES - {
        "countersink",
        "chamfer",
        "fillet",
    }
    if (
        operation_type in profile_operation_types
        and profile not in SUPPORTED_PROFILE_TYPES
    ):
        raise SolidWorksReplayError(
            f"profile '{profile}' is not supported by native replay"
        )

    positions = operation.get("positions", [[0, 0]])
    if operation_type not in {"chamfer", "fillet"}:
        if not positions:
            raise SolidWorksReplayError("at least one sketch position is required")
        for center in positions:
            if len(center) != 2:
                raise SolidWorksReplayError(
                    "every sketch position must contain X and Y coordinates"
                )

    if operation_type in {"chamfer", "fillet"}:
        return _edge_treatment_replay_feature(
            feature,
            feature_name=feature_name,
            native_feature_names=native_feature_names,
            native_feature_frames=native_feature_frames,
        )

    if build_index == 0:
        if operation_type not in {"extrude", "revolve"}:
            raise SolidWorksReplayError(
                "the first native feature must be an extrude or revolve"
            )
        support = _datum_plane_support(operation.get("plane", "XY"))
    elif operation_type in {"add_revolve", "cut_revolve"}:
        support = _datum_plane_support(operation.get("plane", "XY"))
    else:
        support = _named_face_support(
            feature,
            feature_name=feature_name,
            published_faces=published_faces,
            native_feature_names=native_feature_names,
        )

    if operation_type == "countersink":
        sketch = _countersink_position_sketch(feature)
        native_feature = _native_countersink_control(feature)
    else:
        sketch = _native_sketch(feature, profile)
        native_feature = _native_feature_control(feature)
    pattern = _native_pattern_control(feature, feature_name)
    if pattern is not None:
        sketch["positions_mm"] = [pattern["seed_position_mm"]]
        sketch["placement_controls"] = sketch.get("placement_controls", [])[:1]
    publish_references = _published_reference_specs(
        feature,
        support,
        feature_name,
    )
    parameter_bindings = _native_parameter_bindings(
        feature,
        sketch_name=f"{feature_name}_Sketch",
        feature_name=feature_name,
        sketch=sketch,
        native_feature=native_feature,
        pattern=pattern,
    )

    return SolidWorksReplayFeature(
        id=feature.id,
        operation_type=operation_type,
        feature_name=feature_name,
        sketch_name=f"{feature_name}_Sketch",
        support=support,
        sketch=sketch,
        feature=native_feature,
        pattern=pattern,
        parameter_bindings=parameter_bindings,
        publish_references=publish_references,
    )


def _native_sketch(feature: EditableFeatureDefinition, profile: str) -> dict:
    operation = feature.source_operation
    dimensions: list[dict] = []
    positions = [
        [float(position[0]), float(position[1])]
        for position in operation.get("positions", [[0, 0]])
    ]
    geometry: dict[str, object] = {
        "profile": profile,
        "positions_mm": positions,
        "constraint_plan": _native_constraint_plan(feature, profile),
        "placement_controls": _native_placement_controls(feature, positions),
        "coordinate_controls": _native_coordinate_controls(feature, profile),
    }

    if profile == "rectangle":
        geometry["width_mm"] = float(operation["width"])
        geometry["height_mm"] = float(operation["height"])
        dimensions.extend(
            [
                _dimension(
                    feature,
                    parameter_id=f"{feature.id}.sketch.width",
                    fallback_name="width",
                    value=float(operation["width"]),
                ),
                _dimension(
                    feature,
                    parameter_id=f"{feature.id}.sketch.height",
                    fallback_name="height",
                    value=float(operation["height"]),
                ),
            ]
        )
    elif profile == "circle":
        geometry["diameter_mm"] = float(operation["diameter"])
        dimensions.append(
            _dimension(
                feature,
                parameter_id=f"{feature.id}.sketch.diameter",
                fallback_name="diameter",
                value=float(operation["diameter"]),
            )
        )
    elif profile == "polygon":
        geometry["diameter_mm"] = float(operation["diameter"])
        geometry["sides"] = int(operation["sides"])
        dimensions.append(
            _dimension(
                feature,
                parameter_id=f"{feature.id}.sketch.diameter",
                fallback_name="diameter",
                value=float(operation["diameter"]),
            )
        )
    elif profile == "polyline":
        geometry["points_mm"] = [
            [float(point[0]), float(point[1])]
            for point in operation["points"]
        ]
        geometry["close"] = True
    else:
        geometry["start_mm"] = [
            float(operation["start"][0]),
            float(operation["start"][1]),
        ]
        geometry["segments"] = operation["segments"]
        geometry["close"] = bool(operation.get("close", True))

    geometry["driving_dimensions"] = dimensions
    return geometry


def _native_coordinate_controls(
    feature: EditableFeatureDefinition,
    profile: str,
) -> list[dict]:
    """Bind source-defined freeform points to stable native dimensions.

    Arc centers and radii are intentionally derived from their start, through,
    and end points. Driving both representations would over-constrain the
    sketch and make later edits less predictable.
    """
    operation = feature.source_operation
    controls: list[dict] = []

    def add_control(
        *,
        parameter_stem: str,
        fallback_stem: str,
        position: list[float],
        kind: str = "vertex",
        segment_index: int | None = None,
    ) -> None:
        dimensions: dict[str, dict | None] = {}
        for coordinate_index, axis_name in enumerate(("x", "y")):
            value = float(position[coordinate_index])
            dimensions[axis_name] = (
                None
                if abs(value) <= 1e-12
                else _dimension(
                    feature,
                    parameter_id=(
                        f"{feature.id}.{parameter_stem}.{axis_name}"
                    ),
                    fallback_name=f"{fallback_stem}_{axis_name}",
                    value=abs(value),
                    signed_source_value=value,
                )
            )
        controls.append(
            {
                "kind": kind,
                "segment_index": segment_index,
                "position_mm": [float(position[0]), float(position[1])],
                "x_dimension": dimensions["x"],
                "y_dimension": dimensions["y"],
            }
        )

    if profile == "polyline":
        for point_index, point in enumerate(operation["points"], start=1):
            add_control(
                parameter_stem=f"sketch.point{point_index:03d}",
                fallback_stem=f"point{point_index:03d}",
                position=point,
            )
    elif profile == "sketch":
        add_control(
            parameter_stem="sketch.start",
            fallback_stem="start",
            position=operation["start"],
        )
        for segment_index, segment in enumerate(
            operation["segments"], start=1
        ):
            if segment["type"] == "arc":
                add_control(
                    parameter_stem=(
                        f"sketch.segment{segment_index:03d}.through"
                    ),
                    fallback_stem=f"segment{segment_index:03d}_through",
                    position=segment["through"],
                    kind="arc_through",
                    segment_index=segment_index,
                )
            add_control(
                parameter_stem=f"sketch.segment{segment_index:03d}.to",
                fallback_stem=f"segment{segment_index:03d}_to",
                position=segment["to"],
                segment_index=segment_index,
            )
    return controls


def _countersink_position_sketch(feature: EditableFeatureDefinition) -> dict:
    """Return the point layout consumed by a native Hole Wizard feature."""
    operation = feature.source_operation
    positions = [
        [float(position[0]), float(position[1])]
        for position in operation["positions"]
    ]
    return {
        "profile": "points",
        "positions_mm": positions,
        "driving_dimensions": [],
        "placement_controls": _native_placement_controls(feature, positions),
        "constraint_plan": _native_constraint_plan(feature, "points"),
    }


def _native_constraint_plan(
    feature: EditableFeatureDefinition,
    profile: str,
) -> dict:
    """Describe how the native sketch must consume its remaining freedom.

    Explicit source dimensions remain authoritative.  SOLIDWORKS only fills
    degrees of freedom that those dimensions and inferred topology leave
    behind, which keeps the strategy applicable to future sketch entities
    without special-casing each final part shape.
    """
    return {
        "strategy": "complete_remaining_degrees_of_freedom",
        "profile": profile,
        "relations": [
            "coincident",
            "horizontal",
            "vertical",
            "collinear",
            "concentric",
            "equal",
            "parallel",
            "perpendicular",
            "tangent",
            "midpoint",
        ],
        "horizontal_dimension_scheme": "baseline",
        "vertical_dimension_scheme": "baseline",
        "require_fully_defined": True,
        "source_feature_id": feature.id,
    }


def _native_placement_controls(
    feature: EditableFeatureDefinition,
    positions: list[list[float]],
) -> list[dict]:
    """Return stable native controls for parametric profile locations."""
    controls = []
    for index, position in enumerate(positions, start=1):
        axes = {}
        for coordinate_index, axis_name in enumerate(("x", "y")):
            value = float(position[coordinate_index])
            axes[axis_name] = (
                None
                if abs(value) <= 1e-12
                else _dimension(
                    feature,
                    parameter_id=(
                        f"{feature.id}.placement.inst{index:03d}.{axis_name}"
                    ),
                    fallback_name=f"placement_inst{index:03d}_{axis_name}",
                    value=abs(value),
                    signed_source_value=value,
                )
            )
        controls.append(
            {
                "instance_index": index,
                "position_mm": position,
                "x_dimension": axes["x"],
                "y_dimension": axes["y"],
            }
        )
    return controls


def _native_pattern_control(
    feature: EditableFeatureDefinition,
    feature_name: str,
) -> dict | None:
    """Validate and lower canonical operation pattern metadata."""
    operation = feature.source_operation
    pattern = operation.get("pattern")
    if pattern is None:
        return None

    positions = [
        [float(position[0]), float(position[1])]
        for position in operation.get("positions", [])
    ]
    if len(positions) < 2:
        raise SolidWorksReplayError(
            "native pattern metadata requires at least two exact positions"
        )

    pattern_type = pattern.get("type")
    seed = [float(value) for value in pattern["seed_position"]]
    if not _points_close(seed, positions[0]):
        raise SolidWorksReplayError(
            "pattern seed_position must equal the first exact operation position"
        )
    expected_positions = pattern_positions(pattern)
    if len(expected_positions) != len(positions) or any(
        not _points_close(expected, actual)
        for expected, actual in zip(expected_positions, positions)
    ):
        raise SolidWorksReplayError(
            "pattern metadata must reproduce every exact operation position"
        )

    common = {
        "seed_feature_name": f"{feature_name}_Seed",
        "seed_position_mm": seed,
        "positions_mm": positions,
    }
    if pattern_type == "circular":
        count = int(pattern["count"])
        if count != len(positions):
            raise SolidWorksReplayError(
                "circular pattern count must match the exact position count"
            )
        return {
            **common,
            "kind": "circular_pattern",
            "reference_sketch_name": f"{feature_name}_References",
            "axis_name": f"{feature_name}_Axis",
            "center_mm": [float(value) for value in pattern["center"]],
            "count": count,
            "total_angle_deg": float(pattern["total_angle_degrees"]),
        }

    if pattern_type == "linear":
        count_1 = int(pattern["count_1"])
        count_2 = int(pattern["count_2"])
        if count_1 * count_2 != len(positions):
            raise SolidWorksReplayError(
                "linear pattern counts must match the exact position count"
            )
        spacing_1 = float(pattern["spacing_1"])
        spacing_2 = float(pattern["spacing_2"])
        if (count_1 > 1 and spacing_1 <= 0) or (
            count_2 > 1 and spacing_2 <= 0
        ):
            raise SolidWorksReplayError(
                "a repeated linear-pattern direction requires positive spacing"
            )
        return {
            **common,
            "kind": "linear_pattern",
            "reference_sketch_name": f"{feature_name}_References",
            "direction_1": [float(value) for value in pattern["direction_1"]],
            "count_1": count_1,
            "spacing_1_mm": spacing_1,
            "direction_2": [float(value) for value in pattern["direction_2"]],
            "count_2": count_2,
            "spacing_2_mm": spacing_2,
        }

    if pattern_type == "mirror":
        return {
            **common,
            "kind": "mirror_pattern",
            "placement_sketch_name": f"{feature_name}_MirrorPositions",
            "axes": list(pattern["axes"]),
        }

    raise SolidWorksReplayError(f"unsupported native pattern type '{pattern_type}'")


def _native_countersink_control(feature: EditableFeatureDefinition) -> dict:
    operation = feature.source_operation
    depth = operation["depth"]
    dimensions = [
        _dimension(
            feature,
            parameter_id=f"{feature.id}.feature.diameter",
            fallback_name="hole_diameter",
            value=float(operation["diameter"]),
        ),
        _dimension(
            feature,
            parameter_id=f"{feature.id}.feature.countersink_diameter",
            fallback_name="countersink_diameter",
            value=float(operation["countersink_diameter"]),
        ),
        _dimension(
            feature,
            parameter_id=f"{feature.id}.feature.angle",
            fallback_name="countersink_angle",
            value=float(operation["angle"]),
            unit="deg",
        ),
    ]
    if depth != "through":
        dimensions.append(
            _dimension(
                feature,
                parameter_id=f"{feature.id}.feature.depth",
                fallback_name="depth",
                value=float(depth),
            )
        )
    return {
        "kind": "countersink",
        "end_condition": "through_all" if depth == "through" else "blind",
        "depth_mm": None if depth == "through" else float(depth),
        "hole_diameter_mm": float(operation["diameter"]),
        "countersink_diameter_mm": float(operation["countersink_diameter"]),
        "countersink_angle_deg": float(operation["angle"]),
        "driving_dimensions": dimensions,
    }


def _edge_treatment_replay_feature(
    feature: EditableFeatureDefinition,
    *,
    feature_name: str,
    native_feature_names: dict[str, str],
    native_feature_frames: dict[str, dict],
) -> SolidWorksReplayFeature:
    operation = feature.source_operation
    target = str(operation.get("target", ""))
    parent_id, separator, selector = target.partition(".")
    if not separator or not parent_id or not selector:
        raise SolidWorksReplayError(
            "edge treatments require 'feature.edge_selector' targets"
        )
    target_feature_name = native_feature_names.get(parent_id)
    frame = native_feature_frames.get(parent_id)
    if target_feature_name is None or not frame:
        raise SolidWorksReplayError(
            f"edge target references unknown or future feature '{parent_id}'"
        )

    operation_type = feature.operation_type
    dimension_key = "distance" if operation_type == "chamfer" else "radius"
    value = float(operation[dimension_key])
    native_feature = {
        "kind": f"edge_{operation_type}",
        f"{dimension_key}_mm": value,
        "driving_dimension": _dimension(
            feature,
            parameter_id=f"{feature.id}.feature.{dimension_key}",
            fallback_name=dimension_key,
            value=value,
        ),
    }
    return SolidWorksReplayFeature(
        id=feature.id,
        operation_type=operation_type,
        feature_name=feature_name,
        sketch_name=None,
        support={
            "kind": "feature_edges",
            "parent_feature_id": parent_id,
            "target_feature_name": target_feature_name,
            "selector": selector,
            "frame": frame,
            "members": _native_edge_reference_members(feature),
        },
        sketch=None,
        feature=native_feature,
        parameter_bindings=_native_parameter_bindings(
            feature,
            sketch_name=None,
            feature_name=feature_name,
            sketch=None,
            native_feature=native_feature,
            pattern=None,
        ),
    )


def _native_edge_reference_members(
    feature: EditableFeatureDefinition,
) -> list[dict]:
    """Preserve canonical edge-group members as geometric selectors."""
    snapshot = feature.support_reference or {}
    members = snapshot.get("members", [])
    result = []
    for member in members:
        if member.get("kind") != "edge":
            continue
        metadata = member.get("metadata", {})
        center = metadata.get("center")
        box = metadata.get("bounding_box")
        if (
            not isinstance(center, (list, tuple))
            or len(center) != 3
            or not isinstance(box, dict)
        ):
            continue
        result.append(
            {
                "reference_id": member["name"],
                "center_mm": [float(value) for value in center],
                "bounding_box_mm": [
                    float(box[key])
                    for key in ("xmin", "ymin", "zmin", "xmax", "ymax", "zmax")
                ],
            }
        )
    return result


def _native_parameter_bindings(
    feature: EditableFeatureDefinition,
    *,
    sketch_name: str | None,
    feature_name: str,
    sketch: dict | None,
    native_feature: dict,
    pattern: dict | None,
) -> tuple[dict, ...]:
    """Return one canonical manifest for every native editable control.

    Geometry creation still consumes the profile- and feature-specific fields
    for compatibility.  Verification and future mutation tools consume this
    manifest instead, so a new operation cannot silently declare a parameter
    without also describing its native owner and access strategy.
    """
    bindings: list[dict] = []

    if sketch is not None and sketch_name is not None:
        for dimension in sketch.get("driving_dimensions", []):
            bindings.append(
                _dimension_binding(
                    dimension,
                    owner_kind="sketch",
                    owner_name=sketch_name,
                )
            )
        for control in sketch.get("placement_controls", []):
            for dimension in (
                control.get("x_dimension"),
                control.get("y_dimension"),
            ):
                if dimension is not None:
                    bindings.append(
                        _dimension_binding(
                            dimension,
                            owner_kind="sketch",
                            owner_name=sketch_name,
                        )
                    )
        for control in sketch.get("coordinate_controls", []):
            for dimension in (
                control.get("x_dimension"),
                control.get("y_dimension"),
            ):
                if dimension is not None:
                    bindings.append(
                        _dimension_binding(
                            dimension,
                            owner_kind="sketch",
                            owner_name=sketch_name,
                        )
                    )

    native_owner_name = (
        pattern["seed_feature_name"] if pattern is not None else feature_name
    )
    driving_dimension = native_feature.get("driving_dimension")
    if driving_dimension is not None:
        bindings.append(
            _dimension_binding(
                driving_dimension,
                owner_kind="feature",
                owner_name=native_owner_name,
            )
        )
    reverse_driving_dimension = native_feature.get("reverse_driving_dimension")
    if reverse_driving_dimension is not None:
        bindings.append(
            _dimension_binding(
                reverse_driving_dimension,
                owner_kind="feature",
                owner_name=native_owner_name,
            )
        )

    if native_feature.get("kind") == "countersink":
        property_names = {
            "diameter": ["Diameter", "HoleDiameter", "ThruHoleDiameter"],
            "countersink_diameter": ["CounterSinkDiameter"],
            "angle": ["CounterSinkAngle"],
            "depth": ["Depth", "HoleDepth"],
        }
        for dimension in native_feature.get("driving_dimensions", []):
            key = dimension["parameter_id"].rsplit(".", 1)[-1]
            bindings.append(
                _feature_property_binding(
                    dimension,
                    owner_name=native_owner_name,
                    native_properties=property_names[key],
                )
            )

    if pattern is not None:
        bindings.extend(_pattern_parameter_bindings(feature, feature_name, pattern))

    parameter_ids = [binding["parameter_id"] for binding in bindings]
    if len(parameter_ids) != len(set(parameter_ids)):
        raise SolidWorksReplayError(
            f"feature '{feature.id}' produced duplicate native parameter bindings"
        )
    return tuple(bindings)


def _dimension_binding(
    dimension: dict,
    *,
    owner_kind: str,
    owner_name: str,
) -> dict:
    binding = {
        "parameter_id": dimension["parameter_id"],
        "native_name": dimension["native_name"],
        "binding_kind": "named_dimension",
        "owner_kind": owner_kind,
        "owner_name": owner_name,
        "native_properties": [],
        "value": float(dimension["value_mm"]),
        "unit": dimension["unit"],
        "minimum_value": 0.0,
        "minimum_inclusive": False,
    }
    if dimension["unit"] == "deg":
        binding["maximum_value"] = 360.0
        binding["maximum_inclusive"] = True
    if "mutation_mode" in dimension:
        binding["mutation_mode"] = dimension["mutation_mode"]
        binding["source_value"] = float(dimension["source_value"])
    return binding


def _validate_native_mutation(
    parameter_id: str,
    value: float,
    binding: dict,
) -> float:
    """Reject edits a native control cannot represent without rebuilding.

    SOLIDWORKS point-to-point dimensions store a positive distance. The side
    of the origin comes from the sketch topology created during replay, so a
    sign crossing cannot be represented by changing that dimension alone.
    """
    if not math.isfinite(value):
        raise SolidWorksExecutionError(
            f"Native parameter '{parameter_id}' requires a finite value"
        )

    native_value = value
    if binding.get("mutation_mode") == "absolute_same_side":
        source_value = float(binding["source_value"])
        if abs(value) <= 1e-12 or source_value * value <= 0:
            raise SolidWorksExecutionError(
                f"Native coordinate parameter '{parameter_id}' cannot cross "
                "or land on the sketch origin during an in-place SolidWorks "
                "edit. Regenerate the SolidWorks package from the updated "
                "CAD model to change sides safely."
            )
        native_value = abs(value)

    if binding.get("integer_only") and not native_value.is_integer():
        raise SolidWorksExecutionError(
            f"Native parameter '{parameter_id}' requires a whole-number value"
        )

    minimum = binding.get("minimum_value")
    if minimum is not None and (
        native_value < float(minimum)
        or (
            native_value == float(minimum)
            and not binding.get("minimum_inclusive", True)
        )
    ):
        comparison = (
            "at least"
            if binding.get("minimum_inclusive")
            else "greater than"
        )
        raise SolidWorksExecutionError(
            f"Native parameter '{parameter_id}' must be {comparison} {minimum}"
        )

    maximum = binding.get("maximum_value")
    if maximum is not None and (
        native_value > float(maximum)
        or (
            native_value == float(maximum)
            and not binding.get("maximum_inclusive", True)
        )
    ):
        comparison = (
            "at most"
            if binding.get("maximum_inclusive")
            else "less than"
        )
        raise SolidWorksExecutionError(
            f"Native parameter '{parameter_id}' must be {comparison} {maximum}"
        )
    return native_value


def _validate_native_mutation_set(
    plan: SolidWorksReplayPlan,
    bindings: dict[str, dict],
    native_mutations: dict[str, float],
) -> None:
    """Validate dependent controls before any native document is changed."""
    projected = {
        parameter_id: float(binding["value"])
        for parameter_id, binding in bindings.items()
    }
    projected.update(native_mutations)

    for step in plan.features:
        if step.feature.get("kind") == "countersink":
            hole_id = f"{step.id}.feature.diameter"
            countersink_id = f"{step.id}.feature.countersink_diameter"
            if projected[countersink_id] <= projected[hole_id]:
                raise SolidWorksExecutionError(
                    f"Native countersink '{step.id}' requires its countersink "
                    "diameter to remain larger than its hole diameter"
                )

        pattern = step.pattern
        if pattern is None or pattern.get("kind") != "linear_pattern":
            continue
        count_1 = projected[f"{step.id}.pattern.count_1"]
        count_2 = projected[f"{step.id}.pattern.count_2"]
        spacing_1 = projected[f"{step.id}.pattern.spacing_1"]
        spacing_2 = projected[f"{step.id}.pattern.spacing_2"]
        if count_1 * count_2 < 2:
            raise SolidWorksExecutionError(
                f"Native linear pattern '{step.id}' must retain at least two "
                "instances; regenerate the package to remove the pattern"
            )
        if count_1 > 1 and spacing_1 <= 0:
            raise SolidWorksExecutionError(
                f"Native linear pattern '{step.id}' requires positive "
                "direction-1 spacing when count 1 exceeds one"
            )
        if count_2 > 1 and spacing_2 <= 0:
            raise SolidWorksExecutionError(
                f"Native linear pattern '{step.id}' requires positive "
                "direction-2 spacing when count 2 exceeds one"
            )


def _feature_property_binding(
    dimension: dict,
    *,
    owner_name: str,
    native_properties: list[str],
) -> dict:
    binding = {
        "parameter_id": dimension["parameter_id"],
        "native_name": dimension["native_name"],
        "binding_kind": "feature_property",
        "owner_kind": "feature",
        "owner_name": owner_name,
        "native_properties": native_properties,
        "value": float(dimension["value_mm"]),
        "unit": dimension["unit"],
        "minimum_value": 0.0,
        "minimum_inclusive": False,
    }
    if dimension["unit"] == "deg":
        binding["maximum_value"] = 180.0
        binding["maximum_inclusive"] = False
    return binding


def _pattern_parameter_bindings(
    feature: EditableFeatureDefinition,
    feature_name: str,
    pattern: dict,
) -> list[dict]:
    values: list[tuple[str, str, float, str]] = []
    kind = pattern["kind"]
    if kind == "circular_pattern":
        values = [
            ("count", "TotalInstances", float(pattern["count"]), "count"),
            (
                "total_angle",
                "Spacing",
                float(pattern["total_angle_deg"]),
                "deg",
            ),
        ]
    elif kind == "linear_pattern":
        values = [
            ("count_1", "D1TotalInstances", float(pattern["count_1"]), "count"),
            ("spacing_1", "D1Spacing", float(pattern["spacing_1_mm"]), "mm"),
            ("count_2", "D2TotalInstances", float(pattern["count_2"]), "count"),
            ("spacing_2", "D2Spacing", float(pattern["spacing_2_mm"]), "mm"),
        ]
    else:
        return []

    bindings = []
    for parameter_name, native_property, value, unit in values:
        parameter_id = f"{feature.id}.pattern.{parameter_name}"
        binding = {
            "parameter_id": parameter_id,
            "native_name": _dimension_name(parameter_id, parameter_name),
            "binding_kind": "feature_property",
            "owner_kind": "pattern",
            "owner_name": feature_name,
            "native_properties": [native_property],
            "value": value,
            "unit": unit,
            "minimum_value": 0.0,
            "minimum_inclusive": parameter_name.startswith("spacing_"),
        }
        if unit == "count":
            binding["integer_only"] = True
            binding["minimum_value"] = (
                2.0 if kind == "circular_pattern" else 1.0
            )
            binding["minimum_inclusive"] = True
        elif unit == "deg":
            binding["maximum_value"] = 360.0
            binding["maximum_inclusive"] = True
        bindings.append(binding)
    return bindings


def _points_close(first: list[float], second: list[float]) -> bool:
    return len(first) == len(second) and all(
        abs(left - right) <= 1e-6
        for left, right in zip(first, second)
    )


def _native_feature_control(feature: EditableFeatureDefinition) -> dict:
    operation = feature.source_operation
    operation_type = feature.operation_type
    if operation_type in {"extrude", "add_extrude"}:
        distance = float(operation["distance"])
        control = {
            "kind": "boss_extrude",
            "end_condition": "blind",
            "depth_mm": distance,
            "merge_result": True,
            "driving_dimension": _dimension(
                feature,
                parameter_id=f"{feature.id}.feature.distance",
                fallback_name="distance",
                value=distance,
            ),
        }
        attachment_depth = operation.get("attachment_depth")
        if attachment_depth is not None:
            attachment_depth = float(attachment_depth)
            control.update(
                {
                    "reverse_depth_mm": attachment_depth,
                    "reverse_driving_dimension": _dimension(
                        feature,
                        parameter_id=(
                            f"{feature.id}.feature.attachment_depth"
                        ),
                        fallback_name="attachment_depth",
                        value=attachment_depth,
                    ),
                }
            )
        return control

    if operation_type in {"revolve", "add_revolve", "cut_revolve"}:
        angle = float(operation["angle"])
        axis_start = [float(value) for value in operation["axis_start"][:2]]
        axis_end = [float(value) for value in operation["axis_end"][:2]]
        return {
            "kind": (
                "cut_revolve"
                if operation_type == "cut_revolve"
                else "boss_revolve"
            ),
            "angle_deg": angle,
            "axis_start_mm": axis_start,
            "axis_end_mm": axis_end,
            "canonical_axis": _canonical_revolve_axis(axis_start, axis_end),
            "merge_result": operation_type == "add_revolve",
            "driving_dimension": _dimension(
                feature,
                parameter_id=f"{feature.id}.feature.angle",
                fallback_name="angle",
                value=angle,
                unit="deg",
            ),
        }

    depth = operation["depth"]
    if depth == "through":
        return {
            "kind": "cut_extrude",
            "end_condition": "through_all",
            "depth_mm": None,
            "driving_dimension": None,
        }

    depth_value = float(depth)
    return {
        "kind": "cut_extrude",
        "end_condition": "blind",
        "depth_mm": depth_value,
        "driving_dimension": _dimension(
            feature,
            parameter_id=f"{feature.id}.feature.depth",
            fallback_name="depth",
            value=depth_value,
        ),
    }


def _canonical_revolve_axis(
    axis_start: list[float],
    axis_end: list[float],
) -> dict:
    """Represent an endpoint-defined 2D line without endpoint ambiguity.

    A revolve consumes an infinite axis line, so translating or reversing its
    two source endpoints must not change the semantic axis. The closest point
    to the sketch origin plus a sign-normalized unit direction is canonical;
    source endpoints remain in the plan for the proven native runner.
    """
    if len(axis_start) != 2 or len(axis_end) != 2:
        raise SolidWorksReplayError(
            "native revolve axis must contain two 2D points"
        )
    values = [*axis_start, *axis_end]
    if not all(math.isfinite(value) for value in values):
        raise SolidWorksReplayError(
            "native revolve axis coordinates must be finite"
        )

    delta_x = axis_end[0] - axis_start[0]
    delta_y = axis_end[1] - axis_start[1]
    source_span = math.hypot(delta_x, delta_y)
    if source_span <= 1e-12:
        raise SolidWorksReplayError(
            "native revolve axis start and end cannot coincide"
        )

    direction_x = delta_x / source_span
    direction_y = delta_y / source_span
    if direction_x < -1e-12 or (
        abs(direction_x) <= 1e-12 and direction_y < 0
    ):
        direction_x *= -1.0
        direction_y *= -1.0

    normal_x = -direction_y
    normal_y = direction_x
    signed_offset = axis_start[0] * normal_x + axis_start[1] * normal_y
    anchor = [normal_x * signed_offset, normal_y * signed_offset]
    direction_angle = math.degrees(math.atan2(direction_y, direction_x))
    return {
        "kind": "canonical_line_2d",
        "anchor_mm": [_clean_zero(value) for value in anchor],
        "direction": [
            _clean_zero(direction_x),
            _clean_zero(direction_y),
        ],
        "normal": [_clean_zero(normal_x), _clean_zero(normal_y)],
        "signed_offset_mm": _clean_zero(signed_offset),
        "direction_angle_deg": _clean_zero(direction_angle),
        "automated_mutation": False,
        "edit_strategy": "edit_native_construction_line_or_regenerate",
    }


def _clean_zero(value: float) -> float:
    """Avoid serializing negative zero in canonical geometry metadata."""
    return 0.0 if abs(value) <= 1e-12 else value


def _named_face_support(
    feature: EditableFeatureDefinition,
    *,
    feature_name: str,
    published_faces: dict[str, dict[str, str]],
    native_feature_names: dict[str, str],
) -> dict:
    target = feature.target
    if not target or "." not in target:
        raise SolidWorksReplayError(
            "child features require a semantic target such as 'base.top'"
        )
    parent_id, requested_reference = target.split(".", 1)
    reference = _semantic_reference_name(feature, requested_reference)
    frame = _support_frame(feature)
    snapshot = feature.support_reference or {}
    metadata = snapshot.get("reference", {}).get("metadata", {})
    instance_name = metadata.get("instance_name")
    if instance_name:
        target_feature_name = native_feature_names.get(parent_id)
        if target_feature_name is None:
            raise SolidWorksReplayError(
                f"target '{target}' references an unknown native parent feature"
            )
        return {
            "kind": "resolved_feature_face",
            "parent_feature_id": parent_id,
            "reference": reference,
            "target_feature_name": target_feature_name,
            "entity_name": _native_entity_name(
                target_feature_name,
                f"{instance_name}_{reference}",
            ),
            "frame": frame,
        }
    entity_name = published_faces.get(parent_id, {}).get(reference)
    if entity_name is None:
        if native_feature_names.get(parent_id) is None:
            raise SolidWorksReplayError(
                f"target '{target}' references an unknown native parent feature"
            )
        return _axis_aligned_offset_plane_support(
            feature,
            parent_id=parent_id,
            support_feature_name=feature_name,
            reference=reference,
            frame=frame,
        )
    return {
        "kind": "named_face",
        "parent_feature_id": parent_id,
        "reference": reference,
        "entity_name": entity_name,
        "frame": frame,
    }


def _axis_aligned_offset_plane_support(
    feature: EditableFeatureDefinition,
    *,
    parent_id: str,
    support_feature_name: str,
    reference: str,
    frame: dict,
) -> dict:
    """Represent a virtual cardinal face as a stable native datum plane.

    Arbitrary profiles can expose useful tangent supports such as ``right``
    even when no planar B-rep face exists there.  The editable feature graph
    already stores the exact support frame.  Replaying that frame as an offset
    of the matching primary datum plane avoids rediscovering topology from the
    final body and works uniformly for all six world directions.
    """
    normal = _normalize(frame["normal"])
    best_match: tuple[float, str, dict] | None = None
    for plane, specification in DATUM_PLANE_SUPPORTS.items():
        datum_normal = _normalize(specification["frame"]["normal"])
        alignment = abs(_dot(normal, datum_normal))
        if best_match is None or alignment > best_match[0]:
            best_match = (alignment, plane, specification)

    if best_match is None or best_match[0] < 1 - 1e-6:
        raise SolidWorksReplayError(
            f"target '{feature.target}' has no published native face and its "
            "virtual support is not parallel to a primary datum plane"
        )

    _, semantic_plane, specification = best_match
    datum_frame = specification["frame"]
    datum_normal = _normalize(datum_frame["normal"])
    origin_delta = [
        float(frame["origin_mm"][index])
        - float(datum_frame["origin_mm"][index])
        for index in range(3)
    ]
    signed_offset = _dot(origin_delta, datum_normal)
    desired_direction = normal
    if feature.operation_type in {"cut", "countersink"}:
        desired_direction = _scale(normal, -1)
    reverse_direction = _dot(desired_direction, datum_normal) < 0

    if abs(signed_offset) <= 1e-9:
        return {
            "kind": "datum_plane",
            "name": specification["name"],
            "semantic_plane": semantic_plane,
            "parent_feature_id": parent_id,
            "reference": reference,
            "reverse_direction": reverse_direction,
            "frame": frame,
        }

    return {
        "kind": "offset_plane",
        "name": f"{support_feature_name}_SupportPlane",
        "datum_name": specification["name"],
        "semantic_plane": semantic_plane,
        "parent_feature_id": parent_id,
        "reference": reference,
        "offset_mm": abs(signed_offset),
        "flip_offset": signed_offset < 0,
        "reverse_direction": reverse_direction,
        "frame": frame,
    }


def _datum_plane_support(plane: str) -> dict:
    specification = DATUM_PLANE_SUPPORTS.get(plane)
    if specification is None:
        raise SolidWorksReplayError(
            f"datum plane '{plane}' is not supported; use XY, XZ, or YZ"
        )
    return {
        "kind": "datum_plane",
        "name": specification["name"],
        "semantic_plane": plane,
        "frame": specification["frame"],
    }


def _support_frame(feature: EditableFeatureDefinition) -> dict:
    snapshot = feature.support_reference or {}
    if snapshot.get("kind") != "reference":
        raise SolidWorksReplayError(
            f"target '{feature.target}' does not resolve to one planar reference"
        )
    reference = snapshot.get("reference", {})
    if reference.get("kind") != "plane":
        raise SolidWorksReplayError(
            f"target '{feature.target}' is not a planar sketch support"
        )
    frame = reference.get("frame", {})
    return {
        "origin_mm": [float(value) for value in frame["origin"]],
        "x_axis": [float(value) for value in frame["x_axis"]],
        "normal": [float(value) for value in frame["normal"]],
    }


def _semantic_reference_name(
    feature: EditableFeatureDefinition,
    requested_reference: str,
) -> str:
    snapshot = feature.support_reference or {}
    reference = snapshot.get("reference", {})
    semantic_label = reference.get("metadata", {}).get("semantic_label")
    if semantic_label:
        return semantic_label
    aliases = {
        "flat": "top",
        "flat_face": "top",
        "curved": "outer_surface",
        "curved_surface": "outer_surface",
        "side": "front",
    }
    return aliases.get(requested_reference, requested_reference)


def _published_reference_specs(
    feature: EditableFeatureDefinition,
    support: dict,
    feature_name: str,
) -> tuple[dict, ...]:
    """Return extensible native entity-publication instructions.

    The replay plan describes *how* to resolve each entity instead of relying
    on fixed fields such as ``top`` or ``right``.  Face and edge selectors can
    therefore share this contract as the reference vocabulary grows.
    """
    operation_type = feature.operation_type
    if operation_type not in {"extrude", "add_extrude", "revolve", "add_revolve"}:
        return ()

    profile = feature.source_operation.get("profile")
    if operation_type in {"revolve", "add_revolve"}:
        created = set(feature.created_references)
        semantics = []
        if f"{feature.id}.face.f001" in created:
            semantics.append("front")
        if f"{feature.id}.face.f002" in created:
            semantics.append("back")
        if f"{feature.id}.surface.s001" in created:
            semantics.append("outer_surface")
    elif profile == "rectangle":
        semantics = ["top", "front", "back", "left", "right"]
        if operation_type == "extrude":
            semantics.append("bottom")
    elif profile == "circle":
        semantics = ["top", "outer_surface"]
        if operation_type == "extrude":
            semantics.append("bottom")
    elif profile == "polygon":
        semantics = ["top"]
        if operation_type == "extrude":
            semantics.append("bottom")
    else:
        # The support interface of a merged additive feature is consumed by
        # the union and is not a native face that can be named persistently.
        # A standalone base extrusion still owns its bottom face.
        semantics = ["top"]
        if operation_type == "extrude":
            semantics.append("bottom")
    directions = _published_face_directions(feature, support)
    references = []
    for semantic in semantics:
        selector = (
            {"kind": "largest_non_planar_face"}
            if semantic == "outer_surface"
            else {
                "kind": "planar_face_direction",
                "direction": directions[semantic],
            }
        )
        references.append(
            {
                "reference_id": f"{feature.id}.{semantic}",
                "semantic_name": semantic,
                "entity_name": _native_entity_name(feature_name, semantic),
                "entity_type": "face",
                "selector": selector,
            }
        )
    references.extend(
        _actual_planar_face_reference_specs(feature, feature_name)
    )
    return tuple(references)


def _actual_planar_face_reference_specs(
    feature: EditableFeatureDefinition,
    feature_name: str,
) -> list[dict]:
    """Publish topology-derived planar sides with geometric selectors.

    Cardinal names remain convenient aliases, but arbitrary profiles can own
    any number of sloped faces.  Their stable graph snapshots carry enough
    geometry to identify the corresponding native SOLIDWORKS face without
    assuming a particular profile or world-axis orientation.
    """
    references = []
    for snapshot in feature.created_reference_snapshots:
        metadata = snapshot.get("metadata", {})
        if metadata.get("reference_type") not in {
            "actual_planar_side_face",
            "actual_planar_revolve_face",
        }:
            continue

        semantic_name = metadata["semantic_label"]
        instance_name = metadata.get("instance_name")
        published_semantic = semantic_name
        entity_semantic = semantic_name
        if instance_name:
            published_semantic = f"{instance_name}.{semantic_name}"
            entity_semantic = f"{instance_name}_{semantic_name}"

        frame = snapshot["frame"]
        references.append(
            {
                "reference_id": snapshot["name"],
                "semantic_name": published_semantic,
                "entity_name": _native_entity_name(
                    feature_name,
                    entity_semantic,
                ),
                "entity_type": "face",
                "selector": {
                    "kind": "planar_face_geometry",
                    "direction": [
                        float(value) for value in frame["normal"]
                    ],
                    "center_mm": [
                        float(value) for value in metadata["center"]
                    ],
                    "area_mm2": float(metadata["area"]),
                },
            }
        )
    return references


def _published_face_directions(
    feature: EditableFeatureDefinition,
    support: dict,
) -> dict[str, list[float]]:
    frame = support.get("frame") or {}
    normal = [float(value) for value in frame.get("normal", [0, 0, 1])]
    x_axis = [float(value) for value in frame.get("x_axis", [1, 0, 0])]
    y_axis = _cross(normal, x_axis)
    front = y_axis
    if feature.operation_type in {"revolve", "add_revolve"}:
        operation = feature.source_operation
        axis_start = operation["axis_start"]
        axis_end = operation["axis_end"]
        front = _normalize(
            _add(
                _scale(x_axis, float(axis_end[0]) - float(axis_start[0])),
                _scale(y_axis, float(axis_end[1]) - float(axis_start[1])),
            )
        )
    return {
        "top": normal,
        "bottom": _scale(normal, -1.0),
        "right": x_axis,
        "left": _scale(x_axis, -1.0),
        "front": front,
        "back": _scale(front, -1.0),
    }


def _cross(left: list[float], right: list[float]) -> list[float]:
    return [
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    ]


def _dot(left: list[float], right: list[float]) -> float:
    return sum(left[index] * right[index] for index in range(3))


def _add(left: list[float], right: list[float]) -> list[float]:
    return [left[index] + right[index] for index in range(3)]


def _scale(vector: list[float], factor: float) -> list[float]:
    return [value * factor for value in vector]


def _normalize(vector: list[float]) -> list[float]:
    magnitude = sum(value * value for value in vector) ** 0.5
    if magnitude <= 1e-12:
        raise SolidWorksReplayError("native reference direction cannot be zero")
    return [value / magnitude for value in vector]


def _dimension(
    feature: EditableFeatureDefinition,
    *,
    parameter_id: str,
    fallback_name: str,
    value: float,
    unit: str = "mm",
    signed_source_value: float | None = None,
) -> dict:
    parameter = next(
        (
            item
            for item in feature.parameters
            if item.id == parameter_id
        ),
        None,
    )
    source_parameter_id = parameter.id if parameter is not None else parameter_id
    dimension = {
        "parameter_id": source_parameter_id,
        "native_name": _dimension_name(source_parameter_id, fallback_name),
        "value_mm": value,
        "unit": unit,
    }
    if signed_source_value is not None:
        dimension["mutation_mode"] = "absolute_same_side"
        dimension["source_value"] = float(signed_source_value)
    return dimension


def _unique_feature_name(
    feature: EditableFeatureDefinition,
    used_names: set[str],
) -> str:
    feature_id = feature.id
    suffixes = _owned_native_name_suffixes(feature)
    base_name = f"P2P_{_safe_token(feature_id)}"
    if not _native_name_conflicts(base_name, suffixes, used_names):
        return base_name

    digest = sha1(feature_id.encode("utf-8")).hexdigest()[:6]
    candidate = f"{base_name}_{digest}"
    if _native_name_conflicts(candidate, suffixes, used_names):
        raise SolidWorksReplayError(
            f"feature id '{feature_id}' cannot be converted into a unique native name"
        )
    return candidate


def _owned_native_name_suffixes(
    feature: EditableFeatureDefinition,
) -> tuple[str, ...]:
    """List every feature-tree name a replay step will own."""
    suffixes = [""]
    if feature.operation_type not in {"chamfer", "fillet"}:
        suffixes.append("_Sketch")
    if feature.target and feature.operation_type not in {"chamfer", "fillet"}:
        suffixes.append("_SupportPlane")
    pattern = feature.source_operation.get("pattern")
    if not isinstance(pattern, dict):
        return tuple(suffixes)
    suffixes.append("_Seed")
    pattern_type = pattern.get("type")
    if pattern_type in {"circular", "linear"}:
        suffixes.append("_References")
    if pattern_type == "circular":
        suffixes.append("_Axis")
    elif pattern_type == "mirror":
        suffixes.append("_MirrorPositions")
    return tuple(suffixes)


def _native_name_conflicts(
    base_name: str,
    suffixes: tuple[str, ...],
    used_names: set[str],
) -> bool:
    return any(f"{base_name}{suffix}".casefold() in used_names for suffix in suffixes)


def _owned_native_names(feature: SolidWorksReplayFeature) -> tuple[str, ...]:
    """Read all explicit feature-tree names from one replay step."""
    names = [feature.feature_name]
    if feature.sketch_name:
        names.append(feature.sketch_name)
    if feature.support.get("kind") == "offset_plane":
        names.append(feature.support["name"])
    pattern = feature.pattern
    if pattern is not None:
        for field_name in (
            "seed_feature_name",
            "reference_sketch_name",
            "axis_name",
            "placement_sketch_name",
        ):
            name = pattern.get(field_name)
            if name:
                names.append(name)
    return tuple(names)


def _validate_replay_plan_contract(plan: SolidWorksReplayPlan) -> None:
    """Reject ambiguous names and IDs before external CAD is opened."""
    feature_ids = [feature.id for feature in plan.features]
    if len(feature_ids) != len(set(feature_ids)):
        raise SolidWorksReplayError("native replay contains duplicate feature IDs")

    owned_names = [
        name
        for feature in plan.features
        for name in _owned_native_names(feature)
    ]
    folded_names = [name.casefold() for name in owned_names]
    if len(folded_names) != len(set(folded_names)):
        raise SolidWorksReplayError(
            "native replay contains case-insensitive feature-tree name collisions"
        )
    owned_name_set = set(folded_names)

    bindings = [
        binding
        for feature in plan.features
        for binding in feature.parameter_bindings
    ]
    parameter_ids = [binding["parameter_id"] for binding in bindings]
    if len(parameter_ids) != len(set(parameter_ids)):
        raise SolidWorksReplayError(
            "native replay contains duplicate parameter IDs"
        )
    qualified_native_names = [
        (
            binding["owner_name"].casefold(),
            binding["native_name"].casefold(),
        )
        for binding in bindings
    ]
    if len(qualified_native_names) != len(set(qualified_native_names)):
        raise SolidWorksReplayError(
            "native replay contains duplicate qualified parameter names"
        )
    missing_owners = sorted(
        {
            binding["owner_name"]
            for binding in bindings
            if binding["owner_name"].casefold() not in owned_name_set
        }
    )
    if missing_owners:
        raise SolidWorksReplayError(
            "native parameter bindings reference unknown owners: "
            + ", ".join(missing_owners)
        )

    references = [
        reference
        for feature in plan.features
        for reference in feature.publish_references
    ]
    reference_ids = [reference["reference_id"] for reference in references]
    if len(reference_ids) != len(set(reference_ids)):
        raise SolidWorksReplayError(
            "native replay contains duplicate semantic reference IDs"
        )
    entity_names = [reference["entity_name"].casefold() for reference in references]
    if len(entity_names) != len(set(entity_names)):
        raise SolidWorksReplayError(
            "native replay contains duplicate native entity names"
        )


def _dimension_name(parameter_id: str, fallback_name: str) -> str:
    token = _safe_token(parameter_id) or _safe_token(fallback_name)
    return f"P2P_{token}"


def _native_entity_name(feature_name: str, reference: str) -> str:
    return f"{feature_name}_{_safe_token(reference)}"


def _safe_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value)).strip("_")
    return token or "feature"
