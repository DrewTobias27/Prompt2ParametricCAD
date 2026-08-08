import { useCallback, useMemo, useState } from "react";
import {
  buildFromModelData,
  generateFromPrompt,
  getDownloadUrl,
  refineGeneratedDesign,
} from "./api.js";
import { DrawingPreview } from "./DrawingPreview.jsx";
import { FeatureTreePanel } from "./FeatureTreePanel.jsx";
import { resolveManualModelData } from "./manualAssistance.js";
import { ManualBuilder } from "./ManualBuilder.jsx";
import { modelDataToTreeView } from "./modelDataViewModel.js";
import {
  buildManualModelData,
  buildManualPrompt,
  createFeature,
  defaultBase,
  hasApiAssistedFields,
  isEdgeTreatment,
} from "./modelBuilders.js";
import {
  DesignReview,
  GeneratedModelReview,
  OutputPanel,
  RepairHistoryPanel,
} from "./SidePanels.jsx";

export default function App() {
  const [mode, setMode] = useState("manual");
  const [prompt, setPrompt] = useState("Create an 80 mm by 50 mm rectangular plate that is 6 mm thick.");
  const [base, setBase] = useState(defaultBase);
  const [features, setFeatures] = useState([]);
  const [activeFeatureId, setActiveFeatureId] = useState(null);
  const [status, setStatus] = useState("");
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [correction, setCorrection] = useState("");
  const [revisionHistory, setRevisionHistory] = useState([]);

  const usesApiAssistance = hasApiAssistedFields({ base, features });
  const manualModelData = useMemo(
    () => (usesApiAssistance ? null : buildManualModelData({ base, features })),
    [base, features, usesApiAssistance],
  );
  const manualPrompt = useMemo(
    () => buildManualPrompt({ base, features }),
    [base, features],
  );
  const generatedTreeView = useMemo(
    () => modelDataToTreeView(result?.model_data),
    [result],
  );
  const canRefine = result?.status === "success"
    && Boolean(result?.design_intent)
    && ["design_intent", "design_intent_refinement"].includes(
      result?.generation_path,
    );

  const updateBase = useCallback((update) => {
    setBase(update);
    setResult(null);
    setStatus("");
  }, []);

  const updateFeatures = useCallback((update) => {
    setFeatures(update);
    setResult(null);
    setStatus("");
  }, []);

  const updatePrompt = useCallback((value) => {
    setPrompt(value);
    setResult(null);
    setStatus("");
    setCorrection("");
    setRevisionHistory([]);
  }, []);

  function handleModeChange(nextMode) {
    if (nextMode === mode || isLoading) {
      return;
    }

    setMode(nextMode);
    setResult(null);
    setStatus("");
    setCorrection("");
    setRevisionHistory([]);
  }

  async function runRequest(request, {
    loadingMessage = "Generating CAD model...",
    clearResult = true,
    preserveResultOnError = false,
    onSuccess = null,
  } = {}) {
    setIsLoading(true);
    setStatus(loadingMessage);
    if (clearResult) {
      setResult(null);
    }

    try {
      const data = await request();
      if (data.status === "success") {
        setResult(data);
        setStatus("Success");
        onSuccess?.(data);
      } else {
        if (!preserveResultOnError) {
          setResult(data);
        }
        setStatus(`Error: ${data.message}`);
      }
    } catch (error) {
      setStatus(`Error: ${error.message}`);
      if (!preserveResultOnError) {
        setResult({ status: "error", message: error.message });
      }
    } finally {
      setIsLoading(false);
    }
  }

  function handlePromptSubmit(event) {
    event.preventDefault();
    setCorrection("");
    setRevisionHistory([]);
    runRequest(() => generateFromPrompt(prompt));
  }

  function handleRefinement() {
    const correctionText = correction.trim();
    const previousResult = result;
    if (!canRefine || !correctionText || !previousResult) {
      return;
    }

    runRequest(
      () => refineGeneratedDesign({
        originalPrompt: prompt,
        correction: correctionText,
        designIntent: previousResult.design_intent,
        revision: previousResult.revision ?? 1,
      }),
      {
        loadingMessage: "Applying correction...",
        clearResult: false,
        preserveResultOnError: true,
        onSuccess: () => {
          setRevisionHistory((history) => [
            ...history,
            { correction: correctionText, result: previousResult },
          ]);
          setCorrection("");
        },
      },
    );
  }

  function handleRestorePreviousRevision() {
    const previousRevision = revisionHistory.at(-1);
    if (!previousRevision || isLoading) {
      return;
    }

    setResult(previousRevision.result);
    setRevisionHistory((history) => history.slice(0, -1));
    setCorrection("");
    setStatus(`Restored revision ${previousRevision.result.revision ?? 1}.`);
  }

  function handleManualSubmit(event) {
    event.preventDefault();
    if (usesApiAssistance) {
      runRequest(async () => {
        const resolvedModelData = await resolveManualModelData({ base, features });
        return buildFromModelData(resolvedModelData, `manual ${base.profile} base`);
      });
      return;
    }

    runRequest(() => buildFromModelData(manualModelData, `manual ${base.profile} base`));
  }

  function handleTargetReferenceClick(reference) {
    handleModeChange("manual");
    const activeFeatureIndex = features.findIndex((feature) => feature.localId === activeFeatureId);
    const activeFeature = features[activeFeatureIndex];
    const canRetargetActiveFeature = activeFeature
      && referenceCanTargetFeature(reference, activeFeatureIndex)
      && ((reference.kind === "edge" && isEdgeTreatment(activeFeature))
        || (reference.kind === "face" && !isEdgeTreatment(activeFeature)));

    if (canRetargetActiveFeature) {
      updateFeatures((currentFeatures) => currentFeatures.map((feature) => (
        feature.localId === activeFeatureId
          ? { ...feature, target: reference.name }
          : feature
      )));
      setStatus(`Retargeted the active feature to ${reference.name}.`);
      return;
    }

    const feature = createFeature(features.length + 1);
    const newFeature = reference.kind === "edge"
      ? {
        ...feature,
        operation: "chamfer",
        target: reference.name,
        amount: 1,
      }
      : {
        ...feature,
        operation: "add_extrude",
        target: reference.name,
      };

    updateFeatures((currentFeatures) => [...currentFeatures, newFeature]);
    setActiveFeatureId(newFeature.localId);
    setStatus(
      reference.kind === "edge"
        ? `Added a chamfer targeting ${reference.name}.`
        : `Added an extrusion targeting ${reference.name}.`,
    );
  }

  const downloadUrl = getDownloadUrl(result?.download_url);

  return (
    <main className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Prompt2ParametricCAD</p>
          <h1>Build parametric CAD.</h1>
        </div>
      </header>

      <section className="workspace">
        <section className="builder-card">
          <div className="mode-tabs" role="tablist" aria-label="Builder mode">
            <button
              className={mode === "manual" ? "active" : ""}
              type="button"
              disabled={isLoading}
              onClick={() => handleModeChange("manual")}
            >
              Manual builder
            </button>
            <button
              className={mode === "prompt" ? "active" : ""}
              type="button"
              disabled={isLoading}
              onClick={() => handleModeChange("prompt")}
            >
              Description
            </button>
          </div>

          {mode === "manual" ? (
            <ManualBuilder
              base={base}
              setBase={updateBase}
              features={features}
              setFeatures={updateFeatures}
              activeFeatureId={activeFeatureId}
              setActiveFeatureId={setActiveFeatureId}
              modelData={manualModelData}
              manualPrompt={manualPrompt}
              usesApiAssistance={usesApiAssistance}
              onSubmit={handleManualSubmit}
              isLoading={isLoading}
            />
          ) : (
            <PromptBuilder
              prompt={prompt}
              setPrompt={updatePrompt}
              onSubmit={handlePromptSubmit}
              correction={correction}
              setCorrection={setCorrection}
              onRefine={handleRefinement}
              onRestorePreviousRevision={handleRestorePreviousRevision}
              canRefine={canRefine}
              canRestorePreviousRevision={revisionHistory.length > 0}
              revision={result?.revision ?? 1}
              isLoading={isLoading}
            />
          )}
        </section>

        <aside className="side-stack">
          {mode === "manual" && (
            <>
              <DrawingPreview base={base} features={features} usesApiAssistance={usesApiAssistance} />
              <FeatureTreePanel
                base={base}
                features={features}
                onTargetReferenceClick={handleTargetReferenceClick}
              />
              <DesignReview base={base} features={features} usesApiAssistance={usesApiAssistance} />
            </>
          )}
          {mode === "prompt" && generatedTreeView && (
            <>
              <FeatureTreePanel
                base={generatedTreeView.base}
                features={generatedTreeView.features}
                title="Generated feature tree"
              />
              <GeneratedModelReview
                modelData={result?.model_data}
                qualityReport={result?.quality_report}
              />
              <RepairHistoryPanel repairHistory={result?.repair_history} />
            </>
          )}
          <OutputPanel status={status} result={result} downloadUrl={downloadUrl} />
        </aside>
      </section>
    </main>
  );
}

function referenceCanTargetFeature(reference, featureIndex) {
  const [ownerId] = String(reference.name).split(".");
  if (ownerId === "base") {
    return true;
  }

  const match = ownerId.match(/^feature_(\d+)$/);
  if (!match) {
    return false;
  }

  return Number(match[1]) - 1 < featureIndex;
}

function PromptBuilder({
  prompt,
  setPrompt,
  onSubmit,
  correction,
  setCorrection,
  onRefine,
  onRestorePreviousRevision,
  canRefine,
  canRestorePreviousRevision,
  revision,
  isLoading,
}) {
  return (
    <form className="panel" onSubmit={onSubmit}>
      <div>
        <h2>Description builder</h2>
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
      {canRefine && (
        <section className="refinement-panel" aria-label="Refine generated CAD">
          <div className="refinement-heading">
            <div>
              <h3>Refine this result</h3>
              <p>Describe only what should change.</p>
            </div>
            <span>Revision {revision}</span>
          </div>
          <label>
            Correction
            <textarea
              rows={3}
              value={correction}
              placeholder="For example: move the four holes 5 mm farther from the corners."
              onChange={(event) => setCorrection(event.target.value)}
            />
          </label>
          <div className="refinement-actions">
            <button
              type="button"
              onClick={onRefine}
              disabled={isLoading || !correction.trim()}
            >
              {isLoading ? "Applying correction..." : "Apply correction"}
            </button>
            {canRestorePreviousRevision && (
              <button
                className="secondary"
                type="button"
                onClick={onRestorePreviousRevision}
                disabled={isLoading}
              >
                Restore previous revision
              </button>
            )}
          </div>
        </section>
      )}
    </form>
  );
}
