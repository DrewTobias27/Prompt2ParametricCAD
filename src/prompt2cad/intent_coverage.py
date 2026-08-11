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

    failures.extend(intent_structure_failures(design_intent))

    return failures


def intent_structure_failures(design_intent: dict[str, Any]) -> list[str]:
    """Return semantic inconsistencies that schema validation cannot detect."""
    features = design_intent.get("features", [])
    base = design_intent.get("base", {})
    failures = []

    for feature in features:
        if (
            feature.get("role") == "rim"
            and feature.get("operation") == "extrusion"
        ):
            rim_id = feature.get("id")
            rim_distance = feature.get("distance")
            inner_cuts = [
                candidate
                for candidate in features
                if candidate.get("operation") == "cut"
                and candidate.get("target", "").startswith(f"{rim_id}.")
                and candidate.get("placement", {}).get("type") == "centered"
            ]
            for inner_cut in inner_cuts:
                cut_depth = inner_cut.get("depth")
                if (
                    isinstance(rim_distance, (int, float))
                    and isinstance(cut_depth, (int, float))
                    and abs(float(rim_distance) - float(cut_depth)) > 1e-6
                ):
                    failures.append(
                        f"Rim '{rim_id}' is {rim_distance} mm tall, but its "
                        f"center opening cut is only {cut_depth} mm deep. "
                        "Use equal values so the rim remains hollow."
                    )

            wall_features = [
                candidate
                for candidate in features
                if candidate.get("role") == "wall"
                and candidate.get("operation") == "extrusion"
            ]
            target_owner = str(feature.get("target", "")).split(".", 1)[0]
            if wall_features and target_owner in {"base", base.get("id")}:
                failures.append(
                    f"Rim '{rim_id}' starts from the base while separate walls "
                    "already define the tray height. Target a wall top face and "
                    "extrude only the requested rim height."
                )

        if (
            feature.get("role") == "tab"
            and feature.get("operation") == "extrusion"
            and str(feature.get("target", "")).endswith(".top")
            and feature.get("placement", {}).get("type") == "offset_from_edge"
            and isinstance(
                feature.get("placement", {}).get("offset"),
                (int, float),
            )
            and float(feature["placement"]["offset"]) < 0
            and isinstance(feature.get("distance"), (int, float))
            and isinstance(base.get("thickness"), (int, float))
            and abs(float(feature["distance"]) - float(base["thickness"])) <= 1e-6
        ):
            failures.append(
                f"Tab '{feature.get('id')}' is positioned outside a top face "
                "but extrudes another full base thickness upward. For a "
                "coplanar side extension, target the corresponding side face "
                "and use distance as the outward extension."
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

    covered.update(composite_geometry_concepts(design_intent))
    return covered


def composite_geometry_concepts(design_intent: dict[str, Any]) -> set[str]:
    """Return concepts created by combinations rather than one named feature."""
    base = design_intent.get("base", {})
    if base.get("profile") != "circle":
        return set()

    for feature in design_intent.get("features", []):
        placement = feature.get("placement", {})
        if (
            feature.get("operation") == "cut"
            and feature.get("shape") == "circle"
            and feature.get("depth") == "through"
            and placement.get("type") == "centered"
            and feature.get("target", "").endswith(".top")
        ):
            # An annular ring/rim is the result of a centered through-hole in
            # a circular plate; it need not be modeled as a separate feature.
            return {"ring", "rim"}

    return set()


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
    if profile in {"rectangle", "circle", "polygon", "d_shape", "capsule", "cylinder"}:
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
