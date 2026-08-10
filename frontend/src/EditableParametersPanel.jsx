import { useEffect, useMemo, useState } from "react";

import {
  collectParameterUpdates,
  createEditableDraft,
  editableParameterGroups,
  parameterInputLimits,
} from "./editableParameters.js";

export function EditableParametersPanel({
  editableModel,
  isLoading,
  onApply,
  onRestore,
  canRestore,
}) {
  const [draft, setDraft] = useState({});
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    setDraft(createEditableDraft(editableModel));
    setShowAdvanced(false);
  }, [editableModel]);

  const coreGroups = useMemo(
    () => editableParameterGroups(editableModel),
    [editableModel],
  );
  const advancedGroups = useMemo(
    () => editableParameterGroups(editableModel, true)
      .map((feature) => ({
        ...feature,
        parameters: feature.parameters.filter((parameter) => (
          !["sketch_dimension", "feature_control", "placement"].includes(
            parameter.role,
          )
        )),
      }))
      .filter((feature) => feature.parameters.length > 0),
    [editableModel],
  );
  const updates = useMemo(
    () => collectParameterUpdates(editableModel, draft),
    [draft, editableModel],
  );
  const hasChanges = Object.keys(updates).length > 0;

  function updateParameter(parameterId, value) {
    setDraft((current) => ({ ...current, [parameterId]: value }));
  }

  function resetDraft() {
    setDraft(createEditableDraft(editableModel));
  }

  function handleSubmit(event) {
    event.preventDefault();
    if (hasChanges && !isLoading) {
      onApply(updates);
    }
  }

  if (!editableModel || coreGroups.length === 0) {
    return null;
  }

  return (
    <section className="editable-parameters-card">
      <div className="editable-parameters-heading">
        <div>
          <h2>Edit dimensions</h2>
          <p>Change named values, then rebuild a checked STEP revision.</p>
        </div>
        <span>Validated rebuild</span>
      </div>

      <form className="editable-parameter-form" onSubmit={handleSubmit}>
        {coreGroups.map((feature) => (
          <ParameterFeatureGroup
            key={feature.id}
            feature={feature}
            draft={draft}
            isLoading={isLoading}
            onChange={updateParameter}
          />
        ))}

        {advancedGroups.length > 0 && (
          <details
            className="advanced-parameter-details"
            open={showAdvanced}
            onToggle={(event) => setShowAdvanced(event.currentTarget.open)}
          >
            <summary>Advanced sketch and axis coordinates</summary>
            <p>
              Use these only when direct coordinate control is needed.
            </p>
            {advancedGroups.map((feature) => (
              <ParameterFeatureGroup
                key={`advanced-${feature.id}`}
                feature={feature}
                draft={draft}
                isLoading={isLoading}
                onChange={updateParameter}
                compact
              />
            ))}
          </details>
        )}

        <div className="editable-parameter-actions">
          <button type="submit" disabled={isLoading || !hasChanges}>
            {isLoading ? "Rebuilding..." : "Apply changes"}
          </button>
          <button
            className="secondary"
            type="button"
            disabled={isLoading || !hasChanges}
            onClick={resetDraft}
          >
            Reset fields
          </button>
          {canRestore && (
            <button
              className="secondary"
              type="button"
              disabled={isLoading}
              onClick={onRestore}
            >
              Restore prior model
            </button>
          )}
        </div>
      </form>
    </section>
  );
}

function ParameterFeatureGroup({
  feature,
  draft,
  isLoading,
  onChange,
  compact = false,
}) {
  return (
    <fieldset className={`editable-feature-group${compact ? " compact" : ""}`}>
      <legend>
        <span>{feature.id}</span>
        <small>{feature.operationType.replaceAll("_", " ")}</small>
      </legend>
      <div className="editable-parameter-grid">
        {feature.parameters.map((parameter) => (
          <ParameterField
            key={parameter.id}
            parameter={parameter}
            value={draft[parameter.id]}
            disabled={isLoading}
            onChange={(value) => onChange(parameter.id, value)}
          />
        ))}
      </div>
    </fieldset>
  );
}

function ParameterField({ parameter, value, disabled, onChange }) {
  if (parameter.value_type === "end_condition") {
    const isThrough = value === "through";
    return (
      <label>
        {parameter.name}
        <span className="editable-end-condition">
          <select
            value={isThrough ? "through" : "blind"}
            disabled={disabled}
            onChange={(event) => onChange(
              event.target.value === "through" ? "through" : 5,
            )}
          >
            <option value="through">Through</option>
            <option value="blind">Blind</option>
          </select>
          {!isThrough && (
            <input
              type="number"
              min="0.001"
              step="any"
              value={value}
              disabled={disabled}
              aria-label={`${parameter.name} in millimeters`}
              onChange={(event) => onChange(Number(event.target.value))}
            />
          )}
        </span>
      </label>
    );
  }

  const limits = parameterInputLimits(parameter);
  return (
    <label>
      <span className="editable-parameter-label">
        {parameter.name}
        {parameter.unit && <small>{parameter.unit}</small>}
      </span>
      <input
        type="number"
        value={value ?? ""}
        min={limits.min}
        step={limits.step}
        disabled={disabled}
        onChange={(event) => onChange(
          parameter.value_type === "count"
            ? Number.parseInt(event.target.value, 10)
            : Number(event.target.value),
        )}
      />
    </label>
  );
}
