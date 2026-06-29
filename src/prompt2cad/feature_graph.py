"""Feature graph for tracking CAD build history and references.

The graph is the project-level structure that moves us toward editable CAD
features.  It records the ordered operations, parent/child relationships, and
the geometric references created by each feature.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

from prompt2cad.feature_registry import FeatureRegistry
from prompt2cad.sketch_model import SketchDefinition
from prompt2cad.sketch_model import operation_to_sketch


@dataclass
class FeatureNode:
    """One editable feature in the model history."""

    id: str
    operation_type: str
    operation_number: int
    operation: dict
    target: str | None = None
    parent_feature_id: str | None = None
    sketch: SketchDefinition | None = None
    created_references: list[str] = field(default_factory=list)


class FeatureGraph:
    """Track model features, relationships, and geometric references."""

    def __init__(self) -> None:
        self.registry = FeatureRegistry()
        self.features: dict[str, FeatureNode] = {}
        self.build_order: list[str] = []
        self.children_by_feature_id: dict[str, list[str]] = {}

    def add_feature(
        self,
        operation: dict,
        operation_number: int,
    ) -> FeatureNode:
        """Add an operation as a feature node in build order."""
        feature_id = self.get_operation_feature_id(
            operation,
            operation_number,
        )
        if feature_id in self.features:
            raise ValueError(
                f"Operation {operation_number}: duplicate feature id "
                f"'{feature_id}'"
            )

        target = operation.get("target")
        parent_feature_id = self.get_target_feature_id(target)
        sketch = operation_to_sketch(operation) if "profile" in operation else None
        feature_node = FeatureNode(
            id=feature_id,
            operation_type=operation["type"],
            operation_number=operation_number,
            operation=deepcopy(operation),
            target=target,
            parent_feature_id=parent_feature_id,
            sketch=sketch,
        )

        self.features[feature_id] = feature_node
        self.build_order.append(feature_id)

        if parent_feature_id is not None:
            self.children_by_feature_id.setdefault(
                parent_feature_id,
                [],
            ).append(feature_id)

        return feature_node

    def refresh_created_references(self, feature_id: str) -> None:
        """Update a feature node with references created by that feature."""
        feature_node = self.features[feature_id]
        feature_node.created_references = (
            self.registry.reference_names_for_feature(feature_id)
        )

    def get_feature(self, feature_id: str) -> FeatureNode | None:
        """Return a feature node by id, if it exists."""
        return self.features.get(feature_id)

    def children_of(self, feature_id: str) -> list[FeatureNode]:
        """Return child features that target a given feature."""
        return [
            self.features[child_id]
            for child_id in self.children_by_feature_id.get(feature_id, [])
        ]

    @staticmethod
    def get_operation_feature_id(
        operation: dict,
        operation_number: int,
    ) -> str:
        """Return the explicit or generated id for an operation."""
        if operation.get("id"):
            return operation["id"]

        operation_type = operation.get("type", "operation")
        return f"{operation_type}_{operation_number}"

    @staticmethod
    def get_target_feature_id(target: str | None) -> str | None:
        """Return the feature id from a target like 'base.top'."""
        if not target or "." not in target:
            return None

        return target.split(".", 1)[0]
