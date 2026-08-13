"""Export a supported editable model as a native SOLIDWORKS part."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

from prompt2cad.editable_model import build_editable_model_document
from prompt2cad.solidworks_replay import SolidWorksExecutionError
from prompt2cad.solidworks_replay import SolidWorksReplayError
from prompt2cad.solidworks_replay import SolidWorksReplayPlan
from prompt2cad.solidworks_replay import build_solidworks_replay_plan
from prompt2cad.solidworks_replay import export_solidworks_part
from prompt2cad.solidworks_verification import geometry_metrics


def load_json(path: Path) -> dict:
    """Load CAD operation JSON from disk."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_plan(plan: SolidWorksReplayPlan, path: Path) -> Path:
    """Write a readable replay-plan artifact for inspection or debugging."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(plan.to_dict(), file, indent=2)
        file.write("\n")
    return path


def model_path_to_replay_plan(model_path: Path) -> SolidWorksReplayPlan:
    """Build and validate the native replay plan for one model file."""
    model_data = materialize_stable_feature_ids(load_json(model_path))
    part, document = build_editable_model_document(model_data)
    return build_solidworks_replay_plan(
        document,
        expected_geometry=geometry_metrics(part),
    )


def materialize_stable_feature_ids(model_data: dict) -> dict:
    """Return a copy with deterministic IDs on every operation.

    CadQuery can execute leaf operations without IDs, but a native feature tree
    needs a persistent name before SOLIDWORKS opens.  The feature graph already
    uses ``<operation-type>_<build-number>`` for anonymous operations, so the
    exporter writes that same deterministic identity into its private copy.
    """
    normalized = deepcopy(model_data)
    used_ids = {
        str(operation["id"])
        for operation in normalized.get("operations", [])
        if operation.get("id")
    }
    for operation_number, operation in enumerate(
        normalized.get("operations", []),
        start=1,
    ):
        if not operation.get("id"):
            operation_type = operation.get("type", "operation")
            base_id = f"{operation_type}_{operation_number}"
            candidate = base_id
            suffix = 2
            while candidate in used_ids:
                candidate = f"{base_id}_{suffix}"
                suffix += 1
            operation["id"] = candidate
            used_ids.add(candidate)
    return normalized


def parse_args() -> argparse.Namespace:
    """Parse native SOLIDWORKS export arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Replay a supported Prompt2ParametricCAD feature history into "
            "a native SOLIDWORKS SLDPRT file."
        )
    )
    parser.add_argument(
        "model_path",
        type=Path,
        help="Path to validated Prompt2ParametricCAD operation JSON.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Native .SLDPRT output path (required unless --plan-only is used).",
    )
    parser.add_argument(
        "--plan-output",
        type=Path,
        help="Optional path for the validated SOLIDWORKS replay-plan JSON.",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Validate and print/write the replay plan without opening SOLIDWORKS.",
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Show SOLIDWORKS while the native feature history is replayed.",
    )
    parser.add_argument(
        "--template",
        type=Path,
        help="Optional SOLIDWORKS part-template path; defaults to the user setting.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the native SOLIDWORKS export command."""
    args = parse_args()
    if not args.plan_only and args.output is None:
        raise SystemExit("ERROR: --output is required unless --plan-only is used")

    try:
        plan = model_path_to_replay_plan(args.model_path)
        if args.plan_output is not None:
            save_plan(plan, args.plan_output)
            print(f"SAVED replay plan: {args.plan_output}")

        if args.plan_only:
            if args.plan_output is None:
                print(json.dumps(plan.to_dict(), indent=2))
            return

        output_path = export_solidworks_part(
            plan,
            args.output,
            visible=args.visible,
            template_path=args.template,
        )
    except (SolidWorksReplayError, SolidWorksExecutionError) as error:
        raise SystemExit(f"ERROR: {error}") from error

    print(f"SAVED native SOLIDWORKS part: {output_path}")


if __name__ == "__main__":
    main()
