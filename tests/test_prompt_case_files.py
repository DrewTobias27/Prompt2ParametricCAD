"""Tests for exploratory prompt-case files."""

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPT_CASE_FILES = [
    PROJECT_ROOT / "evals" / "intent_gap_tests.json",
    PROJECT_ROOT / "evals" / "intent_stress_cases.json",
]


def test_exploratory_prompt_case_files_are_well_formed():
    """Keep exploratory API test files readable and runnable."""
    seen_names = set()

    for prompt_case_file in PROMPT_CASE_FILES:
        data = json.loads(prompt_case_file.read_text(encoding="utf-8"))
        cases = data["cases"]

        assert data["description"]
        assert cases

        for prompt_case in cases:
            case_name = prompt_case["name"]
            assert case_name not in seen_names
            seen_names.add(case_name)

            assert prompt_case["prompt"]
            assert prompt_case["focus"]
            assert (
                "expected_concepts" in prompt_case
                or "expected_intent" in prompt_case
            )
