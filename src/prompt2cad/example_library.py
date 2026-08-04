"""Retrieve CAD examples that can guide prompt-to-JSON generation."""

import json
import re
from pathlib import Path
from typing import Any

from prompt2cad.training_data import DEFAULT_INTENT_EXAMPLES_DIR
from prompt2cad.training_data import load_intent_examples
from prompt2cad.design_intent import design_intent_to_openai


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LIBRARY_DIR = REPO_ROOT / "examples" / "library"

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

STOP_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "build",
    "by",
    "cad",
    "create",
    "design",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "make",
    "mm",
    "model",
    "of",
    "on",
    "or",
    "part",
    "the",
    "to",
    "with",
}

MIN_INTENT_EXAMPLE_SCORE = 5


def tokenize(text: str) -> set[str]:
    """Turn text into a small searchable set of meaningful lowercase tokens."""
    return {
        token
        for token in TOKEN_PATTERN.findall(text.lower())
        if token not in STOP_WORDS
    }


def load_example_library(
    library_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Load rich prompt examples from the example library directory."""
    library_dir = library_dir or DEFAULT_LIBRARY_DIR
    if not library_dir.exists():
        return []

    examples = []
    for example_path in sorted(library_dir.glob("*.json")):
        with open(example_path, "r", encoding="utf-8") as file:
            example = json.load(file)
        example["source_file"] = example_path.name
        examples.append(example)

    return examples


def example_search_text(example: dict[str, Any]) -> str:
    """Combine the text fields that should influence example retrieval."""
    tags = " ".join(example.get("tags", []))
    plan = " ".join(example.get("construction_plan", []))
    notes = " ".join(example.get("notes", []))
    return " ".join(
        [
            example.get("name", ""),
            example.get("description", ""),
            tags,
            plan,
            notes,
        ]
    )


def score_example(user_prompt: str, example: dict[str, Any]) -> int:
    """Score how useful one example is for a user prompt."""
    prompt_tokens = tokenize(user_prompt)
    if not prompt_tokens:
        return 0

    tag_tokens = tokenize(" ".join(example.get("tags", [])))
    description_tokens = tokenize(example.get("description", ""))
    all_tokens = tokenize(example_search_text(example))

    tag_matches = prompt_tokens & tag_tokens
    description_matches = prompt_tokens & description_tokens
    broad_matches = prompt_tokens & all_tokens

    return (4 * len(tag_matches)) + (2 * len(description_matches)) + len(
        broad_matches
    )


def select_relevant_examples(
    user_prompt: str,
    max_examples: int = 3,
    library_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Return the most relevant examples for a natural language CAD request."""
    scored_examples = []
    for example in load_example_library(library_dir):
        score = score_example(user_prompt, example)
        if score > 0:
            scored_examples.append((score, example.get("name", ""), example))

    scored_examples.sort(key=lambda item: (-item[0], item[1]))
    return [example for _, _, example in scored_examples[:max_examples]]


def intent_example_search_text(example: dict[str, Any]) -> str:
    """Combine prompt, tags, and intent vocabulary for intent retrieval."""
    return " ".join([
        example.get("name", ""),
        example.get("prompt", ""),
        " ".join(example.get("tags", [])),
        json.dumps(example.get("design_intent", {})),
    ])


def score_intent_example(user_prompt: str, example: dict[str, Any]) -> int:
    """Score a prompt-to-intent example against a new CAD request."""
    prompt_tokens = tokenize(user_prompt)
    if not prompt_tokens:
        return 0

    tag_tokens = tokenize(" ".join(example.get("tags", [])))
    source_prompt_tokens = tokenize(example.get("prompt", ""))
    all_tokens = tokenize(intent_example_search_text(example))
    return (
        4 * len(prompt_tokens & tag_tokens)
        + 2 * len(prompt_tokens & source_prompt_tokens)
        + len(prompt_tokens & all_tokens)
    )


def select_relevant_intent_examples(
    user_prompt: str,
    max_examples: int = 2,
    examples_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Return prompt-to-intent examples suited to the preferred pipeline."""
    examples_dir = examples_dir or DEFAULT_INTENT_EXAMPLES_DIR
    scored_examples = []
    for example in load_intent_examples(examples_dir):
        score = score_intent_example(user_prompt, example)
        if score >= MIN_INTENT_EXAMPLE_SCORE:
            scored_examples.append((score, example.get("name", ""), example))

    scored_examples.sort(key=lambda item: (-item[0], item[1]))
    return [example for _, _, example in scored_examples[:max_examples]]


def compact_example(example: dict[str, Any]) -> dict[str, Any]:
    """Keep only the fields that should be shown to the model."""
    return {
        "name": example["name"],
        "description": example["description"],
        "tags": example.get("tags", []),
        "construction_plan": example.get("construction_plan", []),
        "model_data": example["model_data"],
        "notes": example.get("notes", []),
    }


def format_examples_for_prompt(examples: list[dict[str, Any]]) -> str:
    """Format retrieved examples as compact, readable JSON for the API input."""
    compact_examples = [compact_example(example) for example in examples]
    return json.dumps(compact_examples, indent=2)


def compact_intent_example(example: dict[str, Any]) -> dict[str, Any]:
    """Keep only the prompt and exact target format needed for few-shot use."""
    return {
        "name": example["name"],
        "prompt": example["prompt"],
        "tags": example.get("tags", []),
        "design_intent": design_intent_to_openai(example["design_intent"]),
    }


def format_intent_examples_for_prompt(examples: list[dict[str, Any]]) -> str:
    """Format prompt-to-design-intent pairs for the intent generator."""
    return json.dumps(
        [compact_intent_example(example) for example in examples],
        indent=2,
    )
