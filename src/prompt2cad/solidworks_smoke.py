"""Run deterministic STEP-to-SOLIDWORKS parity smoke fixtures."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
import json
from pathlib import Path
import time

from prompt2cad.exporter import export_step
from prompt2cad.editable_model import build_editable_model_document
from prompt2cad.editable_model import rebuild_with_parameter_updates
from prompt2cad.loader import load_model
from prompt2cad.solidworks_export import materialize_stable_feature_ids
from prompt2cad.solidworks_editability import native_parameter_coverage
from prompt2cad.solidworks_export import save_plan
from prompt2cad.solidworks_replay import build_solidworks_replay_plan
from prompt2cad.solidworks_replay import export_solidworks_part
from prompt2cad.solidworks_replay import SUPPORTED_OPERATION_TYPES
from prompt2cad.solidworks_replay import SUPPORTED_PROFILE_TYPES
from prompt2cad.solidworks_replay import validate_solidworks_mutations
from prompt2cad.solidworks_replay import verify_solidworks_editability
from prompt2cad.solidworks_verification import compare_geometry_metrics
from prompt2cad.solidworks_verification import geometry_metrics
from prompt2cad.solidworks_verification import validate_native_build_result
from prompt2cad.solidworks_verification import validate_native_editability_result
from prompt2cad.solidworks_verification import validate_published_references


SMOKE_FIXTURE_NAMES = (
    "solidworks_smoke_patterned_plate",
    "solidworks_smoke_circular_pattern",
    "solidworks_smoke_linear_pattern",
    "solidworks_smoke_side_features",
    "solidworks_smoke_revolved_shaft",
    "solidworks_smoke_edge_details",
    "solidworks_smoke_freeform_edges",
    "solidworks_smoke_coordinate_profiles",
    "solidworks_smoke_arc_revolve",
    "solidworks_smoke_partial_revolve",
)

EDITABILITY_SCENARIOS = {
    "solidworks_smoke_patterned_plate": {
        "base.sketch.width": 120,
        "bosses.placement.inst001.x": 34,
        "bosses.placement.inst001.y": 22,
        "bosses.feature.distance": 10,
        "mounting_holes.feature.diameter": 6,
    },
    "solidworks_smoke_circular_pattern": {
        "base.feature.distance": 10,
        "radial_posts.sketch.diameter": 14,
        "radial_posts.feature.distance": 10,
        "radial_posts.pattern.count": 7,
        "radial_posts.pattern.total_angle": 300,
        "fourth_post_hole.sketch.diameter": 5,
    },
    "solidworks_smoke_linear_pattern": {
        "base.sketch.width": 130,
        "mounting_pads.sketch.width": 16,
        "mounting_pads.feature.distance": 9,
        "mounting_pads.pattern.count_1": 4,
        "mounting_pads.pattern.spacing_1": 30,
        "mounting_pads.pattern.count_2": 3,
        "mounting_pads.pattern.spacing_2": 25,
        "sixth_pad_hole.sketch.diameter": 5,
    },
    "solidworks_smoke_side_features": {
        "base.sketch.width": 90,
        "right_tab.feature.distance": 10,
        "tab_hole.sketch.diameter": 5,
    },
    "solidworks_smoke_revolved_shaft": {
        "shaft.sketch.height": 90,
        "collar.sketch.width": 5,
        "groove.sketch.height": 8,
        "end_bore.sketch.diameter": 7,
    },
    "solidworks_smoke_edge_details": {
        "corner_fillets.feature.radius": 5,
        "boss.sketch.width": 34,
        "boss_chamfer.feature.distance": 1.5,
    },
    "solidworks_smoke_freeform_edges": {
        "base.feature.distance": 15,
        "top_edge_chamfer.feature.distance": 2.5,
    },
    "solidworks_smoke_coordinate_profiles": {
        "base.feature.distance": 10,
        "hex_boss.sketch.diameter": 28,
        "hex_boss.feature.distance": 12,
    },
    "solidworks_smoke_arc_revolve": {
        "capsule.feature.angle": 270,
    },
    "solidworks_smoke_partial_revolve": {
        "half_cylinder.sketch.height": 60,
        "half_cylinder.feature.angle": 220,
    },
}

NATIVE_GATE_REQUIRED_COVERAGE = {
    "operation_types": set(SUPPORTED_OPERATION_TYPES),
    "source_profiles": set(SUPPORTED_PROFILE_TYPES),
    "support_kinds": {
        "datum_plane",
        "feature_edges",
        "named_face",
        "resolved_feature_face",
    },
    "pattern_kinds": {
        "circular_pattern",
        "linear_pattern",
        "mirror_pattern",
    },
    "feature_kinds": {
        "boss_extrude",
        "boss_revolve",
        "countersink",
        "cut_extrude",
        "cut_revolve",
        "edge_chamfer",
        "edge_fillet",
    },
    "end_conditions": {"blind", "through_all"},
    "binding_kinds": {"feature_property", "named_dimension"},
    "binding_units": {"count", "deg", "mm"},
    "mutation_modes": {"absolute_same_side"},
}

NATIVE_EDIT_REQUIRED_COVERAGE = {
    "binding_kinds": {"feature_property", "named_dimension"},
    "binding_units": {"count", "deg", "mm"},
    "owner_kinds": {"feature", "pattern", "sketch"},
    "pattern_kinds": {
        "circular_pattern",
        "linear_pattern",
        "mirror_pattern",
    },
    "pattern_properties": {
        "D1Spacing",
        "D1TotalInstances",
        "D2Spacing",
        "D2TotalInstances",
        "Spacing",
        "TotalInstances",
    },
    "mutation_modes": {"absolute_same_side"},
}


def project_root() -> Path:
    """Return the repository root for an editable or installed source tree."""
    return Path(__file__).resolve().parents[2]


def smoke_fixture_paths(
    fixture_names: Sequence[str] | None = None,
    *,
    root: Path | None = None,
) -> tuple[Path, ...]:
    """Resolve requested fixture names and reject unknown suite members."""
    selected = tuple(fixture_names or SMOKE_FIXTURE_NAMES)
    unknown = sorted(set(selected) - set(SMOKE_FIXTURE_NAMES))
    if unknown:
        raise ValueError("Unknown SOLIDWORKS smoke fixture(s): " + ", ".join(unknown))

    model_root = (root or project_root()) / "examples" / "models"
    paths = tuple(model_root / f"{name}.json" for name in selected)
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Missing SOLIDWORKS smoke fixture(s): " + ", ".join(missing)
        )
    return paths


def run_smoke_suite(
    fixture_paths: Sequence[Path],
    output_root: Path,
    *,
    execute_native: bool = False,
    visible: bool = False,
    template_path: Path | None = None,
    native_exporter: Callable[..., Path] = export_solidworks_part,
    verify_editability: bool = False,
    editability_verifier: Callable[..., Path] = verify_solidworks_editability,
) -> dict:
    """Build STEP, plan native replay, and optionally execute each fixture."""
    output_root.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    observed_coverage = {
        category: set() for category in NATIVE_GATE_REQUIRED_COVERAGE
    }
    observed_edit_coverage = {
        category: set() for category in NATIVE_EDIT_REQUIRED_COVERAGE
    }

    for fixture_path in fixture_paths:
        started = time.perf_counter()
        name = fixture_path.stem
        step_path = output_root / f"{name}.step"
        plan_path = output_root / f"{name}.plan.json"
        native_path = output_root / f"{name}.SLDPRT"
        native_result_path = output_root / f"{name}.native-result.json"
        mutated_native_path = output_root / f"{name}.mutated.SLDPRT"
        editability_result_path = output_root / f"{name}.editability-result.json"
        result = {
            "name": name,
            "fixture": str(fixture_path),
            "status": "fail",
            "step_path": str(step_path),
            "plan_path": str(plan_path),
            "native_path": str(native_path) if execute_native else None,
            "native_result_path": (
                str(native_result_path) if execute_native else None
            ),
            "native_executed": execute_native,
        }
        try:
            model_data = materialize_stable_feature_ids(
                load_model(fixture_path)
            )
            part, source_document = build_editable_model_document(model_data)
            export_step(part, step_path)
            cadquery_metrics = geometry_metrics(part)
            result["cadquery_geometry"] = cadquery_metrics

            plan = build_solidworks_replay_plan(
                source_document,
                expected_geometry=cadquery_metrics,
            )
            _record_native_gate_coverage(
                observed_coverage,
                model_data,
                plan,
            )
            save_plan(plan, plan_path)
            result["operation_count"] = len(model_data["operations"])
            result["native_feature_count"] = len(plan.features)
            result["native_operation_types"] = [
                feature.operation_type for feature in plan.features
            ]
            result["native_parameter_coverage"] = native_parameter_coverage(
                model_data,
                plan,
                document=source_document,
            )
            mutations = EDITABILITY_SCENARIOS.get(name)
            result["native_mutation_preflight"] = (
                validate_solidworks_mutations(plan, mutations)
                if mutations is not None
                else None
            )
            if mutations is not None:
                _record_native_edit_coverage(
                    observed_edit_coverage,
                    plan,
                    mutations,
                )

            if execute_native:
                native_exporter(
                    plan,
                    native_path,
                    visible=visible,
                    template_path=template_path,
                    result_output_path=native_result_path,
                )
                if not native_path.is_file():
                    raise RuntimeError(
                        "Native exporter returned without creating the SLDPRT file"
                    )
                if not native_result_path.is_file():
                    raise RuntimeError(
                        "Native exporter did not create its geometry result"
                    )
                native_result = json.loads(
                    native_result_path.read_text(encoding="utf-8")
                )
                native_contract = validate_native_build_result(
                    plan,
                    native_result,
                    context="native replay",
                )
                result["native_contract"] = native_contract
                native_reference_summary = validate_published_references(
                    plan,
                    native_result,
                    context="native replay",
                )
                result["published_references"] = native_reference_summary
                native_metrics = native_result.get("geometry", {})
                result["solidworks_geometry"] = native_metrics
                result["geometry_comparison"] = compare_geometry_metrics(
                    cadquery_metrics,
                    native_metrics,
                )
                if verify_editability and mutations is not None:
                    expected_part, _ = rebuild_with_parameter_updates(
                        source_document,
                        mutations,
                    )
                    expected_edited_metrics = geometry_metrics(expected_part)
                    editability_verifier(
                        plan,
                        native_path,
                        mutated_native_path,
                        mutations,
                        expected_geometry=expected_edited_metrics,
                        visible=visible,
                        result_output_path=editability_result_path,
                    )
                    editability_result = json.loads(
                        editability_result_path.read_text(encoding="utf-8")
                    )
                    editability_contract = validate_native_editability_result(
                        plan,
                        editability_result,
                        expected_mutation_ids=mutations,
                        context="editability reopen",
                    )
                    editability_reference_summary = validate_published_references(
                        plan,
                        editability_result,
                        context="editability source-reference preservation",
                    )
                    result["editability"] = {
                        "mutations": mutations,
                        "mutated_native_path": str(mutated_native_path),
                        "result_path": str(editability_result_path),
                        "geometry_comparison": compare_geometry_metrics(
                            expected_edited_metrics,
                            editability_result.get("after_geometry", {}),
                        ),
                        "health": editability_result.get("health"),
                        "native_contract": editability_contract,
                        "published_references": editability_reference_summary,
                        "reopened": True,
                    }
            result["status"] = "pass"
        except Exception as error:  # Keep later fixtures running for one report.
            result["error_type"] = type(error).__name__
            result["error"] = str(error)
        result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        results.append(result)

    passed = sum(result["status"] == "pass" for result in results)
    complete_fixture_suite = (
        len(fixture_paths) == len(SMOKE_FIXTURE_NAMES)
        and {path.stem for path in fixture_paths} == set(SMOKE_FIXTURE_NAMES)
    )
    coverage = _native_gate_coverage_summary(
        observed_coverage,
        complete_fixture_suite=complete_fixture_suite,
    )
    edit_coverage = _native_edit_coverage_summary(
        observed_edit_coverage,
        complete_fixture_suite=complete_fixture_suite,
    )
    failed = len(results) - passed
    return {
        "mode": "native" if execute_native else "plan_only",
        "passed": passed,
        "failed": failed,
        "native_gate_coverage": coverage,
        "native_edit_coverage": edit_coverage,
        "release_gate_passed": (
            failed == 0
            and (
                not complete_fixture_suite
                or (
                    coverage["passed"] is True
                    and edit_coverage["passed"] is True
                )
            )
        ),
        "results": results,
    }


def _record_native_gate_coverage(
    observed: dict[str, set[str]],
    model_data: dict,
    plan,
) -> None:
    """Collect executable replay families exercised by native gate fixtures."""
    observed["source_profiles"].update(
        operation["profile"]
        for operation in model_data["operations"]
        if operation.get("profile")
    )
    for feature in plan.features:
        observed["operation_types"].add(feature.operation_type)
        observed["support_kinds"].add(feature.support["kind"])
        feature_kind = feature.feature.get("kind")
        if feature_kind:
            observed["feature_kinds"].add(feature_kind)
        end_condition = feature.feature.get("end_condition")
        if end_condition:
            observed["end_conditions"].add(end_condition)
        if feature.pattern:
            observed["pattern_kinds"].add(feature.pattern["kind"])
        for binding in feature.parameter_bindings:
            observed["binding_kinds"].add(binding["binding_kind"])
            observed["binding_units"].add(binding["unit"])
            mutation_mode = binding.get("mutation_mode")
            if mutation_mode:
                observed["mutation_modes"].add(mutation_mode)


def _record_native_edit_coverage(
    observed: dict[str, set[str]],
    plan,
    mutations: dict[str, float],
) -> None:
    """Collect the exact native controls exercised by edit/reopen scenarios."""
    bindings = {
        binding["parameter_id"]: (feature, binding)
        for feature in plan.features
        for binding in feature.parameter_bindings
    }
    for parameter_id in mutations:
        feature, binding = bindings[parameter_id]
        observed["binding_kinds"].add(binding["binding_kind"])
        observed["binding_units"].add(binding["unit"])
        observed["owner_kinds"].add(binding["owner_kind"])
        mutation_mode = binding.get("mutation_mode")
        if mutation_mode:
            observed["mutation_modes"].add(mutation_mode)
        if feature.pattern:
            observed["pattern_kinds"].add(feature.pattern["kind"])
        if binding["owner_kind"] == "pattern":
            observed["pattern_properties"].update(
                binding.get("native_properties", [])
            )


def _native_gate_coverage_summary(
    observed: dict[str, set[str]],
    *,
    complete_fixture_suite: bool,
) -> dict:
    return _coverage_summary(
        observed,
        NATIVE_GATE_REQUIRED_COVERAGE,
        complete_fixture_suite=complete_fixture_suite,
    )


def _native_edit_coverage_summary(
    observed: dict[str, set[str]],
    *,
    complete_fixture_suite: bool,
) -> dict:
    return _coverage_summary(
        observed,
        NATIVE_EDIT_REQUIRED_COVERAGE,
        complete_fixture_suite=complete_fixture_suite,
    )


def _coverage_summary(
    observed: dict[str, set[str]],
    required: dict[str, set[str]],
    *,
    complete_fixture_suite: bool,
) -> dict:
    normalized_observed = {
        category: sorted(values) for category, values in observed.items()
    }
    missing = {
        category: sorted(expected - observed[category])
        for category, expected in required.items()
        if expected - observed[category]
    }
    return {
        "complete_fixture_suite": complete_fixture_suite,
        "passed": (not missing) if complete_fixture_suite else None,
        "observed": normalized_observed,
        "required": {
            category: sorted(values)
            for category, values in required.items()
        },
        "missing": missing,
    }


def save_report(report: dict, path: Path) -> Path:
    """Write a stable, readable smoke report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    """Parse smoke-suite arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Validate STEP/SOLIDWORKS parity fixtures and optionally replay "
            "them through an installed SOLIDWORKS application."
        )
    )
    parser.add_argument(
        "--fixture",
        action="append",
        choices=SMOKE_FIXTURE_NAMES,
        help="Run one named fixture; repeat to run several. Defaults to all.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("generated/solidworks_smoke"),
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Open SOLIDWORKS through COM and save native SLDPRT files.",
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Show SOLIDWORKS during native execution.",
    )
    parser.add_argument(
        "--verify-editability",
        action="store_true",
        help=(
            "For fixtures with mutation scenarios, reopen the native part, "
            "edit parameters, rebuild, save, reopen, and compare geometry."
        ),
    )
    parser.add_argument("--template", type=Path)
    return parser.parse_args()


def main() -> None:
    """Run the configured smoke suite and return a failing process status."""
    args = parse_args()
    fixtures = smoke_fixture_paths(args.fixture)
    report = run_smoke_suite(
        fixtures,
        args.output_root,
        execute_native=args.execute,
        visible=args.visible,
        template_path=args.template,
        verify_editability=args.verify_editability,
    )
    report_path = save_report(report, args.output_root / "report.json")
    for result in report["results"]:
        detail = f" ({result['error']})" if result["status"] == "fail" else ""
        print(f"{result['status'].upper()} {result['name']}{detail}")
    print(
        f"RESULTS pass={report['passed']} fail={report['failed']} "
        f"mode={report['mode']}"
    )
    print(f"WROTE {report_path}")
    if not report["release_gate_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
