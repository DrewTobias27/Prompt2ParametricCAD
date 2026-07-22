import { useEffect, useMemo } from "react";
import { createLocalId } from "./localIds.js";
import { createFeature, defaultBase, isEdgeTreatment } from "./modelBuilders.js";
import { MANUAL_PRESETS } from "./manualPresets.js";
import * as preview from "./previewEngine.js";
import {
  flattenOptionGroups,
  humanizeTarget,
  targetOptionGroupsForFeature,
} from "./referenceMetadata.js";
import { featureWarningsByNumber } from "./reviewHelpers.js";
import { DIAMETER_SYMBOL, MULTIPLY_SYMBOL } from "./symbols.js";

const SHAPE_OPTIONS = [
  ["rectangle", "Rectangle"],
  ["circle", "Circle"],
  ["polygon", "Polygon"],
  ["polyline", "Polyline"],
];

function minimumForNumberField(field) {
  if (field === "x" || field === "y") {
    return null;
  }
  if (field === "copies") {
    return 2;
  }
  if (field === "sides") {
    return 3;
  }
  return 0;
}

function clampNumberFieldValue(field, value) {
  const minimum = minimumForNumberField(field);
  if (minimum === null || value === "") {
    return value;
  }

  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) {
    return value;
  }

  return numericValue < minimum ? String(minimum) : value;
}

export function ManualBuilder({
  base,
  setBase,
  features,
  setFeatures,
  activeFeatureId,
  setActiveFeatureId,
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
    setFeatures((currentFeatures) => {
      let changed = false;
      const validatedFeatures = currentFeatures.map((feature, index) => {
        const targetOptions = flattenOptionGroups(targetOptionGroupsForFeature({
          base,
          features: currentFeatures,
          featureIndex: index,
          feature,
        }));
        if (targetOptions.length === 0 || targetOptions.some(([value]) => value === feature.target)) {
          return feature;
        }
        changed = true;
        return { ...feature, target: targetOptions[0][0] };
      });

      return changed ? validatedFeatures : currentFeatures;
    });
  }, [base, features, setFeatures]);

  function updateBase(field, value) {
    setBase((current) => ({ ...current, [field]: clampNumberFieldValue(field, value) }));
  }

  function updateFeature(index, field, value) {
    setFeatures((current) => current.map((feature, featureIndex) => {
      if (featureIndex !== index) {
        return feature;
      }

      const updatedFeature = { ...feature, [field]: clampNumberFieldValue(field, value) };
      if (field === "operation") {
        const targetOptions = flattenOptionGroups(
          targetOptionGroupsForFeature({
            base,
            features: current,
            featureIndex: index,
            feature: updatedFeature,
          }),
        );
        updatedFeature.target = targetOptions[0][0];
      }

      return updatedFeature;
    }));
  }

  function removeFeature(indexToRemove) {
    if (features[indexToRemove]?.localId === activeFeatureId) {
      setActiveFeatureId(null);
    }
    setFeatures((current) => current.filter((_, featureIndex) => featureIndex !== indexToRemove));
  }

  function duplicateFeature(indexToDuplicate) {
    const duplicate = cloneFeature(features[indexToDuplicate], features.length + 1);
    setFeatures((current) => [
      ...current.slice(0, indexToDuplicate + 1),
      duplicate,
      ...current.slice(indexToDuplicate + 1),
    ]);
    setActiveFeatureId(duplicate.localId);
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
    const presetFeatures = preset.features.map((featureData, featureIndex) => ({
      ...createFeature(featureIndex + 1),
      ...featureData,
      localId: createLocalId(),
      reasonable: false,
      polylineDescription: "",
    }));
    setFeatures(presetFeatures);
    setActiveFeatureId(presetFeatures[0]?.localId ?? null);
  }

  return (
    <form className="panel" onSubmit={onSubmit}>
      <div>
        <h2>Manual builder</h2>
      </div>

      <section className="form-section compact-section">
        <h3>Examples</h3>
        <div className="preset-grid">
          {MANUAL_PRESETS.map((preset) => (
            <button
              key={preset.id}
              className="preset-button"
              type="button"
              onClick={() => applyPreset(preset)}
            >
              <strong>{preset.name}</strong>
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
            <NumberField label="Thickness" field="thickness" value={base.thickness} onChange={(value) => updateBase("thickness", value)} />
            {base.profile === "rectangle" ? (
              <>
                <NumberField label="Width" field="width" value={base.width} onChange={(value) => updateBase("width", value)} />
                <NumberField label="Height" field="height" value={base.height} onChange={(value) => updateBase("height", value)} />
              </>
            ) : (
              <>
                <NumberField label="Diameter" field="diameter" value={base.diameter} onChange={(value) => updateBase("diameter", value)} />
                {base.profile === "polygon" && (
                  <NumberField label="Sides" field="sides" value={base.sides} onChange={(value) => updateBase("sides", value)} />
                )}
              </>
            )}
          </div>
        )}
      </section>

      <section className="form-section">
        <div className="section-heading">
          <h3>Features</h3>
        </div>

        {features.length === 0 && (
          <p className="muted">No features added.</p>
        )}

        {features.map((feature, index) => (
          <FeatureEditor
            key={feature.localId}
            feature={feature}
            index={index}
            base={base}
            allFeatures={features}
            onChange={updateFeature}
            onRemove={() => removeFeature(index)}
            onDuplicate={() => duplicateFeature(index)}
            onMoveUp={() => moveFeature(index, -1)}
            onMoveDown={() => moveFeature(index, 1)}
            canMoveUp={index > 0}
            canMoveDown={index < features.length - 1}
            warnings={featureReviewMap.get(index + 1) ?? []}
            isActive={feature.localId === activeFeatureId}
            onSelect={() => setActiveFeatureId(feature.localId)}
          />
        ))}

        <button
          className="secondary"
          type="button"
          onClick={() => {
            const feature = createFeature(features.length + 1);
            setFeatures([...features, feature]);
            setActiveFeatureId(feature.localId);
          }}
        >
          Add feature
        </button>
      </section>

      <details className="form-section advanced-output">
        <summary>Advanced output</summary>
        <pre className="model-preview">
          {usesApiAssistance
            ? manualPrompt
            : JSON.stringify(modelData, null, 2)}
        </pre>
      </details>

      <button type="submit" disabled={isLoading}>
        {isLoading ? "Building..." : usesApiAssistance ? "Generate assisted model" : "Build manual model"}
      </button>
    </form>
  );
}

function FeatureEditor({
  feature,
  index,
  base,
  allFeatures,
  onChange,
  onRemove,
  onDuplicate,
  onMoveUp,
  onMoveDown,
  canMoveUp,
  canMoveDown,
  warnings,
  isActive,
  onSelect,
}) {
  const targetOptionGroups = targetOptionGroupsForFeature({
    base,
    features: allFeatures,
    featureIndex: index,
    feature,
  });
  const isCut = feature.operation === "cut";
  const edgeTreatment = isEdgeTreatment(feature);
  const needsDistance = !isCut || feature.depthMode === "blind";
  const showExactDimensions = !edgeTreatment && !feature.reasonable && feature.profile !== "polyline";

  return (
    <article
      className={`feature-card ${isActive ? "active-feature-card" : ""}`}
      onClick={onSelect}
      onFocusCapture={onSelect}
    >
      <div className="section-heading">
        <div>
          <div className="feature-title-row">
            <h4>Feature {index + 1}</h4>
            {isActive && <span className="active-feature-pill">Active target</span>}
          </div>
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
          <button
            type="button"
            className="quiet-button"
            onClick={(event) => {
              event.stopPropagation();
              onMoveUp();
            }}
            disabled={!canMoveUp}
          >
            Up
          </button>
          <button
            type="button"
            className="quiet-button"
            onClick={(event) => {
              event.stopPropagation();
              onMoveDown();
            }}
            disabled={!canMoveDown}
          >
            Down
          </button>
          <button
            type="button"
            className="quiet-button"
            onClick={(event) => {
              event.stopPropagation();
              onDuplicate();
            }}
          >
            Duplicate
          </button>
          <button
            type="button"
            className="quiet-button danger"
            onClick={(event) => {
              event.stopPropagation();
              onRemove();
            }}
          >
            Remove
          </button>
        </div>
      </div>

      <div className={`feature-workflow-grid ${edgeTreatment ? "edge-workflow" : ""}`}>
        <SelectField
          label="Operation"
          value={feature.operation}
          onChange={(value) => onChange(index, "operation", value)}
          options={[
            ["add_extrude", "Extrusion"],
            ["cut", "Cut"],
            ["chamfer", "Chamfer"],
            ["fillet", "Fillet"],
          ]}
        />
        <GroupedSelectField
          label={edgeTreatment ? "Target edge group" : "Target face"}
          value={feature.target}
          onChange={(value) => onChange(index, "target", value)}
          groups={targetOptionGroups}
        />
        {!edgeTreatment && (
          <SelectField
            label="Shape"
            value={feature.profile}
            onChange={(value) => onChange(index, "profile", value)}
            options={SHAPE_OPTIONS}
          />
        )}
      </div>

      {!edgeTreatment && (
        <section className="feature-workflow-section">
          <div className="feature-workflow-heading">
            <span>Sketch dimensions</span>
          </div>

          <div className="feature-reasonable-row">
            <CheckboxField
              label="Use reasonable dimensions"
              checked={feature.reasonable}
              onChange={(value) => onChange(index, "reasonable", value)}
            />
          </div>

          {feature.profile === "polyline" && (
            <label className="full-span">
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
            <div className="feature-dimension-grid">
              {feature.profile === "rectangle" ? (
                <>
                  <NumberField label="Width" field="width" value={feature.width} onChange={(value) => onChange(index, "width", value)} />
                  <NumberField label="Height" field="height" value={feature.height} onChange={(value) => onChange(index, "height", value)} />
                </>
              ) : (
                <>
                  <NumberField label="Diameter" field="diameter" value={feature.diameter} onChange={(value) => onChange(index, "diameter", value)} />
                  {feature.profile === "polygon" && (
                    <NumberField label="Sides" field="sides" value={feature.sides} onChange={(value) => onChange(index, "sides", value)} />
                  )}
                </>
              )}
            </div>
          )}

          <div className="feature-dimension-grid">
            <NumberField label="Position X" field="x" value={feature.x} onChange={(value) => onChange(index, "x", value)} />
            <NumberField label="Position Y" field="y" value={feature.y} onChange={(value) => onChange(index, "y", value)} />
          </div>
        </section>
      )}

      <section className="feature-workflow-section">
        <div className="feature-workflow-heading">
          <span>{edgeTreatment ? "Edge treatment size" : "Feature depth"}</span>
        </div>
        <div className="feature-depth-grid">
          {!edgeTreatment && isCut && (
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
              label={
                edgeTreatment
                  ? feature.operation === "chamfer" ? "Chamfer distance" : "Fillet radius"
                  : isCut ? "Cut depth" : "Extrusion distance"
              }
              field="amount"
              value={feature.amount}
              onChange={(value) => onChange(index, "amount", value)}
            />
          )}
        </div>
      </section>

      {!edgeTreatment && (
        <section className="feature-workflow-section">
          <div className="feature-workflow-heading">
            <span>Pattern after feature</span>
          </div>
          <div className="feature-pattern-grid">
            <SelectField
              label="Pattern"
              value={feature.pattern}
              onChange={(value) => onChange(index, "pattern", value)}
              options={[
                ["single", "Single"],
                ["circular", "Circular pattern"],
              ]}
            />
            {feature.pattern === "circular" ? (
              <>
                <NumberField
                  label="Circular copies"
                  field="copies"
                  value={feature.copies}
                  onChange={(value) => onChange(index, "copies", value)}
                />
                <div className="pattern-placeholder" aria-hidden="true" />
              </>
            ) : (
              <>
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
              </>
            )}
          </div>
        </section>
      )}
    </article>
  );
}

function NumberField({ label, field, value, onChange }) {
  const minimum = minimumForNumberField(field);
  return (
    <label>
      {label}
      <input
        type="number"
        min={minimum ?? undefined}
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

function GroupedSelectField({ label, value, onChange, groups, helpText }) {
  return (
    <label>
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {groups.map((group) => (
          <optgroup key={group.label} label={group.label}>
            {group.options.map(([optionValue, optionLabel]) => (
              <option key={optionValue} value={optionValue}>{optionLabel}</option>
            ))}
          </optgroup>
        ))}
      </select>
      {helpText && <span className="field-help">{helpText}</span>}
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
    localId: createLocalId(),
    requestedName: `feature_${featureNumber}`,
    x: Number(feature.x) + 8,
  };
}

function featureSummaryText(feature) {
  if (isEdgeTreatment(feature)) {
    const operation = feature.operation === "chamfer" ? "Chamfer" : "Fillet";
    const dimension = feature.operation === "chamfer"
      ? `${preview.formatDimension(feature.amount)} distance`
      : `${preview.formatDimension(feature.amount)} radius`;
    return [
      `${operation}: ${dimension}`,
      `on ${humanizeTarget(feature.target)}`,
    ].join(" - ");
  }

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
  ].filter(Boolean).join(" - ");
}
