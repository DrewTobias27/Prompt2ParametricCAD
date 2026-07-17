import { DIAMETER_SYMBOL, MULTIPLY_SYMBOL } from "./symbols.js";
import { isEdgeTreatment } from "./modelBuilders.js";
import {
  baseReferences,
  featureReferences,
  humanizeTarget,
} from "./referenceMetadata.js";

export function FeatureTreePanel({
  base,
  features,
  onTargetReferenceClick,
  title = "Feature tree",
  description = "",
  hint = "",
}) {
  const tree = buildFeatureTree(features);

  return (
    <section className="feature-tree-card">
      <div className="section-heading">
        <div>
          <h2>{title}</h2>
          {description && <p>{description}</p>}
          {hint && <p className="tree-hint">{hint}</p>}
        </div>
      </div>

      <div className="feature-tree" role="tree" aria-label={`${title} feature tree`}>
        <TreeNode
          title="Base"
          summary={baseSummary(base)}
          references={baseReferences(base)}
          childrenNodes={tree}
          onTargetReferenceClick={onTargetReferenceClick}
          isRoot
        />
      </div>
    </section>
  );
}

function TreeNode({
  title,
  summary,
  meta,
  references = [],
  childrenNodes = [],
  onTargetReferenceClick,
  isRoot = false,
}) {
  return (
    <div className={`feature-tree-item ${isRoot ? "root" : ""}`} role="treeitem">
      <div className="feature-tree-branch">
        <div className="tree-connector" aria-hidden="true" />
        <div className="feature-tree-node">
          <span className="tree-node-title">{title}</span>
          <span className="tree-node-summary">{summary}</span>
          {meta && <span className="tree-node-meta">{meta}</span>}
          {references.length > 0 && (
            <div className="tree-reference-list" aria-label={`${title} available targets`}>
              {references.map((reference) => (
                onTargetReferenceClick ? (
                  <button
                    className={`tree-reference-chip ${reference.kind}`}
                    key={reference.name}
                    type="button"
                    title={targetActionTitle(reference)}
                    onClick={() => onTargetReferenceClick(reference)}
                  >
                    {reference.label}
                  </button>
                ) : (
                  <span className={`tree-reference-chip ${reference.kind} readonly`} key={reference.name}>
                    {reference.label}
                  </span>
                )
              ))}
            </div>
          )}
        </div>
      </div>

      {childrenNodes.length > 0 && (
        <div className="feature-tree-children" role="group">
          {childrenNodes.map((node) => (
            <TreeNode
              key={node.id}
              title={node.title}
              summary={node.summary}
              meta={node.meta}
              references={node.references}
              childrenNodes={node.children}
              onTargetReferenceClick={onTargetReferenceClick}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function baseSummary(base) {
  if (base.summary) {
    return base.summary;
  }

  if (base.reasonable) {
    return `Reasonable ${base.profile} base`;
  }

  if (base.profile === "rectangle") {
    return `Rectangle ${base.width} ${MULTIPLY_SYMBOL} ${base.height} ${MULTIPLY_SYMBOL} ${base.thickness}`;
  }

  if (base.profile === "circle") {
    return `Circle ${DIAMETER_SYMBOL}${base.diameter} ${MULTIPLY_SYMBOL} ${base.thickness}`;
  }

  if (base.profile === "polygon") {
    return `${base.sides}-sided polygon ${DIAMETER_SYMBOL}${base.diameter} ${MULTIPLY_SYMBOL} ${base.thickness}`;
  }

  return `Polyline base: ${base.polylineDescription || "API-defined profile"}`;
}

function featureSummary(feature) {
  if (feature.summary) {
    return feature.summary;
  }

  if (isEdgeTreatment(feature)) {
    const operation = feature.operation === "chamfer" ? "Chamfer" : "Fillet";
    const dimension = feature.operation === "chamfer"
      ? `${feature.amount} distance`
      : `${feature.amount} radius`;
    return `${operation} - ${dimension}`;
  }

  const operation = feature.operation === "cut" ? "Cut" : "Extrusion";
  const shape = shapeSummary(feature);
  const depth = feature.operation === "cut"
    ? feature.depthMode === "through" ? "through" : `${feature.amount} deep`
    : `${feature.amount} tall`;
  const pattern = patternSummary(feature);

  return [operation, shape, depth, pattern].filter(Boolean).join(" - ");
}

function shapeSummary(feature) {
  if (feature.reasonable) {
    return `reasonable ${feature.profile}`;
  }

  if (feature.profile === "rectangle") {
    return `${feature.width} ${MULTIPLY_SYMBOL} ${feature.height} rectangle`;
  }

  if (feature.profile === "circle") {
    return `${DIAMETER_SYMBOL}${feature.diameter} circle`;
  }

  if (feature.profile === "polygon") {
    return `${feature.sides}-sided polygon ${DIAMETER_SYMBOL}${feature.diameter}`;
  }

  return `polyline: ${feature.polylineDescription || "API-defined profile"}`;
}

function patternSummary(feature) {
  if (feature.pattern === "circular") {
    return `${feature.copies} circular copies`;
  }

  return [
    feature.mirrorX ? "mirror X" : "",
    feature.mirrorY ? "mirror Y" : "",
  ].filter(Boolean).join(", ");
}

function buildFeatureTree(features) {
  const nodes = features.map((feature, index) => ({
    id: `feature_${index + 1}`,
    title: `Feature ${index + 1}`,
    summary: featureSummary(feature),
    meta: `Target: ${humanizeTarget(feature.target)}`,
    references: featureReferences(feature, index + 1),
    children: [],
  }));
  const nodesById = new Map(nodes.map((node) => [node.id, node]));
  const rootChildren = [];

  for (const node of nodes) {
    const featureIndex = Number(node.id.replace("feature_", "")) - 1;
    const parentNode = nodesById.get(parentFeatureId(features[featureIndex].target));

    if (parentNode) {
      parentNode.children.push(node);
    } else {
      rootChildren.push(node);
    }
  }

  return rootChildren;
}

function parentFeatureId(target) {
  const [id] = String(target).split(".");
  return id?.startsWith("feature_") ? id : "base";
}

function targetActionTitle(reference) {
  if (reference.kind === "edge") {
    return `Add a chamfer targeting ${reference.name}`;
  }

  return `Add an extrusion targeting ${reference.name}`;
}
