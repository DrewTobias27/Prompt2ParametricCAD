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


def test_intent_coverage_recognizes_ring_from_circle_and_center_hole():
    design_intent = {
        "required_concepts": ["base_body", "rim"],
        "base": {
            "id": "base",
            "role": "base_body",
            "profile": "circle",
            "diameter": 100,
            "thickness": 8,
        },
        "features": [
            {
                "id": "center_hole",
                "role": "hole",
                "operation": "cut",
                "target": "base.top",
                "shape": "circle",
                "diameter": 60,
                "depth": "through",
                "placement": {"type": "centered"},
            }
        ],
        "edge_treatments": [],
    }

    assert intent_coverage_failures(design_intent) == []
    assert {"ring", "rim"}.issubset(covered_intent_concepts(design_intent))


def test_intent_coverage_rejects_rim_opening_depth_mismatch():
    design_intent = {
        "required_concepts": ["rim"],
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 120,
            "height": 80,
            "thickness": 4,
        },
        "features": [
            {
                "id": "left_wall",
                "role": "wall",
                "operation": "extrusion",
                "target": "base.top",
                "shape": "rectangle",
                "width": 4,
                "height": 80,
                "distance": 20,
                "placement": {
                    "type": "offset_from_edge",
                    "edge": "left",
                    "offset": 2,
                    "along": 0,
                },
            },
            {
                "id": "top_rim",
                "role": "rim",
                "operation": "extrusion",
                "target": "base.top",
                "shape": "rectangle",
                "width": 120,
                "height": 80,
                "distance": 23,
                "placement": {"type": "centered"},
            },
            {
                "id": "rim_opening",
                "role": "cutout",
                "operation": "cut",
                "target": "top_rim.top",
                "shape": "rectangle",
                "width": 112,
                "height": 72,
                "depth": 3,
                "placement": {"type": "centered"},
            },
        ],
        "edge_treatments": [],
    }

    failures = intent_coverage_failures(design_intent)

    assert any("only 3 mm deep" in failure for failure in failures)
    assert any("starts from the base" in failure for failure in failures)


def test_intent_coverage_accepts_hollow_rim_from_wall_top():
    design_intent = {
        "required_concepts": ["rim"],
        "base": {
            "id": "base",
            "profile": "rectangle",
            "width": 120,
            "height": 80,
            "thickness": 4,
        },
        "features": [
            {
                "id": "left_wall",
                "role": "wall",
                "operation": "extrusion",
                "target": "base.top",
                "shape": "rectangle",
                "width": 4,
                "height": 80,
                "distance": 20,
                "placement": {
                    "type": "offset_from_edge",
                    "edge": "left",
                    "offset": 2,
                    "along": 0,
                },
            },
            {
                "id": "top_rim",
                "role": "rim",
                "operation": "extrusion",
                "target": "left_wall.top",
                "shape": "rectangle",
                "width": 120,
                "height": 80,
                "distance": 3,
                "placement": {"type": "centered"},
            },
            {
                "id": "rim_opening",
                "role": "cutout",
                "operation": "cut",
                "target": "top_rim.top",
                "shape": "rectangle",
                "width": 112,
                "height": 72,
                "depth": 3,
                "placement": {"type": "centered"},
            },
        ],
        "edge_treatments": [],
    }

    assert intent_coverage_failures(design_intent) == []


def test_intent_coverage_rejects_raised_top_tab_for_coplanar_extension():
    design_intent = {
        "required_concepts": ["tab"],
        "base": {
            "id": "base",
            "profile": "d_shape",
            "width": 100,
            "height": 70,
            "thickness": 8,
        },
        "features": [
            {
                "id": "left_tab",
                "role": "tab",
                "operation": "extrusion",
                "target": "base.top",
                "shape": "rectangle",
                "width": 10,
                "height": 18,
                "distance": 8,
                "placement": {
                    "type": "offset_from_edge",
                    "edge": "left",
                    "offset": -5,
                    "along": 0,
                },
            }
        ],
        "edge_treatments": [],
    }

    failures = intent_coverage_failures(design_intent)

    assert any("coplanar side extension" in failure for failure in failures)
