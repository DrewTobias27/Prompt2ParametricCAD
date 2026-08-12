"""Run the deterministic prompt-to-native-CAD release parity matrix.

The live API remains probabilistic, so release gating uses checked-in golden
prompt-to-intent examples.  Each example then traverses the exact production
lowering, CadQuery, STEP, editable-model, and SOLIDWORKS replay-plan layers.
This separates model-quality evaluation from backend parity regressions while
keeping both tied to the same human-readable prompts.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import time

import cadquery as cq

from prompt2cad.candidate_evaluation import evaluate_design_intent_candidate
from prompt2cad.editable_model import model_data_to_editable_document
from prompt2cad.editable_model import rebuild_with_parameter_updates
from prompt2cad.exporter import export_step
from prompt2cad.interpreter import build_model
from prompt2cad.solidworks_replay import build_solidworks_replay_plan
from prompt2cad.solidworks_smoke import compare_geometry_metrics
from prompt2cad.solidworks_smoke import geometry_metrics
from prompt2cad.solidworks_smoke import native_parameter_coverage
from prompt2cad.training_data import DEFAULT_INTENT_EXAMPLES_DIR
from prompt2cad.training_data import load_intent_examples


@dataclass(frozen=True)
class ReleaseMatrixCase:
    """One golden prompt/intent example and a safe editability probe."""

    name: str
    mutations: dict[str, float | int]


RELEASE_MATRIX_CASES = (
    ReleaseMatrixCase(
        "rectangular_plate_corner_holes",
        {"corner_holes.sketch.diameter": 7},
    ),
    ReleaseMatrixCase(
        "counterbored_bolt_circle",
        {"counterbores.feature.depth": 5},
    ),
    ReleaseMatrixCase(
        "two_wall_u_bracket",
        {
            "left_wall_hole.sketch.diameter": 9,
            "right_wall_hole.sketch.diameter": 9,
        },
    ),
    ReleaseMatrixCase(
        "shaft_collars_grooves_chamfers",
        {"rear_collar.sketch.width": 8},
    ),
    ReleaseMatrixCase(
        "half_cylinder_cradle_mounting_plate",
        {
            "base.sketch.height": 105,
            "mounting_holes.pattern.spacing_1": 50,
        },
    ),
    ReleaseMatrixCase(
        "cross_arm_hub_plate",
        {"central_hub.feature.distance": 20},
    ),
    ReleaseMatrixCase(
        "open_top_drainage_tray",
        {"front_wall.feature.distance": 22},
    ),
)


def run_release_matrix(
    output_root: Path,
    *,
    case_names: tuple[str, ...] | None = None,
    examples_dir: Path = DEFAULT_INTENT_EXAMPLES_DIR,
) -> dict:
    """Run selected golden examples through every deterministic CAD stage."""
    available_cases = {case.name: case for case in RELEASE_MATRIX_CASES}
    selected_names = case_names or tuple(available_cases)
    unknown = sorted(set(selected_names) - set(available_cases))
    if unknown:
        raise ValueError("Unknown release matrix cases: " + ", ".join(unknown))

    examples = {
        example["name"]: example
        for example in load_intent_examples(examples_dir)
    }
    missing_examples = sorted(set(selected_names) - set(examples))
    if missing_examples:
        raise FileNotFoundError(
            "Missing golden prompt/intent examples: "
            + ", ".join(missing_examples)
        )

    output_root.mkdir(parents=True, exist_ok=True)
    results = [
        run_release_case(
            available_cases[name],
            examples[name],
            output_root,
        )
        for name in selected_names
    ]
    passed = sum(result["status"] == "pass" for result in results)
    return {
        "format": "prompt2cad.release-parity-matrix",
        "version": 1,
        "pipeline": [
            "golden_prompt",
            "design_intent",
            "operation_json",
            "cadquery_geometry",
            "step_round_trip",
            "editable_parameter_rebuild",
            "solidworks_replay_plan",
        ],
        "case_count": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }


def run_release_case(
    case: ReleaseMatrixCase,
    example: dict,
    output_root: Path,
) -> dict:
    """Run one case and keep a stage-specific failure instead of stopping."""
    started = time.perf_counter()
    stage = "golden_prompt"
    result = {
        "name": case.name,
        "prompt": example["prompt"],
        "intent_source": f"training/intent_examples/{example['source_file']}",
        "status": "fail",
        "checks": {},
    }
    try:
        if not example["prompt"].strip():
            raise ValueError("Golden prompt is empty")
        result["checks"][stage] = {"passed": True}

        stage = "design_intent"
        evaluation = evaluate_design_intent_candidate(example["design_intent"])
        if not evaluation["passed"]:
            raise ValueError(json.dumps(evaluation["feedback"], sort_keys=True))
        model_data = evaluation["model_data"]
        result["checks"][stage] = {
            "passed": True,
            "intent_alignment_passed": evaluation["intent_alignment"]["passed"],
            "concept_coverage_failures": len(
                evaluation["intent_coverage_failures"]
            ),
        }

        stage = "operation_json"
        model_path = output_root / f"{case.name}.model.json"
        model_path.write_text(
            json.dumps(model_data, indent=2) + "\n",
            encoding="utf-8",
        )
        result["checks"][stage] = {
            "passed": True,
            "operation_count": len(model_data["operations"]),
            "quality_passed": evaluation["quality_report"]["passed"],
            "operation_effects_passed": evaluation["operation_effects"]["passed"],
        }

        stage = "cadquery_geometry"
        part = build_model(model_data)
        source_metrics = geometry_metrics(part)
        result["checks"][stage] = {
            "passed": True,
            **source_metrics,
        }

        stage = "step_round_trip"
        step_path = export_step(part, output_root / f"{case.name}.step")
        imported_part = cq.importers.importStep(str(step_path))
        step_comparison = compare_geometry_metrics(
            source_metrics,
            geometry_metrics(imported_part),
        )
        result["checks"][stage] = {
            **step_comparison,
            "artifact": str(step_path),
        }

        stage = "editable_parameter_rebuild"
        document = model_data_to_editable_document(model_data)
        edited_part, edited_document = rebuild_with_parameter_updates(
            document,
            case.mutations,
        )
        edited_metrics = geometry_metrics(edited_part)
        if edited_metrics == source_metrics:
            raise ValueError("Declared parameter mutations did not change geometry")
        if edited_document.build_order != document.build_order:
            raise ValueError("Parameter rebuild changed feature build order")
        result["checks"][stage] = {
            "passed": True,
            "mutations": case.mutations,
            "editable_format_version": document.format_version,
            "parameter_count": sum(
                len(feature.parameters) for feature in document.features
            ),
        }

        stage = "solidworks_replay_plan"
        plan = build_solidworks_replay_plan(document)
        plan_path = output_root / f"{case.name}.solidworks-plan.json"
        plan_path.write_text(
            json.dumps(plan.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
        coverage = native_parameter_coverage(
            model_data,
            plan,
            document=document,
        )
        bound_ids = {
            binding["parameter_id"]
            for feature in plan.features
            for binding in feature.parameter_bindings
        }
        unbound_mutations = sorted(set(case.mutations) - bound_ids)
        if unbound_mutations:
            raise ValueError(
                "Editability probe parameters lack native bindings: "
                + ", ".join(unbound_mutations)
            )
        result["checks"][stage] = {
            "passed": True,
            "native_feature_count": len(plan.features),
            "native_parameter_coverage": coverage,
            "published_reference_count": sum(
                len(feature.publish_references) for feature in plan.features
            ),
            "artifact": str(plan_path),
        }
        result["status"] = "pass"
    except Exception as error:  # Preserve every case in one release report.
        result["failed_stage"] = stage
        result["error_type"] = type(error).__name__
        result["error"] = str(error)

    result["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    return result


def parse_args() -> argparse.Namespace:
    """Parse release-matrix command-line options."""
    parser = argparse.ArgumentParser(
        description="Run deterministic prompt-to-STEP-to-SOLIDWORKS parity gates."
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("generated/release-matrix"),
    )
    parser.add_argument(
        "--case",
        action="append",
        choices=[case.name for case in RELEASE_MATRIX_CASES],
        help="Run one case; repeat to select several. Defaults to all.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the matrix, write its report, and fail on any broken stage."""
    args = parse_args()
    report = run_release_matrix(
        args.output_root,
        case_names=tuple(args.case) if args.case else None,
    )
    report_path = args.output_root / "report.json"
    report_path.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    for result in report["results"]:
        detail = ""
        if result["status"] == "fail":
            detail = f" at {result['failed_stage']}: {result['error']}"
        print(f"{result['status'].upper()} {result['name']}{detail}")
    print(
        f"RESULTS pass={report['passed']} fail={report['failed']} "
        f"total={report['case_count']}"
    )
    print(f"WROTE {report_path}")
    if report["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
