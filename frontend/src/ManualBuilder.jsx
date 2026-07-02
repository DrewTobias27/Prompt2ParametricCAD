import { useEffect, useMemo } from "react";
import { createFeature, defaultBase } from "./modelBuilders.js";
import { MANUAL_PRESETS } from "./manualPresets.js";
import * as preview from "./previewEngine.js";
import { featureWarningsByNumber } from "./reviewHelpers.js";
import { DIAMETER_SYMBOL, MULTIPLY_SYMBOL } from "./symbols.js";

const SHAPE_OPTIONS = [
  ["rectangle", "Rectangle"],
  ["circle", "Circle"],
  ["polygon", "Polygon"],
  ["polyline", "Polyline"],
];

const TARGET_OPTIONS = [
  ["base.top", "Base top"],
  ["base.bottom", "Base bottom"],
  ["base.front", "Base front"],
  ["base.back", "Base back"],
  ["base.left", "Base left"],
  ["base.right", "Base right"],
];

export function ManualBuilder({
  base,
  setBase,
  features,
  setFeatures,
  modelData,
  manualPrompt,
  usesApiAssistance,
  onSubmit,
  isLoading,
}) {
  const featureReviewMap = useMemo(
    () => featureWarningsByNumber(preview.buildPreviewModel({ base, features }).warnings),
    [base, features],
  );

  useEffect(() => {
    setFeatures((currentFeatures) => currentFeatures.map((feature, index) => {
      const targetOptions = targetOptionsForFeature(currentFeatures, index);
      if (targetOptions.some(([value]) => value === feature.target)) {
        return feature;
      }
      return { ...feature, target: targetOptions[0][0] };
    }));
  }, [features.length, setFeatures]);

  function updateBase(field, value) {
    setBase((current) => ({ ...current, [field]: value }));
  }

  function updateFeature(index, field, value) {
    setFeatures((current) => current.map((feature, featureIndex) => (
      featureIndex === index ? { ...feature, [field]: value } : feature
    )));
  }

  function removeFeature(indexToRemove) {
    setFeatures((current) => current.filter((_, featureIndex) => featureIndex !== indexToRemove));
  }

  function duplicateFeature(indexToDuplicate) {
    setFeatures((current) => {
      const duplicate = cloneFeature(current[indexToDuplicate], current.length + 1);
      return [
        ...current.slice(0, indexToDuplicate + 1),
        duplicate,
        ...current.slice(indexToDuplicate + 1),
      ];
    });
  }

  function moveFeature(indexToMove, direction) {
    setFeatures((current) => {
      const nextIndex = indexToMove + direction;
      if (nextIndex < 0 || nextIndex >= current.length) {
        return current;
      }

      const reordered = [...current];
      const [feature] = reordered.splice(indexToMove, 1);
      reordered.splice(nextIndex, 0, feature);
      return reordered;
    });
  }

  function applyPreset(preset) {
    setBase({
      ...defaultBase,
      ...preset.base,
      reasonable: false,
      polylineDescription: "",
    });
    setFeatures(preset.features.map((featureData, featureIndex) => ({
      ...createFeature(featureIndex + 1),
      ...featureData,
      localId: crypto.randomUUID(),
      reasonable: false,
      polylineDescription: "",
    })));
  }

  return (
    <form className="panel" onSubmit={onSubmit}>
      <div>
        <h2>Manual builder</h2>
        <p>
          Build the part by choosing a base shape and adding feature cards. Exact
          dimensions build directly; reasonable dimensions and polyline descriptions
          ask the API to fill in the CAD JSON.
        </p>
      </div>

      <section className="form-section compact-section">
        <div>
          <h3>Start from an example</h3>
          <p className="muted">Optional: load a simple engineering-style part, then edit the dimensions and features.</p>
        </div>
        <div className="preset-grid">
          {MANUAL_PRESETS.map((preset) => (
            <button
              key={preset.id}
              className="preset-button"
              type="button"
              onClick={() => applyPreset(preset)}
            >
              <strong>{preset.name}</strong>
              <span>{preset.description}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="form-section">
        <h3>Main frame</h3>
        <div className="field-grid compact">
          <SelectField
            label="Shape"
            value={base.profile}
            onChange={(value) => updateBase("profile", value)}
            options={SHAPE_OPTIONS}
          />
          <CheckboxField
            label="Use reasonable dimensions"
            checked={base.reasonable}
            onChange={(value) => updateBase("reasonable", value)}
          />
        </div>

        {base.profile === "polyline" && (
          <label>
            Polyline description
            <textarea
              rows={3}
              value={base.polylineDescription}
              onChange={(event) => updateBase("polylineDescription", event.target.value)}
              placeholder="Example: L-shaped plate with a long lower arm and shorter upper arm"
            />
          </label>
        )}

        {!base.reasonable && base.profile !== "polyline" && (
          <div className="field-grid">
            <NumberField label="Thickness" value={base.thickness} onChange={(value) => updateBase("thickness", value)} />
            {base.profile === "rectangle" ? (
              <>
                <NumberField label="Width" value={base.width} onChange={(value) => updateBase("width", value)} />
                <NumberField label="Height" value={base.height} onChange={(value) => updateBase("height", value)} />
              </>
            ) : (
              <>
                <NumberField label="Diameter" value={base.diameter} onChange={(value) => updateBase("diameter", value)} />
                {base.profile === "polygon" && (
                  <NumberField label="Sides" value={base.sides} onChange={(value) => updateBase("sides", value)} />
                )}
              </>
            )}
          </div>
        )}
      </section>

      <section className="form-section">
        <div className="section-heading">
          <div>
            <h3>Features</h3>
            <p>Add cuts or extrusions after the base shape.</p>
          </div>
        </div>

        {features.length === 0 && (
          <p className="muted">No features yet. Add an extrusion or cut to the base.</p>
        )}

        {features.map((feature, index) => (
          <FeatureEditor
            key={feature.localId}
            feature={feature}
            index={index}
            allFeatures={features}
            onChange={updateFeature}
            onRemove={() => removeFeature(index)}
            onDuplicate={() => duplicateFeature(index)}
            onMoveUp={() => moveFeature(index, -1)}
            onMoveDown={() => moveFeature(index, 1)}
            canMoveUp={index > 0}
            canMoveDown={index < features.length - 1}
            warnings={featureReviewMap.get(index + 1) ?? []}
          />
        ))}

        <button
          className="secondary"
          type="button"
          onClick={() => setFeatures([...features, createFeature(features.length + 1)])}
        >
          Add feature
        </button>
      </section>

      <section className="form-section">
        <h3>{usesApiAssistance ? "API-assisted manual prompt" : "Generated CAD JSON"}</h3>
        <pre className="model-preview">
          {usesApiAssistance
            ? manualPrompt
            : JSON.stringify(modelData, null, 2)}
        </pre>
      </section>

      <button type="submit" disabled={isLoading}>
        {isLoading ? "Building..." : usesApiAssistance ? "Generate assisted model" : "Build manual model"}
      </button>
    </form>
  );
}

function FeatureEditor({
  feature,
  index,
  allFeatures,
  onChange,
  onRemove,
  onDuplicate,
  onMoveUp,
  onMoveDown,
  canMoveUp,
  canMoveDown,
  warnings,
}) {
  const targetOptions = targetOptionsForFeature(allFeatures, index);
  const isCut = feature.operation === "cut";
  const needsDistance = !isCut || feature.depthMode === "blind";
  const showExactDimensions = !feature.reasonable && feature.profile !== "polyline";

  return (
    <article className="feature-card">
      <div className="section-heading">
        <div>
          <h4>Feature {index + 1}</h4>
          <p className="feature-summary">{featureSummaryText(feature)}</p>
          {warnings.length > 0 && (
            <div className="feature-badges">
              {warnings.slice(0, 2).map((warning) => (
                <span className={`feature-badge ${warning.severity}`} key={`${warning.title}-${warning.message}`}>
                  {warning.severity}: {warning.title.replace(`Feature ${index + 1} `, "")}
                </span>
              ))}
              {warnings.length > 2 && (
                <span className="feature-badge info">+{warnings.length - 2} more</span>
              )}
            </div>
          )}
        </div>
        <div className="feature-actions" aria-label={`Feature ${index + 1} actions`}>
          <button type="button" className="quiet-button" onClick={onMoveUp} disabled={!canMoveUp}>
            Up
          </button>
          <button type="button" className="quiet-button" onClick={onMoveDown} disabled={!canMoveDown}>
            Down
          </button>
          <button type="button" className="quiet-button" onClick={onDuplicate}>
            Duplicate
          </button>
          <button type="button" className="quiet-button danger" onClick={onRemove}>
            Remove
          </button>
        </div>
      </div>

      <div className="field-grid">
        <SelectField
          label="Operation"
          value={feature.operation}
          onChange={(value) => onChange(index, "operation", value)}
          options={[
            ["add_extrude", "Extrusion"],
            ["cut", "Cut"],
          ]}
        />
        <SelectField
          label="Target face"
          value={feature.target}
          onChange={(value) => onChange(index, "target", value)}
          options={targetOptions}
        />
        <SelectField
          label="Shape"
          value={feature.profile}
          onChange={(value) => onChange(index, "profile", value)}
          options={SHAPE_OPTIONS}
        />
        <SelectField
          label="Pattern"
          value={feature.pattern}
          onChange={(value) => onChange(index, "pattern", value)}
          options={[
            ["single", "Single"],
            ["circular", "Circular pattern"],
          ]}
        />
      </div>

      {feature.pattern === "circular" ? (
        <div className="field-grid compact">
          <NumberField
            label="Circular copies"
            value={feature.copies}
            onChange={(value) => onChange(index, "copies", value)}
          />
        </div>
      ) : (
        <div className="inline-checks">
          <CheckboxField
            label="Mirror across X axis"
            checked={feature.mirrorX}
            onChange={(value) => onChange(index, "mirrorX", value)}
          />
          <CheckboxField
            label="Mirror across Y axis"
            checked={feature.mirrorY}
            onChange={(value) => onChange(index, "mirrorY", value)}
          />
        </div>
      )}

      <div className="inline-checks">
        <CheckboxField
          label="Use reasonable dimensions"
          checked={feature.reasonable}
          onChange={(value) => onChange(index, "reasonable", value)}
        />
      </div>

      {feature.profile === "polyline" && (
        <label>
          Polyline description
          <textarea
            rows={3}
            value={feature.polylineDescription}
            onChange={(event) => onChange(index, "polylineDescription", event.target.value)}
            placeholder="Example: rounded triangular tab or narrow slot with angled sides"
          />
        </label>
      )}

      {showExactDimensions && (
        <div className="field-grid">
          {feature.profile === "rectangle" ? (
            <>
              <NumberField label="Width" value={feature.width} onChange={(value) => onChange(index, "width", value)} />
              <NumberField label="Height" value={feature.height} onChange={(value) => onChange(index, "height", value)} />
            </>
          ) : (
            <>
              <NumberField label="Diameter" value={feature.diameter} onChange={(value) => onChange(index, "diameter", value)} />
              {feature.profile === "polygon" && (
                <NumberField label="Sides" value={feature.sides} onChange={(value) => onChange(index, "sides", value)} />
              )}
            </>
          )}
        </div>
      )}

      <div className="field-grid">
        <NumberField label="Position X" value={feature.x} onChange={(value) => onChange(index, "x", value)} />
        <NumberField label="Position Y" value={feature.y} onChange={(value) => onChange(index, "y", value)} />
        {isCut && (
          <SelectField
            label="Cut depth type"
            value={feature.depthMode}
            onChange={(value) => onChange(index, "depthMode", value)}
            options={[
              ["through", "Through cut"],
              ["blind", "Blind depth"],
            ]}
          />
        )}
        {needsDistance && (
          <NumberField
            label={isCut ? "Cut depth" : "Extrusion distance"}
            value={feature.amount}
            onChange={(value) => onChange(index, "amount", value)}
          />
        )}
      </div>
    </article>
  );
}

function NumberField({ label, value, onChange }) {
  return (
    <label>
      {label}
      <input
        type="number"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function SelectField({ label, value, onChange, options }) {
  return (
    <label>
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map(([optionValue, optionLabel]) => (
          <option key={optionValue} value={optionValue}>{optionLabel}</option>
        ))}
      </select>
    </label>
  );
}

function CheckboxField({ label, checked, onChange }) {
  return (
    <label className="checkbox-field">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      {label}
    </label>
  );
}

function cloneFeature(feature, featureNumber) {
  return {
    ...feature,
    localId: crypto.randomUUID(),
    requestedName: `feature_${featureNumber}`,
    x: Number(feature.x) + 8,
  };
}

function featureSummaryText(feature) {
  const operation = feature.operation === "cut" ? "Cut" : "Extrusion";
  const shape = feature.profile === "circle"
    ? `${DIAMETER_SYMBOL}${preview.formatDimension(feature.diameter)} circle`
    : feature.profile === "rectangle"
      ? `${preview.formatDimension(feature.width)} ${MULTIPLY_SYMBOL} ${preview.formatDimension(feature.height)} rectangle`
      : feature.profile === "polygon"
        ? `${feature.sides}-sided polygon`
        : "custom polyline";
  const pattern = feature.pattern === "circular"
    ? `${feature.copies} circular copies`
    : [feature.mirrorX && "mirror X", feature.mirrorY && "mirror Y"].filter(Boolean).join(", ");
  const depth = feature.operation === "cut"
    ? feature.depthMode === "through" ? "through" : `${preview.formatDimension(feature.amount)} deep`
    : `${preview.formatDimension(feature.amount)} tall`;

  return [
    `${operation}: ${shape}`,
    `on ${humanizeTarget(feature.target)}`,
    depth,
    pattern ? `pattern: ${pattern}` : "",
  ].filter(Boolean).join(" · ");
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

function targetOptionsForFeature(features, featureIndex) {
  const options = [...TARGET_OPTIONS];

  for (let priorIndex = 0; priorIndex < featureIndex; priorIndex += 1) {
    const priorFeature = features[priorIndex];
    if (priorFeature.operation !== "add_extrude") {
      continue;
    }

    const featureNumber = priorIndex + 1;
    const faces = [
      ["top", "top"],
      ["bottom", "bottom"],
    ];

    if (priorFeature.profile === "rectangle") {
      faces.push(
        ["front", "front"],
        ["back", "back"],
        ["left", "left"],
        ["right", "right"],
      );
    }

    for (const [faceValue, faceLabel] of faces) {
      options.push([
        `feature_${featureNumber}.${faceValue}`,
        `Feature ${featureNumber} ${faceLabel}`,
      ]);
    }
  }

  return options;
}
