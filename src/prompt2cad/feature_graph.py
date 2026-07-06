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

    def to_debug_dict(
        self,
        children: list[str],
        canonical_target: str | None,
    ) -> dict:
        """Return a JSON-friendly feature-tree node."""
        sketch = None
        if self.sketch is not None:
            sketch = self.sketch.to_debug_dict()

        return {
            "id": self.id,
            "type": self.operation_type,
            "operation_number": self.operation_number,
            "target": self.target,
            "canonical_target": canonical_target,
            "parent_feature_id": self.parent_feature_id,
            "children": children,
            "created_references": self.created_references,
            "sketch": sketch,
            "operation": self.operation,
        }


@dataclass(frozen=True)
class GraphValidationWarning:
    """A non-blocking issue found while building the feature graph."""

    operation_number: int
    message: str

    def to_debug_dict(self) -> dict:
        """Return a JSON-friendly warning."""
        return {
            "operation_number": self.operation_number,
            "message": self.message,
        }


class FeatureGraph:
    """Track model features, relationships, and geometric references."""

    def __init__(self) -> None:
        self.registry = FeatureRegistry()
        self.features: dict[str, FeatureNode] = {}
        self.build_order: list[str] = []
        self.children_by_feature_id: dict[str, list[str]] = {}
        self.validation_warnings: list[GraphValidationWarning] = []

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
        self.validate_target(target, operation_number)
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
        self.validate_created_references(feature_node)

    def get_feature(self, feature_id: str) -> FeatureNode | None:
        """Return a feature node by id, if it exists."""
        return self.features.get(feature_id)

    def children_of(self, feature_id: str) -> list[FeatureNode]:
        """Return child features that target a given feature."""
        return [
            self.features[child_id]
            for child_id in self.children_by_feature_id.get(feature_id, [])
        ]

    def validate_target(
        self,
        target: str | None,
        operation_number: int,
    ) -> None:
        """Validate a new feature target against the existing graph."""
        if target is None:
            return

        if "." not in target:
            raise ValueError(
                f"Operation {operation_number}: target '{target}' must use "
                "the format 'feature.reference', such as 'base.top'"
            )

        parent_feature_id = self.get_target_feature_id(target)
        if parent_feature_id not in self.features:
            raise ValueError(
                f"Operation {operation_number}: target parent feature "
                f"'{parent_feature_id}' has not been built"
            )

        if (
            not self.registry.has_reference(target)
            and not self.registry.has_reference_group(target)
        ):
            self.validation_warnings.append(
                GraphValidationWarning(
                    operation_number=operation_number,
                    message=(
                        f"Target '{target}' is not a registered feature "
                        "reference; builder will fall back to CadQuery tags "
                        "or virtual target logic"
                    ),
                )
            )

    def validate_created_references(self, feature_node: FeatureNode) -> None:
        """Warn when a feature cannot create graph references yet."""
        if not self.should_create_planar_references(feature_node):
            return

        if feature_node.created_references:
            return

        self.validation_warnings.append(
            GraphValidationWarning(
                operation_number=feature_node.operation_number,
                message=(
                    f"Feature '{feature_node.id}' did not create graph "
                    "references. This is usually because the operation "
                    "created multiple instances or uses unsupported "
                    "reference extraction."
                ),
            )
        )

    @staticmethod
    def should_create_planar_references(feature_node: FeatureNode) -> bool:
        """Return whether this feature is expected to create planar refs."""
        if feature_node.operation_type not in {"extrude", "add_extrude"}:
            return False

        if feature_node.operation.get("profile") != "rectangle":
            return False

        return bool(feature_node.operation.get("id"))

    def to_debug_tree(self) -> dict:
        """Return a JSON-friendly feature tree for inspection/export."""
        return {
            "build_order": self.build_order,
            "features": [
                self.features[feature_id].to_debug_dict(
                    children=self.children_by_feature_id.get(feature_id, []),
                    canonical_target=self.registry.resolve_reference_name(
                        self.features[feature_id].target
                    )
                    if self.features[feature_id].target is not None
                    else None,
                )
                for feature_id in self.build_order
            ],
            "validation_warnings": [
                warning.to_debug_dict()
                for warning in self.validation_warnings
            ],
            "registry": self.registry.to_debug_dict(),
        }

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
