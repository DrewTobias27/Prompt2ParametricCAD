import { useMemo, useState } from "react";
import { buildFromModelData, generateFromPrompt, getDownloadUrl } from "./api.js";
import { buildManualModelData } from "./modelBuilders.js";

const defaultBase = {
  profile: "rectangle",
  width: 80,
  height: 50,
  diameter: 60,
  sides: 6,
  thickness: 6,
};

function createFeature() {
  return {
    operation: "add_extrude",
    target: "base.top",
    profile: "rectangle",
    width: 20,
    height: 12,
    diameter: 10,
    x: 0,
    y: 0,
    amount: 6,
    depthMode: "through",
  };
}

export default function App() {
  const [mode, setMode] = useState("prompt");
  const [prompt, setPrompt] = useState("Create an 80 mm by 50 mm rectangular plate that is 6 mm thick.");
  const [base, setBase] = useState(defaultBase);
  const [features, setFeatures] = useState([]);
  const [status, setStatus] = useState("");
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const manualModelData = useMemo(
    () => buildManualModelData({ base, features }),
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
            A React frontend for the CadQuery/FastAPI backend. This is the start
            of the Vercel-ready version.
          </p>
        </div>
        <div className="hero-card">
          <span>Frontend migration</span>
          <strong>React + Vite</strong>
        </div>
      </header>

      <section className="workspace">
        <div className="builder-card">
          <div className="mode-tabs" role="tablist" aria-label="Builder mode">
            <button
              className={mode === "prompt" ? "active" : ""}
              type="button"
              onClick={() => setMode("prompt")}
            >
              Description
            </button>
            <button
              className={mode === "manual" ? "active" : ""}
              type="button"
              onClick={() => setMode("manual")}
            >
              Manual builder
            </button>
          </div>

          {mode === "prompt" ? (
            <PromptBuilder
              prompt={prompt}
              setPrompt={setPrompt}
              onSubmit={handlePromptSubmit}
              isLoading={isLoading}
            />
          ) : (
            <ManualBuilder
              base={base}
              setBase={setBase}
              features={features}
              setFeatures={setFeatures}
              modelData={manualModelData}
              onSubmit={handleManualSubmit}
              isLoading={isLoading}
            />
          )}
        </div>

        <aside className="result-card">
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
        <p>Describe the part. The backend will convert it into validated CAD JSON.</p>
      </div>
      <label>
        CAD prompt
        <textarea
          rows={8}
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
        />
      </label>
      <button type="submit" disabled={isLoading}>
        {isLoading ? "Generating..." : "Generate CAD"}
      </button>
    </form>
  );
}

function ManualBuilder({ base, setBase, features, setFeatures, modelData, onSubmit, isLoading }) {
  function updateBase(field, value) {
    setBase((current) => ({ ...current, [field]: value }));
  }

  function updateFeature(index, field, value) {
    setFeatures((current) => current.map((feature, featureIndex) => (
      featureIndex === index ? { ...feature, [field]: value } : feature
    )));
  }

  return (
    <form className="panel" onSubmit={onSubmit}>
      <div>
        <h2>Manual builder</h2>
        <p>This is the first React version of the guided CAD builder.</p>
      </div>

      <section className="form-section">
        <h3>Main frame</h3>
        <div className="field-grid">
          <SelectField
            label="Shape"
            value={base.profile}
            onChange={(value) => updateBase("profile", value)}
            options={[
              ["rectangle", "Rectangle"],
              ["circle", "Circle"],
              ["polygon", "Polygon"],
            ]}
          />
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
      </section>

      <section className="form-section">
        <div className="section-heading">
          <h3>Features</h3>
          <button type="button" onClick={() => setFeatures([...features, createFeature()])}>
            Add feature
          </button>
        </div>

        {features.length === 0 && (
          <p className="muted">No features yet. Add an extrusion or cut to the base.</p>
        )}

        {features.map((feature, index) => (
          <FeatureEditor
            key={index}
            feature={feature}
            index={index}
            onChange={updateFeature}
            onRemove={() => setFeatures(features.filter((_, featureIndex) => featureIndex !== index))}
          />
        ))}
      </section>

      <section className="form-section">
        <h3>Generated model data</h3>
        <pre className="model-preview">{JSON.stringify(modelData, null, 2)}</pre>
      </section>

      <button type="submit" disabled={isLoading}>
        {isLoading ? "Building..." : "Build manual model"}
      </button>
    </form>
  );
}

function FeatureEditor({ feature, index, onChange, onRemove }) {
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
          label="Target"
          value={feature.target}
          onChange={(value) => onChange(index, "target", value)}
          options={[
            ["base.top", "Base top"],
            ["base.front", "Base front"],
            ["base.right", "Base right"],
          ]}
        />
        <SelectField
          label="Shape"
          value={feature.profile}
          onChange={(value) => onChange(index, "profile", value)}
          options={[
            ["rectangle", "Rectangle"],
            ["circle", "Circle"],
          ]}
        />
        {feature.profile === "rectangle" ? (
          <>
            <NumberField label="Width" value={feature.width} onChange={(value) => onChange(index, "width", value)} />
            <NumberField label="Height" value={feature.height} onChange={(value) => onChange(index, "height", value)} />
          </>
        ) : (
          <NumberField label="Diameter" value={feature.diameter} onChange={(value) => onChange(index, "diameter", value)} />
        )}
        <NumberField label="Position X" value={feature.x} onChange={(value) => onChange(index, "x", value)} />
        <NumberField label="Position Y" value={feature.y} onChange={(value) => onChange(index, "y", value)} />
        {feature.operation === "cut" && (
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
        {(feature.operation === "add_extrude" || feature.depthMode === "blind") && (
          <NumberField
            label={feature.operation === "cut" ? "Cut depth" : "Extrusion distance"}
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
        {options.map(([optionValue, labelText]) => (
          <option key={optionValue} value={optionValue}>
            {labelText}
          </option>
        ))}
      </select>
    </label>
  );
}
