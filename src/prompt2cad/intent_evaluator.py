"""Evaluate generated design intent before it is lowered into CAD operations."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from prompt2cad.design_intent import fill_reasonable_missing_dimensions
from prompt2cad.design_intent import intent_to_model_data
from prompt2cad.design_intent import remove_null_values
from prompt2cad.design_intent import validate_design_intent
from prompt2cad.diagnostics import check_model_data


DEFAULT_CASES_DIR = Path("evals/intent_cases")


@dataclass
class IntentEvaluationResult:
    """Result of checking design intent against expected intent concepts."""

    passed: bool
    failures: list[str]


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def values_match(actual_value: object, expected_value: object) -> bool:
    """Return whether an actual intent value matches an expected value."""
    return actual_value == expected_value


def find_matching_feature(
    design_intent: dict[str, Any],
    expected_feature: dict[str, Any],
) -> dict[str, Any] | None:
    """Return the first feature that satisfies an expected feature pattern."""
    for feature in design_intent.get("features", []):
        if feature_matches_expected(feature, expected_feature):
            return feature
    return None


def find_matching_edge_treatment(
    design_intent: dict[str, Any],
    expected_edge_treatment: dict[str, Any],
) -> dict[str, Any] | None:
    """Return the first edge treatment matching an expected pattern."""
    for edge_treatment in design_intent.get("edge_treatments", []):
        if edge_treatment_matches_expected(
            edge_treatment,
            expected_edge_treatment,
        ):
            return edge_treatment
    return None


def feature_matches_expected(
    feature: dict[str, Any],
    expected_feature: dict[str, Any],
) -> bool:
    """Return whether one feature satisfies an expected feature pattern."""
    for key, expected_value in expected_feature.items():
        if key == "placement":
            placement = feature.get("placement", {})
            for placement_key, placement_expected_value in expected_value.items():
                if not values_match(
                    placement.get(placement_key),
                    placement_expected_value,
                ):
                    return False
        elif not values_match(feature.get(key), expected_value):
            return False

    return True


def edge_treatment_matches_expected(
    edge_treatment: dict[str, Any],
    expected_edge_treatment: dict[str, Any],
) -> bool:
    """Return whether one edge treatment satisfies an expected pattern."""
    for key, expected_value in expected_edge_treatment.items():
        if not values_match(edge_treatment.get(key), expected_value):
            return False

    return True


def expected_base_failures(
    design_intent: dict[str, Any],
    expected_base: dict[str, Any],
) -> list[str]:
    """Return failures for base-level intent expectations."""
    failures = []
    base = design_intent.get("base", {})
    for key, expected_value in expected_base.items():
        actual_value = base.get(key)
        if not values_match(actual_value, expected_value):
            failures.append(
                f"Expected base {key} {expected_value}, but found {actual_value}."
            )

    return failures


def expected_feature_failures(
    design_intent: dict[str, Any],
    expected_features: list[dict[str, Any]],
) -> list[str]:
    """Return failures for feature-level intent expectations."""
    failures = []
    for expected_feature in expected_features:
        if find_matching_feature(design_intent, expected_feature) is None:
            failures.append(
                "Missing feature intent matching "
                + json.dumps(expected_feature, sort_keys=True)
            )

    return failures


def expected_edge_treatment_failures(
    design_intent: dict[str, Any],
    expected_edge_treatments: list[dict[str, Any]],
) -> list[str]:
    """Return failures for edge-treatment intent expectations."""
    failures = []
    for expected_edge_treatment in expected_edge_treatments:
        if (
            find_matching_edge_treatment(
                design_intent,
                expected_edge_treatment,
            )
            is None
        ):
            failures.append(
                "Missing edge treatment intent matching "
                + json.dumps(expected_edge_treatment, sort_keys=True)
            )

    return failures


def evaluate_design_intent(
    design_intent: dict[str, Any],
    eval_case: dict[str, Any],
) -> IntentEvaluationResult:
    """Evaluate design intent against one intent eval case."""
    failures = []
    design_intent = remove_null_values(design_intent)
    design_intent = fill_reasonable_missing_dimensions(design_intent)
    try:
        validate_design_intent(design_intent)
    except Exception as error:
        return IntentEvaluationResult(
            passed=False,
            failures=[f"Design intent schema validation failed: {error}"],
        )

    expected = eval_case.get("expected_intent", {})
    failures.extend(expected_base_failures(design_intent, expected.get("base", {})))
    failures.extend(
        expected_feature_failures(
            design_intent,
            expected.get("features", []),
        )
    )
    failures.extend(
        expected_edge_treatment_failures(
            design_intent,
            expected.get("edge_treatments", []),
        )
    )

    if expected.get("lowers_to_buildable_model", False):
        model_data = intent_to_model_data(design_intent)
        diagnosis = check_model_data(model_data)
        if not diagnosis["passed"]:
            failures.append(
                "Expected intent to lower into a buildable model, but got: "
                f"{diagnosis['reason']}"
            )

    return IntentEvaluationResult(passed=not failures, failures=failures)


def run_case(intent_path: Path, case_path: Path) -> tuple[str, list[str]]:
    """Evaluate one saved design-intent JSON file against one eval case."""
    design_intent = load_json(intent_path)
    eval_case = load_json(case_path)
    result = evaluate_design_intent(design_intent, eval_case)
    return eval_case["name"], result.failures


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Evaluate generated design-intent JSON against intent eval cases."
    )
    parser.add_argument("intent_path", type=Path, help="Generated design-intent JSON.")
    parser.add_argument("case_path", type=Path, help="Intent eval case JSON.")
    return parser.parse_args()


def main() -> None:
    """Run one design-intent eval case."""
    args = parse_args()
    case_name, failures = run_case(args.intent_path, args.case_path)
    if failures:
        print(f"FAIL {case_name}")
        for failure in failures:
            print(f"  - {failure}")
        raise SystemExit(1)

    print(f"PASS {case_name}")


if __name__ == "__main__":
    main()
