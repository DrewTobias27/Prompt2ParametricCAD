import { useEffect, useMemo, useState } from "react";
import { buildFromModelData, generateFromPrompt, getDownloadUrl } from "./api.js";
import {
  buildManualModelData,
  buildManualPrompt,
  createFeature,
  defaultBase,
  hasApiAssistedFields,
} from "./modelBuilders.js";
import * as preview from "./previewEngine.js";

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

export default function App() {
  const [mode, setMode] = useState("manual");
  const [prompt, setPrompt] = useState("Create an 80 mm by 50 mm rectangular plate that is 6 mm thick.");
  const [base, setBase] = useState(defaultBase);
  const [features, setFeatures] = useState([]);
  const [status, setStatus] = useState("");
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const usesApiAssistance = hasApiAssistedFields({ base, features });
  const manualModelData = useMemo(
    () => (usesApiAssistance ? null : buildManualModelData({ base, features })),
    [base, features, usesApiAssistance],
  );
  const manualPrompt = useMemo(
    () => buildManualPrompt({ base, features }),
    [base, features],
  );

  async function runRequest(request) {
    setIsLoading(true);
    setStatus("Generating CAD model...");
    setResult(null);

    try {
      const data = await request();
      setResult(data);
      setStatus(data.status === "success" ? "Success" : `Error: ${data.message}`);
    } catch (error) {
      setStatus(`Error: ${error.message}`);
      setResult({ status: "error", message: error.message });
    } finally {
      setIsLoading(false);
    }
  }

  function handlePromptSubmit(event) {
    event.preventDefault();
    runRequest(() => generateFromPrompt(prompt));
  }

  function handleManualSubmit(event) {
    event.preventDefault();
    if (usesApiAssistance) {
      runRequest(() => generateFromPrompt(manualPrompt));
      return;
    }

    runRequest(() => buildFromModelData(manualModelData, `manual ${base.profile} base`));
  }

  const downloadUrl = getDownloadUrl(result?.download_url);

  useEffect(() => {
    setFeatures((currentFeatures) => currentFeatures.map((feature, index) => {
      const targetOptions = targetOptionsForFeature(currentFeatures, index);
      if (targetOptions.some(([value]) => value === feature.target)) {
        return feature;
      }
      return { ...feature, target: targetOptions[0][0] };
    }));
  }, [features.length]);

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Prompt2ParametricCAD</p>
          <h1>Build parametric CAD from prompts or guided features.</h1>
          <p className="hero-copy">
            A cleaner React frontend for the CadQuery/FastAPI backend, with a guided
            manual builder, drawing preview, and live design-review scaffolding.
          </p>
        </div>
        <div className="hero-card">
          <span>Frontend migration</span>
          <strong>React + Vite</strong>
        </div>
      </header>

      <section className="workspace">
        <section className="builder-card">
          <div className="mode-tabs" role="tablist" aria-label="Builder mode">
            <button
              className={mode === "manual" ? "active" : ""}
              type="button"
              onClick={() => setMode("manual")}
            >
              Manual builder
            </button>
            <button
              className={mode === "prompt" ? "active" : ""}
              type="button"
              onClick={() => setMode("prompt")}
            >
              Description
            </button>
          </div>

          {mode === "manual" ? (
            <ManualBuilder
              base={base}
              setBase={setBase}
              features={features}
              setFeatures={setFeatures}
              modelData={manualModelData}
              manualPrompt={manualPrompt}
              usesApiAssistance={usesApiAssistance}
              onSubmit={handleManualSubmit}
              isLoading={isLoading}
            />
          ) : (
            <PromptBuilder
              prompt={prompt}
              setPrompt={setPrompt}
              onSubmit={handlePromptSubmit}
              isLoading={isLoading}
            />
          )}
        </section>

        <aside className="side-stack">
          <DrawingPreview base={base} features={features} usesApiAssistance={usesApiAssistance} />
          <DesignReview base={base} features={features} usesApiAssistance={usesApiAssistance} />
          <OutputPanel status={status} result={result} downloadUrl={downloadUrl} />
        </aside>
      </section>
    </main>
  );
}

function PromptBuilder({ prompt, setPrompt, onSubmit, isLoading }) {
  return (
    <form className="panel" onSubmit={onSubmit}>
      <div>
        <h2>Description builder</h2>
        <p>
          Describe the part in normal language. The backend converts the prompt into
          validated CAD JSON and exports a STEP file.
        </p>
      </div>
      <label>
        CAD prompt
        <textarea
          rows={8}
          value={prompt}
          placeholder="Describe the CAD model you want..."
          onChange={(event) => setPrompt(event.target.value)}
        />
      </label>
      <button type="submit" disabled={isLoading}>
        {isLoading ? "Generating..." : "Generate CAD"}
      </button>
    </form>
  );
}

function ManualBuilder({
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

function FeatureEditor({ feature, index, allFeatures, onChange, onRemove }) {
  const targetOptions = targetOptionsForFeature(allFeatures, index);
  const isCut = feature.operation === "cut";
  const needsDistance = !isCut || feature.depthMode === "blind";
  const showExactDimensions = !feature.reasonable && feature.profile !== "polyline";

  return (
    <article className="feature-card">
      <div className="section-heading">
        <h4>Feature {index + 1}</h4>
        <button type="button" className="secondary" onClick={onRemove}>
          Remove
        </button>
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

function DrawingPreview({ base, features, usesApiAssistance }) {
  const previewModel = useMemo(
    () => preview.buildPreviewModel({ base, features }),
    [base, features],
  );
  const sharedScale = sharedPreviewScale(previewModel);
  const dimensionPlan = useMemo(
    () => buildDimensionPlan(previewModel),
    [previewModel],
  );
  const primaryFeatureCount = previewModel.primaryCount;
  const featureSummary = primaryFeatureCount === 1
    ? "1 feature instance"
    : `${primaryFeatureCount} feature instances`;

  return (
    <section className="preview-card">
      <div className="section-heading">
        <div>
          <h2>Drawing preview</h2>
          <p>
            {previewModel.baseGeometry === null
              ? "Preview is waiting for exact base dimensions."
              : `Previewing ${featureSummary} across top/front/right views${previewModel.skippedCount > 0 ? `; ${previewModel.skippedCount} API-assisted or unsupported feature(s) are hidden.` : "."}`}
          </p>
        </div>
        <PreviewLegend />
      </div>

      {usesApiAssistance && (
        <p className="soft-warning">
          Some fields use API assistance, so the preview shows only exact manual geometry.
        </p>
      )}

      <div className="ansi-grid">
        <DrawingView
          title="Top view"
          viewData={previewModel.views.top}
          view="top"
          sharedScale={sharedScale}
          dimensionPlan={dimensionPlan.top}
        />
        <div className="ansi-note">
          ANSI third-angle layout: top view above front, right-side view to the right.
        </div>
        <DrawingView
          title="Front view"
          viewData={previewModel.views.front}
          view="front"
          sharedScale={sharedScale}
          dimensionPlan={dimensionPlan.front}
        />
        <DrawingView
          title="Right view"
          viewData={previewModel.views.right}
          view="right"
          sharedScale={sharedScale}
          dimensionPlan={dimensionPlan.right}
        />
      </div>
    </section>
  );
}

function DrawingView({ title, viewData, view, sharedScale, dimensionPlan }) {
  const baseGeometry = viewData.baseGeometry;
  const features = viewData.features.filter((feature) => preview.validBounds(feature.bounds));
  const geometryBounds = baseGeometry === null
    ? [-50, -30, 50, 30]
    : preview.allPreviewBounds(baseGeometry, features);
  const worldBounds = expandBoundsForAnnotations(geometryBounds);
  const mapper = preview.createPreviewMapper(worldBounds, sharedScale);
  const primaryFeatureCount = features.filter((record) => record.isPrimary).length;
  const projectedDimensionCount = features.filter((record) => shouldDimensionProjectedFeature(record)).length;
  const featureGroups = buildFeatureGroups(features);
  const annotationLayout = buildAnnotationLayout({
    baseGeometry,
    features,
    mapper,
    annotationBounds: worldBounds,
    dimensionPlan,
    featureGroups,
  });

  return (
    <div className={`drawing-view ${view}-view`}>
      <h3>{title}</h3>
      <svg viewBox={`0 0 ${preview.PREVIEW_WIDTH} ${preview.PREVIEW_HEIGHT}`} role="img" aria-label={title}>
        <PreviewDefs />
        <PreviewGrid mapper={mapper} worldBounds={worldBounds} />

        {baseGeometry === null ? (
          <text className="preview-empty-text" x={preview.PREVIEW_WIDTH / 2} y={preview.PREVIEW_HEIGHT / 2} textAnchor="middle">
            Enter exact base dimensions
          </text>
        ) : (
          <>
            <BasePreview baseGeometry={baseGeometry} mapper={mapper} />
            <OverallDimensions
              baseGeometry={baseGeometry}
              mapper={mapper}
              annotationBounds={worldBounds}
              dimensionSelection={dimensionPlan.base}
            />
          </>
        )}

        {features.map((feature) => (
          <FeaturePreview
            key={`${feature.featureNumber}-${view}-${feature.bounds.join(",")}-${feature.isPrimary}`}
            feature={feature}
            mapper={mapper}
            featureCount={primaryFeatureCount}
            projectedDimensionCount={projectedDimensionCount}
            featureGroups={featureGroups}
            annotation={annotationLayout.get(annotationKey(feature))}
          />
        ))}

        {baseGeometry !== null && features.length === 0 && (
          <text className="preview-note-text" x={preview.PREVIEW_WIDTH / 2} y={preview.PREVIEW_HEIGHT - 16} textAnchor="middle">
            No exact features in this view
          </text>
        )}
      </svg>
    </div>
  );
}

function PreviewDefs() {
  return (
    <defs>
      <marker
        id="preview-dimension-arrow"
        viewBox="0 0 10 10"
        refX="5"
        refY="5"
        markerWidth="5"
        markerHeight="5"
        orient="auto-start-reverse"
      >
        <path d="M 0 0 L 10 5 L 0 10 z" className="preview-dimension-arrow" />
      </marker>
    </defs>
  );
}

function PreviewGrid({ mapper, worldBounds }) {
  const origin = mapper.point(0, 0);
  const left = mapper.point(worldBounds[0], 0);
  const right = mapper.point(worldBounds[2], 0);
  const bottom = mapper.point(0, worldBounds[1]);
  const top = mapper.point(0, worldBounds[3]);

  return (
    <>
      <line className="preview-axis" x1={left[0]} y1={left[1]} x2={right[0]} y2={right[1]} />
      <line className="preview-axis" x1={bottom[0]} y1={bottom[1]} x2={top[0]} y2={top[1]} />
      <circle className="preview-origin" cx={origin[0]} cy={origin[1]} r="2.5" />
    </>
  );
}

function BasePreview({ baseGeometry, mapper }) {
  if (baseGeometry.profile === "rectangle" || baseGeometry.profile === "projection") {
    return <BoundsRectangle bounds={baseGeometry.bounds} mapper={mapper} className="preview-base" />;
  }

  if (baseGeometry.profile === "circle") {
    const center = mapper.point(0, 0);
    return (
      <>
        <circle className="preview-base" cx={center[0]} cy={center[1]} r={mapper.length(baseGeometry.radius)} />
        <Centerlines center={[0, 0]} size={baseGeometry.diameter * 1.25} mapper={mapper} />
      </>
    );
  }

  if (baseGeometry.profile === "polygon") {
    return (
      <polygon
        className="preview-base"
        points={preview.regularPolygonPoints([0, 0], baseGeometry.radius, baseGeometry.sides, mapper)}
      />
    );
  }

  return null;
}

function FeaturePreview({ feature, mapper, featureCount, projectedDimensionCount, featureGroups, annotation }) {
  let className = feature.operation === "cut" ? "preview-cut" : "preview-extrude";
  if (feature.isPrimary && !previewFeatureInsideBase(feature)) {
    className += " preview-outside";
  }
  const shouldAnnotateFeature = feature.isPrimary && isFirstFeatureInGroup(feature, featureGroups);
  const featureGroup = featureGroupFor(feature, featureGroups);
  const shouldShowLinearDimensions = Boolean(annotation?.dimensions)
    && shouldDimensionFeature(feature, featureCount, projectedDimensionCount);

  return (
    <g>
      <FeatureShape feature={feature} mapper={mapper} className={className} />
      {feature.profile === "circle" && feature.isPrimary && (
        <Centerlines center={feature.position} size={feature.radius * 2.6} mapper={mapper} />
      )}
      {shouldShowLinearDimensions && <FeatureDimensions feature={feature} mapper={mapper} annotation={annotation} />}
      {shouldAnnotateFeature && <PreviewLabel feature={feature} mapper={mapper} annotation={annotation} />}
      {shouldAnnotateFeature && <FeatureCallout feature={feature} mapper={mapper} annotation={annotation} featureGroup={featureGroup} />}
    </g>
  );
}

function shouldDimensionFeature(feature, primaryFeatureCount, projectedDimensionCount) {
  if (feature.profile !== "rectangle") {
    return false;
  }

  if (feature.isPrimary) {
    return primaryFeatureCount <= 1;
  }

  return shouldDimensionProjectedFeature(feature) && projectedDimensionCount <= 3;
}

function shouldDimensionProjectedFeature(feature) {
  return feature.profile === "rectangle" && !feature.isPrimary && feature.operation === "add_extrude";
}

function FeatureShape({ feature, mapper, className }) {
  if (feature.profile === "rectangle") {
    return <BoundsRectangle bounds={feature.bounds} mapper={mapper} className={className} />;
  }

  if (feature.profile === "circle") {
    const center = mapper.point(feature.position[0], feature.position[1]);
    return <circle className={className} cx={center[0]} cy={center[1]} r={mapper.length(feature.radius)} />;
  }

  if (feature.profile === "polygon") {
    return (
      <polygon
        className={className}
        points={preview.regularPolygonPoints(feature.position, feature.radius, feature.sides, mapper)}
      />
    );
  }

  return null;
}

function BoundsRectangle({ bounds, mapper, className }) {
  const topLeft = mapper.point(bounds[0], bounds[3]);
  const bottomRight = mapper.point(bounds[2], bounds[1]);
  return (
    <rect
      className={className}
      x={topLeft[0]}
      y={topLeft[1]}
      width={bottomRight[0] - topLeft[0]}
      height={bottomRight[1] - topLeft[1]}
    />
  );
}

function Centerlines({ center, size, mapper }) {
  const halfLength = size / 2;
  const horizontalStart = mapper.point(center[0] - halfLength, center[1]);
  const horizontalEnd = mapper.point(center[0] + halfLength, center[1]);
  const verticalStart = mapper.point(center[0], center[1] - halfLength);
  const verticalEnd = mapper.point(center[0], center[1] + halfLength);

  return (
    <>
      <line className="preview-centerline" x1={horizontalStart[0]} y1={horizontalStart[1]} x2={horizontalEnd[0]} y2={horizontalEnd[1]} />
      <line className="preview-centerline" x1={verticalStart[0]} y1={verticalStart[1]} x2={verticalEnd[0]} y2={verticalEnd[1]} />
    </>
  );
}

function PreviewLegend() {
  return (
    <div className="legend">
      <span><i className="legend-box base" />Base</span>
      <span><i className="legend-box extrusion" />Extrusion</span>
      <span><i className="legend-box cut" />Cut</span>
    </div>
  );
}

function sharedPreviewScale(previewModel) {
  if (previewModel.baseGeometry === null) {
    return null;
  }

  const viewBounds = Object.values(previewModel.views)
    .filter((view) => view.baseGeometry !== null)
    .map((view) => expandBoundsForAnnotations(preview.allPreviewBounds(view.baseGeometry, view.features)));

  if (viewBounds.length === 0) {
    return null;
  }

  return Math.min(...viewBounds.map(preview.previewScaleForBounds));
}

function buildDimensionPlan(previewModel) {
  const plan = {
    top: emptyViewDimensionPlan(),
    front: emptyViewDimensionPlan(),
    right: emptyViewDimensionPlan(),
  };

  const usedDimensionKeys = new Set();
  const viewLimits = {
    front: 8,
    top: 6,
    right: 5,
  };

  for (const viewName of ["front", "top", "right"]) {
    const viewData = previewModel.views[viewName];
    if (!viewData?.baseGeometry) {
      continue;
    }

    const viewPlan = plan[viewName];
    let assignedInView = 0;

    assignedInView += claimDimension({
      usedDimensionKeys,
      viewLimit: viewLimits[viewName],
      assignedInView,
      key: dimensionKeyForRecord(viewData.baseGeometry, "horizontal", "base"),
      selection: viewPlan.base,
      orientation: "horizontal",
    });
    assignedInView += claimDimension({
      usedDimensionKeys,
      viewLimit: viewLimits[viewName],
      assignedInView,
      key: dimensionKeyForRecord(viewData.baseGeometry, "vertical", "base"),
      selection: viewPlan.base,
      orientation: "vertical",
    });

    const features = viewData.features.filter((feature) => preview.validBounds(feature.bounds));
    const primaryFeatureCount = features.filter((record) => record.isPrimary).length;
    const projectedDimensionCount = features.filter((record) => shouldDimensionProjectedFeature(record)).length;

    for (const feature of features) {
      if (!shouldDimensionFeature(feature, primaryFeatureCount, projectedDimensionCount)) {
        continue;
      }

      const featureKey = annotationKey(feature);
      const featureSelection = viewPlan.features.get(featureKey) ?? { horizontal: false, vertical: false };

      assignedInView += claimDimension({
        usedDimensionKeys,
        viewLimit: viewLimits[viewName],
        assignedInView,
        key: dimensionKeyForRecord(feature, "horizontal", `feature:${feature.featureId}`),
        selection: featureSelection,
        orientation: "horizontal",
      });
      assignedInView += claimDimension({
        usedDimensionKeys,
        viewLimit: viewLimits[viewName],
        assignedInView,
        key: dimensionKeyForRecord(feature, "vertical", `feature:${feature.featureId}`),
        selection: featureSelection,
        orientation: "vertical",
      });

      if (featureSelection.horizontal || featureSelection.vertical) {
        viewPlan.features.set(featureKey, featureSelection);
      }
    }
  }

  return plan;
}

function emptyViewDimensionPlan() {
  return {
    base: { horizontal: false, vertical: false },
    features: new Map(),
  };
}

function claimDimension({
  usedDimensionKeys,
  viewLimit,
  assignedInView,
  key,
  selection,
  orientation,
}) {
  if (key === "" || usedDimensionKeys.has(key) || assignedInView >= viewLimit) {
    return 0;
  }

  usedDimensionKeys.add(key);
  selection[orientation] = true;
  return 1;
}

function dimensionKeyForRecord(record, orientation, ownerPrefix) {
  const axes = record.dimensionAxes ?? viewAxes(record.viewName);
  const axis = orientation === "horizontal" ? axes[0] : axes[1];
  if (!axis) {
    return "";
  }

  return `${ownerPrefix}:${axis}`;
}

function viewAxes(viewName) {
  if (viewName === "top") {
    return ["x", "y"];
  }

  if (viewName === "front") {
    return ["x", "z"];
  }

  if (viewName === "right") {
    return ["y", "z"];
  }

  return ["x", "y"];
}

function expandBoundsForAnnotations(bounds) {
  const width = preview.boundsWidth(bounds);
  const height = preview.boundsHeight(bounds);
  const pad = Math.max(width, height, 1) * 0.28;
  return [
    bounds[0] - pad,
    bounds[1] - pad,
    bounds[2] + pad * 0.7,
    bounds[3] + pad * 0.55,
  ];
}

function outsideDimensionLines(bounds, annotationBounds) {
  const width = preview.boundsWidth(annotationBounds);
  const height = preview.boundsHeight(annotationBounds);
  const horizontalGap = Math.max(height * 0.08, 5);
  const verticalGap = Math.max(width * 0.08, 5);

  return {
    horizontalY: annotationBounds[1] + horizontalGap,
    verticalX: annotationBounds[0] + verticalGap,
    horizontalTextDy: -6,
    verticalTextDx: -8,
  };
}

function featureDimensionLines(bounds) {
  const featureSize = Math.max(preview.boundsWidth(bounds), preview.boundsHeight(bounds), 1);
  const offset = Math.max(featureSize * 0.45, 7);

  return {
    horizontalY: bounds[1] - offset,
    verticalX: bounds[0] - offset,
    horizontalTextDy: -6,
    verticalTextDx: -8,
  };
}

function previewFeatureInsideBase(feature) {
  const baseBounds = feature.baseGeometry?.bounds;
  const bounds = feature.bounds;
  if (!preview.validBounds(baseBounds) || !preview.validBounds(bounds)) {
    return true;
  }

  return (
    bounds[0] >= baseBounds[0]
    && bounds[1] >= baseBounds[1]
    && bounds[2] <= baseBounds[2]
    && bounds[3] <= baseBounds[3]
  );
}

function annotationKey(feature) {
  return `${feature.featureNumber}-${feature.viewName}-${feature.bounds.join(",")}-${feature.isPrimary}`;
}

function featureGroupKey(feature) {
  return [
    feature.featureId,
    feature.viewName,
    feature.operation,
    feature.profile,
    feature.isPrimary ? "primary" : "projection",
  ].join(":");
}

function buildFeatureGroups(features) {
  const groups = new Map();

  for (const feature of features) {
    const key = featureGroupKey(feature);
    if (!groups.has(key)) {
      groups.set(key, {
        count: 0,
        firstAnnotationKey: annotationKey(feature),
      });
    }

    groups.get(key).count += 1;
  }

  return groups;
}

function featureGroupFor(feature, featureGroups) {
  return featureGroups.get(featureGroupKey(feature)) ?? {
    count: 1,
    firstAnnotationKey: annotationKey(feature),
  };
}

function isFirstFeatureInGroup(feature, featureGroups) {
  return featureGroupFor(feature, featureGroups).firstAnnotationKey === annotationKey(feature);
}

function buildAnnotationLayout({ baseGeometry, features, mapper, annotationBounds, dimensionPlan, featureGroups }) {
  const layout = new Map();
  const occupied = [];

  if (baseGeometry !== null) {
    for (const box of overallDimensionTextBoxes(baseGeometry, mapper, annotationBounds, dimensionPlan.base)) {
      occupied.push(box);
    }

    for (const box of geometryOccupancyBoxes(baseGeometry, features, mapper)) {
      occupied.push(box);
    }
  }

  for (const feature of features) {
    const dimensionSelection = dimensionPlan.features.get(annotationKey(feature));
    if (!dimensionSelection) {
      continue;
    }

    const dimensions = placeFeatureDimensions(feature, mapper, occupied, dimensionSelection);
    if (!dimensions) {
      continue;
    }

    for (const box of dimensions.boxes) {
      occupied.push(box);
    }

    layout.set(annotationKey(feature), {
      ...(layout.get(annotationKey(feature)) ?? {}),
      dimensions,
    });
  }

  for (const feature of features.filter((record) => record.isPrimary && isFirstFeatureInGroup(record, featureGroups))) {
    const label = placeFeatureLabel(feature, mapper, occupied);
    if (label) {
      occupied.push(label.box);
    }

    const calloutText = featureCalloutText(feature, mapper, featureGroupFor(feature, featureGroups));
    const callout = calloutText
      ? placeFeatureCallout(feature, mapper, calloutText, occupied)
      : null;
    if (callout) {
      occupied.push(callout.box);
    }

    layout.set(annotationKey(feature), {
      ...(layout.get(annotationKey(feature)) ?? {}),
      label,
      callout,
    });
  }

  return layout;
}

function geometryOccupancyBoxes(baseGeometry, features, mapper) {
  return [baseGeometry, ...features]
    .filter((record) => preview.validBounds(record.bounds))
    .map((record) => screenBoxFromBounds(record.bounds, mapper, 6));
}

function screenBoxFromBounds(bounds, mapper, margin = 0) {
  const first = mapper.point(bounds[0], bounds[3]);
  const second = mapper.point(bounds[2], bounds[1]);

  return {
    xMin: Math.min(first[0], second[0]) - margin,
    xMax: Math.max(first[0], second[0]) + margin,
    yMin: Math.min(first[1], second[1]) - margin,
    yMax: Math.max(first[1], second[1]) + margin,
  };
}

function placeFeatureDimensions(feature, mapper, occupied, dimensionSelection) {
  const bounds = feature.bounds;
  const featureSize = Math.max(preview.boundsWidth(bounds), preview.boundsHeight(bounds), 1);
  const nearOffset = Math.max(featureSize * 0.65, 8);
  const farOffset = Math.max(featureSize * 0.95, 12);
  const horizontalLabel = preview.formatDimension(preview.boundsWidth(bounds));
  const verticalLabel = preview.formatDimension(preview.boundsHeight(bounds));
  const boxes = [];
  const result = {};

  if (dimensionSelection.horizontal && horizontalLabel !== "") {
    const horizontal = chooseBestCandidate([
      horizontalDimensionCandidate(bounds, mapper, horizontalLabel, bounds[1] - nearOffset, 14),
      horizontalDimensionCandidate(bounds, mapper, horizontalLabel, bounds[3] + nearOffset, -6),
      horizontalDimensionCandidate(bounds, mapper, horizontalLabel, bounds[1] - farOffset, 14),
      horizontalDimensionCandidate(bounds, mapper, horizontalLabel, bounds[3] + farOffset, -6),
    ], occupied);

    if (horizontal) {
      result.horizontalY = horizontal.y;
      result.horizontalTextDy = horizontal.textDy;
      boxes.push(horizontal.box);
    }
  }

  if (dimensionSelection.vertical && verticalLabel !== "") {
    const vertical = chooseBestCandidate([
      verticalDimensionCandidate(bounds, mapper, verticalLabel, bounds[0] - nearOffset, -8),
      verticalDimensionCandidate(bounds, mapper, verticalLabel, bounds[2] + nearOffset, 14),
      verticalDimensionCandidate(bounds, mapper, verticalLabel, bounds[0] - farOffset, -8),
      verticalDimensionCandidate(bounds, mapper, verticalLabel, bounds[2] + farOffset, 14),
    ], [...occupied, ...boxes]);

    if (vertical) {
      result.verticalX = vertical.x;
      result.verticalTextDx = vertical.textDx;
      boxes.push(vertical.box);
    }
  }

  if (boxes.length === 0) {
    return null;
  }

  return {
    ...featureDimensionLines(bounds),
    ...result,
    boxes,
  };
}

function horizontalDimensionCandidate(bounds, mapper, label, y, textDy) {
  const textPoint = mapper.point((bounds[0] + bounds[2]) / 2, y);
  return {
    y,
    textDy,
    box: textBox(label, textPoint[0], textPoint[1] + textDy, "center"),
  };
}

function verticalDimensionCandidate(bounds, mapper, label, x, textDx) {
  const textPoint = mapper.point(x, (bounds[1] + bounds[3]) / 2);
  const textX = textPoint[0] + textDx;
  return {
    x,
    textDx,
    box: rotatedTextBox(label, textX, textPoint[1]),
  };
}

function overallDimensionTextBoxes(baseGeometry, mapper, annotationBounds, dimensionSelection) {
  if (baseGeometry.profile === "circle") {
    const leaderEnd = mapper.point(baseGeometry.radius * 0.75, baseGeometry.radius * 0.75);
    const textPoint = [
      Math.min(leaderEnd[0] + 20, preview.PREVIEW_WIDTH - 80) + 4,
      Math.max(leaderEnd[1] - 16, 20) - 4,
    ];
    return [textBox(`Ø${preview.formatDimension(baseGeometry.diameter)}`, textPoint[0], textPoint[1], "left")];
  }

  const dimensionLines = outsideDimensionLines(baseGeometry.bounds, annotationBounds);
  const horizontalPoint = mapper.point(
    (baseGeometry.bounds[0] + baseGeometry.bounds[2]) / 2,
    dimensionLines.horizontalY,
  );
  const verticalPoint = mapper.point(
    dimensionLines.verticalX,
    (baseGeometry.bounds[1] + baseGeometry.bounds[3]) / 2,
  );

  const boxes = [];

  if (dimensionSelection.horizontal) {
    boxes.push(textBox(
      preview.formatDimension(preview.boundsWidth(baseGeometry.bounds)),
      horizontalPoint[0],
      horizontalPoint[1] + dimensionLines.horizontalTextDy,
      "center",
    ));
  }

  if (dimensionSelection.vertical) {
    boxes.push(rotatedTextBox(
      preview.formatDimension(preview.boundsHeight(baseGeometry.bounds)),
      verticalPoint[0] + dimensionLines.verticalTextDx,
      verticalPoint[1],
    ));
  }

  return boxes;
}

function placeFeatureLabel(feature, mapper, occupied) {
  const center = mapper.point(...preview.boundsCenter(feature.bounds));
  const label = String(feature.featureNumber);
  const candidates = [
    [center[0], center[1] + 5],
    [center[0], center[1] - 13],
    [center[0] + 16, center[1] + 5],
    [center[0] - 16, center[1] + 5],
  ];

  return chooseBestCandidate(
    candidates.map(([x, y]) => ({
      x,
      y,
      box: textBox(label, x, y, "center", 18, 20),
    })),
    occupied,
  );
}

function placeFeatureCallout(feature, mapper, calloutText, occupied) {
  const center = mapper.point(...preview.boundsCenter(feature.bounds));
  const topRight = mapper.point(feature.bounds[2], feature.bounds[3]);
  const bottomRight = mapper.point(feature.bounds[2], feature.bounds[1]);
  const topLeft = mapper.point(feature.bounds[0], feature.bounds[3]);
  const bottomLeft = mapper.point(feature.bounds[0], feature.bounds[1]);
  const midTop = mapper.point((feature.bounds[0] + feature.bounds[2]) / 2, feature.bounds[3]);
  const midBottom = mapper.point((feature.bounds[0] + feature.bounds[2]) / 2, feature.bounds[1]);

  const candidates = [
    calloutCandidate(calloutText, center, topRight, [34, -34], "left"),
    calloutCandidate(calloutText, center, bottomRight, [34, 42], "left"),
    calloutCandidate(calloutText, center, topLeft, [-34, -34], "right"),
    calloutCandidate(calloutText, center, bottomLeft, [-34, 42], "right"),
    calloutCandidate(calloutText, center, midTop, [0, -42], "center"),
    calloutCandidate(calloutText, center, midBottom, [0, 50], "center"),
  ];

  return chooseBestCandidate(candidates, occupied);
}

function calloutCandidate(text, leaderStart, anchorPoint, offset, anchor) {
  const x = clamp(anchorPoint[0] + offset[0], 24, preview.PREVIEW_WIDTH - 24);
  const y = clamp(anchorPoint[1] + offset[1], 24, preview.PREVIEW_HEIGHT - 24);
  return {
    leaderStart,
    leaderEnd: [x, y],
    textPoint: [x + (anchor === "left" ? 5 : anchor === "right" ? -5 : 0), y - 4],
    textAnchor: anchor,
    box: textBox(text, x, y - 4, anchor),
  };
}

function chooseBestCandidate(candidates, occupied) {
  const scored = candidates.map((candidate) => ({
    ...candidate,
    score: collisionScore(candidate.box, occupied) + offscreenPenalty(candidate.box),
  }));
  scored.sort((a, b) => a.score - b.score);
  return scored[0] || null;
}

function collisionScore(box, occupied) {
  return occupied.reduce((total, otherBox) => {
    if (!boxesOverlap(box, otherBox)) {
      return total;
    }
    const overlapX = Math.min(box.xMax, otherBox.xMax) - Math.max(box.xMin, otherBox.xMin);
    const overlapY = Math.min(box.yMax, otherBox.yMax) - Math.max(box.yMin, otherBox.yMin);
    return total + Math.max(overlapX, 0) * Math.max(overlapY, 0) + 1000;
  }, 0);
}

function offscreenPenalty(box) {
  const left = Math.max(0, -box.xMin);
  const top = Math.max(0, -box.yMin);
  const right = Math.max(0, box.xMax - preview.PREVIEW_WIDTH);
  const bottom = Math.max(0, box.yMax - preview.PREVIEW_HEIGHT);
  return (left + top + right + bottom) * 500;
}

function textBox(text, x, y, anchor = "left", characterWidth = 9.5, height = 22) {
  const width = Math.max(String(text).length * characterWidth + 8, 18);
  let xMin = x;
  if (anchor === "center") {
    xMin = x - width / 2;
  } else if (anchor === "right") {
    xMin = x - width;
  }

  return {
    xMin,
    xMax: xMin + width,
    yMin: y - height,
    yMax: y + 5,
  };
}

function rotatedTextBox(text, x, y) {
  const width = 24;
  const height = Math.max(String(text).length * 9.5 + 8, 18);
  return {
    xMin: x - width / 2,
    xMax: x + width / 2,
    yMin: y - height / 2,
    yMax: y + height / 2,
  };
}

function boxesOverlap(first, second, margin = 4) {
  return !(
    first.xMax + margin < second.xMin
    || first.xMin - margin > second.xMax
    || first.yMax + margin < second.yMin
    || first.yMin - margin > second.yMax
  );
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function OverallDimensions({ baseGeometry, mapper, annotationBounds, dimensionSelection }) {
  if (baseGeometry.profile === "circle") {
    if (!dimensionSelection.horizontal && !dimensionSelection.vertical) {
      return null;
    }

    const center = mapper.point(0, 0);
    const leaderEnd = mapper.point(baseGeometry.radius * 0.75, baseGeometry.radius * 0.75);
    const textPoint = [
      Math.min(leaderEnd[0] + 20, preview.PREVIEW_WIDTH - 80),
      Math.max(leaderEnd[1] - 16, 20),
    ];

    return (
      <g>
        <line className="preview-leader-line" x1={center[0]} y1={center[1]} x2={textPoint[0]} y2={textPoint[1]} />
        <text className="preview-callout-text" x={textPoint[0] + 4} y={textPoint[1] - 4}>
          Ø{preview.formatDimension(baseGeometry.diameter)}
        </text>
      </g>
    );
  }

  const dimensionLines = outsideDimensionLines(baseGeometry.bounds, annotationBounds);
  return (
    <>
      {dimensionSelection.horizontal && (
        <HorizontalDimension bounds={baseGeometry.bounds} mapper={mapper} label={preview.formatDimension(preview.boundsWidth(baseGeometry.bounds))} y={dimensionLines.horizontalY} textDy={dimensionLines.horizontalTextDy} />
      )}
      {dimensionSelection.vertical && (
        <VerticalDimension bounds={baseGeometry.bounds} mapper={mapper} label={preview.formatDimension(preview.boundsHeight(baseGeometry.bounds))} x={dimensionLines.verticalX} textDx={dimensionLines.verticalTextDx} />
      )}
    </>
  );
}

function FeatureDimensions({ feature, mapper, annotation }) {
  const dimensionLines = annotation?.dimensions ?? featureDimensionLines(feature.bounds);
  const dimensionSelection = annotation?.dimensions ?? { horizontal: true, vertical: true };
  const widthLabel = preview.formatDimension(preview.boundsWidth(feature.bounds));
  const heightLabel = preview.formatDimension(preview.boundsHeight(feature.bounds));

  return (
    <>
      {dimensionSelection.horizontal && widthLabel !== "" && <HorizontalDimension bounds={feature.bounds} mapper={mapper} label={widthLabel} y={dimensionLines.horizontalY} textDy={dimensionLines.horizontalTextDy} />}
      {dimensionSelection.vertical && heightLabel !== "" && <VerticalDimension bounds={feature.bounds} mapper={mapper} label={heightLabel} x={dimensionLines.verticalX} textDx={dimensionLines.verticalTextDx} />}
    </>
  );
}

function HorizontalDimension({ bounds, mapper, label, y, textDy = -6 }) {
  const left = mapper.point(bounds[0], y);
  const right = mapper.point(bounds[2], y);
  const leftExtensionStart = mapper.point(bounds[0], bounds[1]);
  const rightExtensionStart = mapper.point(bounds[2], bounds[1]);
  const textPoint = mapper.point((bounds[0] + bounds[2]) / 2, y);

  return (
    <g>
      <line className="preview-extension-line" x1={leftExtensionStart[0]} y1={leftExtensionStart[1]} x2={left[0]} y2={left[1]} />
      <line className="preview-extension-line" x1={rightExtensionStart[0]} y1={rightExtensionStart[1]} x2={right[0]} y2={right[1]} />
      <line className="preview-dimension-line" x1={left[0]} y1={left[1]} x2={right[0]} y2={right[1]} markerStart="url(#preview-dimension-arrow)" markerEnd="url(#preview-dimension-arrow)" />
      <text className="preview-dimension-text" x={textPoint[0]} y={textPoint[1] + textDy} textAnchor="middle">{label}</text>
    </g>
  );
}

function VerticalDimension({ bounds, mapper, label, x, textDx = -8 }) {
  const bottom = mapper.point(x, bounds[1]);
  const top = mapper.point(x, bounds[3]);
  const bottomExtensionStart = mapper.point(bounds[0], bounds[1]);
  const topExtensionStart = mapper.point(bounds[0], bounds[3]);
  const textPoint = mapper.point(x, (bounds[1] + bounds[3]) / 2);
  const textX = textPoint[0] + textDx;

  return (
    <g>
      <line className="preview-extension-line" x1={bottomExtensionStart[0]} y1={bottomExtensionStart[1]} x2={bottom[0]} y2={bottom[1]} />
      <line className="preview-extension-line" x1={topExtensionStart[0]} y1={topExtensionStart[1]} x2={top[0]} y2={top[1]} />
      <line className="preview-dimension-line" x1={bottom[0]} y1={bottom[1]} x2={top[0]} y2={top[1]} markerStart="url(#preview-dimension-arrow)" markerEnd="url(#preview-dimension-arrow)" />
      <text
        className="preview-dimension-text"
        x={textX}
        y={textPoint[1]}
        textAnchor="middle"
        transform={`rotate(-90 ${textX} ${textPoint[1]})`}
      >
        {label}
      </text>
    </g>
  );
}

function PreviewLabel({ feature, mapper, annotation }) {
  const fallback = mapper.point(...preview.boundsCenter(feature.bounds));
  const x = annotation?.label?.x ?? fallback[0];
  const y = annotation?.label?.y ?? fallback[1] + 4;
  return (
    <text className="preview-label" x={x} y={y}>
      {feature.featureNumber}
    </text>
  );
}

function FeatureCallout({ feature, mapper, annotation, featureGroup }) {
  const center = mapper.point(...preview.boundsCenter(feature.bounds));
  const calloutText = featureCalloutText(feature, mapper, featureGroup);

  if (calloutText === "") {
    return null;
  }

  const leaderEnd = annotation?.callout?.leaderEnd ?? [
    Math.min(center[0] + 36, preview.PREVIEW_WIDTH - 90),
    Math.max(center[1] - 32, 28),
  ];
  const textPoint = annotation?.callout?.textPoint ?? [leaderEnd[0] + 5, leaderEnd[1] - 4];
  const textAnchor = annotation?.callout?.textAnchor ?? "left";

  return (
    <g>
      <line className="preview-leader-line" x1={center[0]} y1={center[1]} x2={leaderEnd[0]} y2={leaderEnd[1]} />
      <text className="preview-callout-text" x={textPoint[0]} y={textPoint[1]} textAnchor={textAnchor}>
        {calloutText}
      </text>
    </g>
  );
}

function featureCalloutText(feature, mapper, featureGroup = { count: 1 }) {
  const countPrefix = featureGroup.count > 1 ? `${featureGroup.count}X ` : "";

  if (feature.profile === "circle") {
    let calloutText = `${countPrefix}Ø${preview.formatDimension(feature.radius * 2)}`;
    if (feature.operation === "cut") {
      calloutText += feature.feature?.depthMode === "blind" ? " CUT" : " THRU";
    } else {
      calloutText += " BOSS";
    }
    return calloutText;
  }

  if (feature.profile === "rectangle") {
    const renderedWidth = mapper.length(preview.boundsWidth(feature.bounds));
    const renderedHeight = mapper.length(preview.boundsHeight(feature.bounds));
    if (
      featureGroup.count === 1
      &&
      renderedWidth >= preview.SMALL_FEATURE_CALLOUT_THRESHOLD
      && renderedHeight >= preview.SMALL_FEATURE_CALLOUT_THRESHOLD
    ) {
      return "";
    }
    const operationText = feature.operation === "cut" ? "CUT" : "BOSS";
    return `${countPrefix}${preview.formatDimension(feature.width)} × ${preview.formatDimension(feature.height)} ${operationText}`;
  }

  if (feature.profile === "polygon") {
    return `${countPrefix}${feature.sides} SIDES ON Ø${preview.formatDimension(feature.radius * 2)}`;
  }

  return "";
}

function DesignReview({ base, features, usesApiAssistance }) {
  const previewModel = useMemo(
    () => preview.buildPreviewModel({ base, features }),
    [base, features],
  );
  const warnings = previewModel.warnings;
  const isClear = warnings.length === 1 && warnings[0].severity === "success";

  return (
    <section className="review-card">
      <h2>Design review</h2>
      {usesApiAssistance && (
        <p className="soft-warning">
          API-assisted fields cannot be fully checked until model data is generated.
        </p>
      )}
      <div className={isClear ? "review-message ok" : "review-message warn"}>
        <strong>{isClear ? warnings[0].title : `${warnings.length} review item${warnings.length > 1 ? "s" : ""}`}</strong>
        {isClear && <p>{warnings[0].message}</p>}
        {!isClear && (
          <div className="review-list">
            {warnings.map((warning) => (
              <div className={`review-item ${warning.severity}`} key={`${warning.title}-${warning.message}`}>
                <strong>{warning.title}</strong>
                <p>{warning.message}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function OutputPanel({ status, result, downloadUrl }) {
  return (
    <section className="result-card">
      <h2>Output</h2>
      <p className={result?.status === "error" ? "status error" : "status"}>
        {status || "Run a prompt or manual model to see output."}
      </p>

      {downloadUrl && (
        <a className="download-link" href={downloadUrl}>
          Download STEP file
        </a>
      )}

      <pre>{result ? JSON.stringify(result, null, 2) : "No result yet."}</pre>
    </section>
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
        {options.map(([optionValue, labelText]) => (
          <option key={optionValue} value={optionValue}>
            {labelText}
          </option>
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
