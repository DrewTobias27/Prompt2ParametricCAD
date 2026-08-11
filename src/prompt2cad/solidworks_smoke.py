"""Run deterministic STEP-to-SOLIDWORKS parity smoke fixtures."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
import json
from pathlib import Path
import time

from prompt2cad.exporter import export_step
from prompt2cad.editable_model import model_data_to_editable_document
from prompt2cad.editable_model import rebuild_with_parameter_updates
from prompt2cad.interpreter import build_model
from prompt2cad.loader import load_model
from prompt2cad.schema import validate_model_data
from prompt2cad.solidworks_export import model_path_to_replay_plan
from prompt2cad.solidworks_export import save_plan
from prompt2cad.solidworks_replay import SolidWorksReplayPlan
from prompt2cad.solidworks_replay import export_solidworks_part
from prompt2cad.solidworks_replay import verify_solidworks_editability


SMOKE_FIXTURE_NAMES = (
    "solidworks_smoke_patterned_plate",
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
            model_data = load_model(fixture_path)
            validate_model_data(model_data)
            part = build_model(model_data)
            export_step(part, step_path)
            cadquery_metrics = geometry_metrics(part)
            result["cadquery_geometry"] = cadquery_metrics

            plan = model_path_to_replay_plan(fixture_path)
            save_plan(plan, plan_path)
            result["operation_count"] = len(model_data["operations"])
            result["native_feature_count"] = len(plan.features)
            result["native_operation_types"] = [
                feature.operation_type for feature in plan.features
            ]

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
                mutations = EDITABILITY_SCENARIOS.get(name)
                if verify_editability and mutations is not None:
                    source_document = model_data_to_editable_document(model_data)
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
                    if not editability_result.get("reopened"):
                        raise RuntimeError(
                            "Native editability verifier did not reopen the saved part"
                        )
                    if editability_result.get("mutation_count") != len(mutations):
                        raise RuntimeError(
                            "Native editability verifier did not apply every mutation"
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


def validate_published_references(
    plan: SolidWorksReplayPlan,
    native_result: dict,
    *,
    context: str,
) -> dict:
    """Require every planned semantic entity to retain a resolvable PID."""
    expected = {
        reference["reference_id"]
        for feature in plan.features
        for reference in feature.publish_references
    }
    records = native_result.get("published_references")
    if not isinstance(records, list):
        raise RuntimeError(f"{context} did not report persistent references")

    actual = {record.get("reference_id") for record in records}
    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        raise RuntimeError(
            f"{context} persistent-reference mismatch; "
            f"missing={missing}, unexpected={unexpected}"
        )
    invalid = [
        record.get("reference_id")
        for record in records
        if record.get("resolved") is not True
        or not record.get("persistent_id_base64")
    ]
    if invalid:
        raise RuntimeError(
            f"{context} has unresolved persistent references: "
            + ", ".join(str(reference_id) for reference_id in invalid)
        )
    return {
        "expected_count": len(expected),
        "resolved_count": len(records),
        "passed": True,
    }


def geometry_metrics(part) -> dict:
    """Measure the invariant geometry used to compare both CAD kernels."""
    solids = list(part.solids().vals())
    bounding_box = part.val().BoundingBox()
    return {
        "solid_body_count": len(solids),
        "volume_mm3": sum(float(solid.Volume()) for solid in solids),
        "bounding_box_mm": [
            float(bounding_box.xmin),
            float(bounding_box.ymin),
            float(bounding_box.zmin),
            float(bounding_box.xmax),
            float(bounding_box.ymax),
            float(bounding_box.zmax),
        ],
    }


def compare_geometry_metrics(cadquery: dict, solidworks: dict) -> dict:
    """Reject material or envelope differences large enough to change a part."""
    if solidworks.get("solid_body_count") != cadquery["solid_body_count"]:
        raise RuntimeError(
            "SolidWorks body count does not match the CadQuery result"
        )

    expected_volume = float(cadquery["volume_mm3"])
    native_volume = float(solidworks.get("volume_mm3", 0.0))
    relative_volume_error = abs(native_volume - expected_volume) / max(
        expected_volume,
        1.0,
    )
    if relative_volume_error > 0.005:
        raise RuntimeError(
            "SolidWorks volume differs from CadQuery by "
            f"{relative_volume_error:.2%}"
        )

    expected_box = cadquery["bounding_box_mm"]
    native_box = solidworks.get("bounding_box_mm")
    if not isinstance(native_box, list) or len(native_box) != 6:
        raise RuntimeError("SolidWorks did not report a valid bounding box")
    expected_spans = [
        expected_box[index + 3] - expected_box[index] for index in range(3)
    ]
    native_spans = [
        float(native_box[index + 3]) - float(native_box[index])
        for index in range(3)
    ]
    span_errors = [
        abs(native - expected)
        for native, expected in zip(native_spans, expected_spans)
    ]
    for error, expected in zip(span_errors, expected_spans):
        if error > max(0.5, abs(expected) * 0.01):
            raise RuntimeError(
                "SolidWorks bounding-box span does not match CadQuery"
            )
    return {
        "passed": True,
        "relative_volume_error": relative_volume_error,
        "span_errors_mm": span_errors,
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
