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

export function OutputPanel({
  status,
  result,
  downloadUrl,
  onDownloadSolidWorks,
  isSolidWorksLoading,
  solidWorksStatus,
}) {
  const hasRequestError = status.startsWith("Error:");

  return (
    <section className="result-card">
      <h2>Output</h2>
      <p className={hasRequestError || result?.status === "error" ? "status error" : "status"}>
        {status || "No output yet."}
      </p>

      {downloadUrl && result?.model_data && (
        <div className="download-section">
          <div className="download-actions">
            <a className="download-link" href={downloadUrl}>
              <DownloadIcon />
              Download STEP
            </a>
            <button
              className="download-link solidworks-download"
              type="button"
              onClick={onDownloadSolidWorks}
              disabled={isSolidWorksLoading}
            >
              <DownloadIcon />
              {isSolidWorksLoading ? "Preparing package..." : "Download SolidWorks package"}
            </button>
          </div>
          <p className="download-note">
            Builds an editable SLDPRT on your computer. Requires Windows and an installed copy of SolidWorks.
          </p>
          {solidWorksStatus && (
            <p
              className={solidWorksStatus.includes("unavailable")
                ? "package-status error"
                : "package-status"}
              role="status"
            >
              {solidWorksStatus}
            </p>
          )}
        </div>
      )}

      {result?.revision_summary && (
        <RevisionSummary
          revision={result.revision}
          summary={result.revision_summary}
        />
      )}

      {result?.performance && <PerformanceSummary performance={result.performance} />}

      {result && <pre>{JSON.stringify(result, null, 2)}</pre>}
    </section>
  );
}

function DownloadIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M12 3v12m0 0 5-5m-5 5-5-5M5 21h14" />
    </svg>
  );
}

function RevisionSummary({ revision, summary }) {
  const changeCount = Number(summary.change_count ?? 0);
  const noun = changeCount === 1 ? "operation" : "operations";
  const summaryText = summary.operation_order_changed && changeCount === 1
    ? "Feature build order changed"
    : `${changeCount} CAD ${noun} changed`;

  return (
    <div className="revision-summary">
      <strong>Revision {revision}</strong>
      <span>{summaryText}</span>
    </div>
  );
}

function PerformanceSummary({ performance }) {
  const rows = [
    ["Total", performance.total_seconds],
    ["AI generation", performance.api_seconds],
    ["Intent lowering", performance.lowering_seconds],
    ["Validation", performance.validation_seconds],
    ["CAD build", performance.build_seconds],
    ["STEP export", performance.export_seconds],
    ["Quality", performance.quality_seconds],
  ].filter(([, value]) => value !== undefined);

  return (
    <div className="performance-summary">
      <div className="performance-heading">
        <strong>Performance</strong>
        <span className={performance.cache_hit ? "cache-hit" : "cache-miss"}>
          {performance.cache_hit ? "Cache hit" : "Fresh run"}
        </span>
      </div>
      <dl>
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{formatSeconds(value)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function formatSeconds(value) {
  return `${Number(value).toFixed(3)}s`;
}

export function RepairHistoryPanel({ repairHistory }) {
  if (!repairHistory?.length) {
    return null;
  }

  return (
    <section className="review-card">
      <h2>Repair history</h2>
      <div className="repair-history-list">
        {repairHistory.map((repair, index) => (
          <RepairHistoryItem
            key={`repair-${index + 1}`}
            repair={repair}
            attemptNumber={index + 1}
          />
        ))}
      </div>
    </section>
  );
}

function RepairHistoryItem({ repair, attemptNumber }) {
  const failureAnalysis = repair.failure_analysis ?? {};
  const qualityReport = failureAnalysis.quality_report;
  const issueCodes = failureAnalysis.repairable_quality_codes ?? [];
  const suggestions = failureAnalysis.suggested_fixes ?? [];
  const statusLabel = qualityReport?.status ?? (failureAnalysis.passed ? "pass" : "needs repair");
  const statusClass = String(statusLabel).replace(/\s+/g, "-");

  return (
    <article className="repair-history-item">
      <div className="repair-history-heading">
        <strong>Attempt {attemptNumber}</strong>
        <span className={`repair-status ${statusClass}`}>{statusLabel}</span>
      </div>

      <p>
        <span className="repair-label">Reason:</span>{" "}
        {failureAnalysis.reason ?? "No repair reason was provided."}
      </p>

      {failureAnalysis.failure_type && (
        <p>
          <span className="repair-label">Failure type:</span>{" "}
          <code>{failureAnalysis.failure_type}</code>
        </p>
      )}

      {issueCodes.length > 0 && (
        <div className="repair-chip-row" aria-label="Repairable quality issue codes">
          {issueCodes.map((code) => (
            <code className="repair-chip" key={code}>{code}</code>
          ))}
        </div>
      )}

      {suggestions.length > 0 && (
        <ul className="repair-suggestion-list">
          {suggestions.map((suggestion) => (
            <li key={suggestion}>{suggestion}</li>
          ))}
        </ul>
      )}
    </article>
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

  return (
    <section className="review-card">
      <h2>Generated model review</h2>
      <div className={isClear ? "review-message ok" : "review-message warn"}>
        <strong>{isClear ? clearTitle : `${warnings.length} generated review item${warnings.length > 1 ? "s" : ""}`}</strong>
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
