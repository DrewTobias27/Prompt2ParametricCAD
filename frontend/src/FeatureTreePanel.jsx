import { DIAMETER_SYMBOL, MULTIPLY_SYMBOL } from "./symbols.js";

export function FeatureTreePanel({ base, features }) {
  return (
    <section className="feature-tree-card">
      <div className="section-heading">
        <div>
          <h2>Feature tree</h2>
          <p>Build order, parent faces, and major dimensions.</p>
        </div>
      </div>

      <ol className="feature-tree">
        <li>
          <div className="feature-tree-node">
            <span className="tree-node-title">Base</span>
            <span className="tree-node-summary">{baseSummary(base)}</span>
          </div>
        </li>
        {features.map((feature, index) => (
          <li key={feature.localId}>
            <div className="feature-tree-node">
              <span className="tree-node-title">Feature {index + 1}</span>
              <span className="tree-node-summary">{featureSummary(feature)}</span>
              <span className="tree-node-meta">
                Parent: {humanizeTarget(feature.target)}
              </span>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function baseSummary(base) {
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
  const operation = feature.operation === "cut" ? "Cut" : "Extrusion";
  const shape = shapeSummary(feature);
  const depth = feature.operation === "cut"
    ? feature.depthMode === "through" ? "through" : `${feature.amount} deep`
    : `${feature.amount} tall`;
  const pattern = patternSummary(feature);

  return [operation, shape, depth, pattern].filter(Boolean).join(" · ");
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

function humanizeTarget(target) {
  const [id, face] = String(target).split(".");
  if (!id || !face) {
    return target;
  }

  if (id === "base") {
    return `base ${face}`;
  }

  return `${id.replace("_", " ")} ${face}`;
}
