"""Tests for semantic required-concept coverage in design intent."""

from prompt2cad.intent_coverage import covered_intent_concepts
from prompt2cad.intent_coverage import intent_coverage_failures


def test_intent_coverage_reports_missing_mounting_plate():
    design_intent = {
        "required_concepts": [
            "cradle",
            "mounting_plate",
            "hole",
            "groove",
        ],
        "base": {
            "id": "base",
            "role": "cradle",
            "profile": "half_cylinder",
            "diameter": 60,
            "length": 100,
        },
        "features": [
            {
                "id": "mounting_holes",
                "role": "hole",
                "operation": "cut",
                "target": "base.bottom",
                "shape": "circle",
                "diameter": 6,
                "depth": "through",
                "placement": {"type": "centered"},
            },
            {
                "id": "cradle_groove",
                "role": "groove",
                "operation": "cut",
                "target": "base.top",
                "shape": "slot",
                "length": 80,
                "width": 6,
                "depth": 2,
                "placement": {"type": "centered"},
            },
        ],
        "edge_treatments": [],
    }

    failures = intent_coverage_failures(design_intent)

    assert len(failures) == 1
    assert "mounting_plate" in failures[0]


def test_intent_coverage_accepts_roles_ids_and_treatments():
    design_intent = {
        "required_concepts": [
            "plate",
            "boss",
            "bolt_hole",
            "chamfer",
        ],
        "base": {
            "id": "base",
            "role": "plate",
            "profile": "rectangle",
            "width": 80,
            "height": 50,
            "thickness": 6,
        },
        "features": [
            {
                "id": "center_boss",
                "role": "boss",
                "operation": "extrusion",
                "target": "base.top",
                "shape": "circle",
                "diameter": 20,
                "distance": 8,
                "placement": {"type": "centered"},
            },
            {
                "id": "bolt_holes",
                "role": "bolt_hole",
                "operation": "cut",
                "target": "base.top",
                "shape": "circle",
                "diameter": 5,
                "depth": "through",
                "placement": {
                    "type": "circular_pattern",
                    "count": 4,
                    "radius": 25,
                },
            },
        ],
        "edge_treatments": [
            {
                "id": "top_chamfer",
                "role": "chamfer",
                "treatment": "chamfer",
                "target_feature": "base",
                "edge_selector": "top_outer_edges",
                "distance": 1,
            }
        ],
    }

    assert intent_coverage_failures(design_intent) == []
    assert {"plate", "boss", "bolt_hole", "chamfer"}.issubset(
        covered_intent_concepts(design_intent)
    )


def test_intent_coverage_accepts_aliases_for_support_plate():
    design_intent = {
        "required_concepts": ["support_plate"],
        "base": {
            "id": "base",
            "role": "cradle",
            "profile": "half_cylinder",
            "diameter": 60,
            "length": 100,
        },
        "features": [
            {
                "id": "mounting_plate",
                "role": "mounting_plate",
                "operation": "extrusion",
                "target": "base.bottom",
                "shape": "rectangle",
                "width": 80,
                "height": 110,
                "distance": 6,
                "placement": {"type": "centered"},
            }
        ],
        "edge_treatments": [],
    }

    assert intent_coverage_failures(design_intent) == []
