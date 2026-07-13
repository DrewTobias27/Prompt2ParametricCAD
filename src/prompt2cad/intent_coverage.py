"""Check whether generated design intent covers its required concepts."""

from __future__ import annotations

from typing import Any

from prompt2cad.design_intent import remove_null_values


CONCEPT_ALIASES = {
    "mounting_plate": {"mounting_plate", "support_plate", "plate"},
    "support_plate": {"support_plate", "mounting_plate", "plate"},
    "bolt_hole": {"bolt_hole", "hole"},
    "key_slot": {"key_slot", "slot"},
    "o_ring_groove": {"o_ring_groove", "groove"},
}


def intent_coverage_failures(design_intent: dict[str, Any]) -> list[str]:
    """Return missing required semantic concepts in a design-intent object."""
    design_intent = remove_null_values(design_intent)
    required_concepts = design_intent.get("required_concepts", [])
    if not required_concepts:
        return []

    covered_concepts = covered_intent_concepts(design_intent)
    failures = []
    for required_concept in required_concepts:
        acceptable_concepts = CONCEPT_ALIASES.get(
            required_concept,
            {required_concept},
        )
        if not covered_concepts.intersection(acceptable_concepts):
            failures.append(
                f"Required concept '{required_concept}' is not covered by "
                "the base, features, edge treatments, roles, or ids."
            )

    return failures


def covered_intent_concepts(design_intent: dict[str, Any]) -> set[str]:
    """Return semantic concepts covered by base/features/edge treatments."""
    covered = set()
    base = design_intent.get("base", {})
    covered.update(concepts_from_item(base))
    covered.update(base_profile_concepts(base))

    for feature in design_intent.get("features", []):
        covered.update(concepts_from_item(feature))
        covered.update(feature_shape_concepts(feature))

    for edge_treatment in design_intent.get("edge_treatments", []):
        covered.update(concepts_from_item(edge_treatment))
        treatment = edge_treatment.get("treatment")
        if treatment:
            covered.add(treatment)

    return covered


def concepts_from_item(item: dict[str, Any]) -> set[str]:
    """Return role/id-derived concepts for one intent item."""
    concepts = set()
    role = item.get("role")
    if role:
        concepts.add(role)

    item_id = item.get("id", "")
    for concept in known_concept_words():
        if concept in item_id:
            concepts.add(concept)

    return concepts


def base_profile_concepts(base: dict[str, Any]) -> set[str]:
    """Return concepts implied by a base profile."""
    profile = base.get("profile")
    if profile == "half_cylinder":
        return {"cradle", "base_body"}
    if profile in {"rectangle", "circle", "polygon", "capsule", "cylinder"}:
        return {"base_body"}
    return set()


def feature_shape_concepts(feature: dict[str, Any]) -> set[str]:
    """Return conservative concepts implied by feature operation and shape."""
    operation = feature.get("operation")
    shape = feature.get("shape")
    concepts = set()

    if operation == "cut":
        if shape == "circle":
            concepts.add("hole")
        elif shape == "slot":
            concepts.add("slot")
        elif shape in {"rectangle", "rounded_rectangle", "polyline"}:
            concepts.update({"cutout", "pocket"})

    if operation == "extrusion":
        if shape == "circle":
            concepts.update({"boss", "post", "hub"})
        elif shape == "rectangle":
            concepts.update({"pad", "tab", "rib", "wall"})

    if operation == "revolved_extrusion":
        concepts.add("collar")
    if operation == "revolved_cut":
        concepts.add("groove")

    return concepts


def known_concept_words() -> set[str]:
    """Return semantic words worth detecting inside stable ids."""
    return {
        "base_body",
        "plate",
        "mounting_plate",
        "support_plate",
        "cradle",
        "bracket",
        "wall",
        "rib",
        "boss",
        "hub",
        "post",
        "pad",
        "tab",
        "rim",
        "lip",
        "tube",
        "collar",
        "hole",
        "bolt_hole",
        "counterbore",
        "countersink",
        "slot",
        "key_slot",
        "groove",
        "o_ring_groove",
        "pocket",
        "cutout",
        "drain",
        "spoke",
        "chamfer",
        "fillet",
    }
