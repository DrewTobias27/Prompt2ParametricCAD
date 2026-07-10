import { useMemo } from "react";
import { reviewGeneratedModel } from "./generatedModelReview.js";
import * as preview from "./previewEngine.js";

export function DesignReview({ base, features, usesApiAssistance }) {
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
                {warning.suggestion && <p className="review-suggestion">Suggested fix: {warning.suggestion}</p>}
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

export function OutputPanel({ status, result, downloadUrl }) {
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

export function GeneratedModelReview({ modelData, qualityReport }) {
  const warnings = useMemo(
    () => qualityReport?.issues ?? reviewGeneratedModel(modelData),
    [modelData, qualityReport],
  );
  if (!modelData) {
    return null;
  }

  const isBackendClear = qualityReport?.status === "pass" && warnings.length === 0;
  const isFallbackClear = warnings.length === 1 && warnings[0].severity === "success";
  const isClear = isBackendClear || isFallbackClear;
  const clearTitle = isBackendClear
    ? "Generated model quality gate passed"
    : warnings[0]?.title;
  const clearMessage = isBackendClear
    ? "The backend quality report found no schema or structural issues."
    : warnings[0]?.message;

  return (
    <section className="review-card">
      <h2>Generated model review</h2>
      <p>
        Deterministic checks on the API-generated CAD JSON before deeper geometry validation.
      </p>
      <div className={isClear ? "review-message ok" : "review-message warn"}>
        <strong>{isClear ? clearTitle : `${warnings.length} generated review item${warnings.length > 1 ? "s" : ""}`}</strong>
        {isClear && <p>{clearMessage}</p>}
        {!isClear && (
          <div className="review-list">
            {warnings.map((warning) => (
              <div className={`review-item ${warning.severity}`} key={`${warning.title}-${warning.message}`}>
                <strong>{warning.title}</strong>
                <p>{warning.message}</p>
                {warning.suggestion && <p className="review-suggestion">Suggested fix: {warning.suggestion}</p>}
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
