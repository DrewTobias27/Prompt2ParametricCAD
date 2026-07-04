import { useMemo, useState } from "react";
import { buildFromModelData, generateFromPrompt, getDownloadUrl } from "./api.js";
import { DrawingPreview } from "./DrawingPreview.jsx";
import { ManualBuilder } from "./ManualBuilder.jsx";
import {
  buildManualModelData,
  buildManualPrompt,
  defaultBase,
  hasApiAssistedFields,
} from "./modelBuilders.js";
import { DesignReview, OutputPanel } from "./SidePanels.jsx";

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
