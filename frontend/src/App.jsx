import { useMemo, useState } from "react";
import {
  buildFromModelData,
  generateFromPrompt,
  generateFromPromptIntent,
  getDownloadUrl,
} from "./api.js";
import { DrawingPreview } from "./DrawingPreview.jsx";
import { FeatureTreePanel } from "./FeatureTreePanel.jsx";
import { ManualBuilder } from "./ManualBuilder.jsx";
import {
  buildManualModelData,
  buildManualPrompt,
  createFeature,
  defaultBase,
  hasApiAssistedFields,
} from "./modelBuilders.js";
import { DesignReview, OutputPanel } from "./SidePanels.jsx";

export default function App() {
  const [mode, setMode] = useState("manual");
  const [promptGenerationMode, setPromptGenerationMode] = useState("direct");
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
    if (promptGenerationMode === "intent") {
      runRequest(() => generateFromPromptIntent(prompt));
      return;
    }

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

  function handleTargetReferenceClick(reference) {
    setMode("manual");
    setFeatures((currentFeatures) => {
      const feature = createFeature(currentFeatures.length + 1);

      if (reference.kind === "edge") {
        return [
          ...currentFeatures,
          {
            ...feature,
            operation: "chamfer",
            target: reference.name,
            amount: 1,
          },
        ];
      }

      return [
        ...currentFeatures,
        {
          ...feature,
          operation: "add_extrude",
          target: reference.name,
        },
      ];
    });
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
              generationMode={promptGenerationMode}
              setGenerationMode={setPromptGenerationMode}
              onSubmit={handlePromptSubmit}
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
          <OutputPanel status={status} result={result} downloadUrl={downloadUrl} />
        </aside>
      </section>
    </main>
  );
}

function PromptBuilder({
  prompt,
  setPrompt,
  generationMode,
  setGenerationMode,
  onSubmit,
  isLoading,
}) {
  return (
    <form className="panel" onSubmit={onSubmit}>
      <div>
        <h2>Description builder</h2>
        <p>
          Describe the part in normal language. The backend converts the prompt into
          validated CAD JSON and exports a STEP file.
        </p>
      </div>
      <fieldset className="mode-choice">
        <legend>Generation mode</legend>
        <label>
          <input
            type="radio"
            name="prompt-generation-mode"
            checked={generationMode === "direct"}
            onChange={() => setGenerationMode("direct")}
          />
          <span>
            Direct CAD JSON
            <small>Current production path. Best for general compatibility.</small>
          </span>
        </label>
        <label>
          <input
            type="radio"
            name="prompt-generation-mode"
            checked={generationMode === "intent"}
            onChange={() => setGenerationMode("intent")}
          />
          <span>
            Design intent beta
            <small>Experimental path for relationships like centered, near corners, and bolt circles.</small>
          </span>
        </label>
      </fieldset>
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
        {isLoading ? "Generating..." : generationMode === "intent" ? "Generate with intent beta" : "Generate CAD"}
      </button>
    </form>
  );
}
