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
        "bosses.feature.distance": 10,
        "mounting_holes.feature.diameter": 6,
    },
    "solidworks_smoke_circular_pattern": {
        "base.feature.distance": 10,
        "radial_posts.sketch.diameter": 14,
        "radial_posts.feature.distance": 10,
        "fourth_post_hole.sketch.diameter": 5,
    },
    "solidworks_smoke_linear_pattern": {
        "base.sketch.width": 130,
        "mounting_pads.sketch.width": 16,
        "mounting_pads.feature.distance": 9,
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

            plan = build_solidworks_replay_plan(source_document)
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
                        context="editability reopen",
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
    return {
        "mode": "native" if execute_native else "plan_only",
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
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
    if report["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
