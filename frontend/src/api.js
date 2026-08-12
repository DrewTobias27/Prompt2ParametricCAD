const configuredApiUrl = import.meta.env?.VITE_API_BASE_URL?.trim();
const API_BASE_URL = configuredApiUrl
  || (import.meta.env?.DEV ? "/api" : "");

async function postJson(path, payload) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  let data = null;
  try {
    data = await response.json();
  } catch {
    // The status fallback below still gives a useful error for non-JSON failures.
  }

  if (!response.ok) {
    const detail = typeof data?.detail === "string"
      ? data.detail
      : data?.message;
    throw new Error(detail || `Request failed with status ${response.status}`);
  }

  return data;
}

async function postDownload(path, payload, fallbackFilename) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let detail = null;
    try {
      const data = await response.json();
      detail = typeof data?.detail === "string" ? data.detail : data?.message;
    } catch {
      // The status fallback remains useful for non-JSON server failures.
    }
    throw new Error(detail || `Request failed with status ${response.status}`);
  }

  const disposition = response.headers.get("Content-Disposition") || "";
  const filenameMatch = disposition.match(/filename="?([^";]+)"?/i);
  return {
    blob: await response.blob(),
    filename: filenameMatch?.[1] || fallbackFilename,
    editability: {
      numericParameterCount: numericHeader(
        response,
        "X-Prompt2CAD-Numeric-Parameters",
      ),
      namedBindingCount: numericHeader(
        response,
        "X-Prompt2CAD-Named-Bindings",
      ),
      relationControlledCount: numericHeader(
        response,
        "X-Prompt2CAD-Relation-Controls",
      ),
      unsupportedCount: numericHeader(
        response,
        "X-Prompt2CAD-Unsupported-Parameters",
      ),
      controlCoverageRatio: numericHeader(
        response,
        "X-Prompt2CAD-Control-Coverage",
      ),
    },
  };
}

function numericHeader(response, name) {
  const rawValue = response.headers.get(name);
  if (rawValue === null || rawValue.trim() === "") {
    return null;
  }

  const value = Number(rawValue);
  return Number.isFinite(value) ? value : null;
}

export function generateFromPrompt(prompt) {
  return postJson("/generate", { prompt });
}

export function refineGeneratedDesign({
  originalPrompt,
  correction,
  designIntent,
  revision,
}) {
  return postJson("/refine", {
    original_prompt: originalPrompt,
    correction,
    design_intent: designIntent,
    revision,
  });
}

export function buildFromModelData(modelData, filenameHint) {
  return postJson("/build", {
    model_data: modelData,
    filename_hint: filenameHint,
  });
}

export function getEditableModel(modelData) {
  return postJson("/editable-model", {
    model_data: modelData,
  });
}

export function createSolidWorksPackage(modelData, filenameHint) {
  return postDownload(
    "/solidworks-package",
    {
      model_data: modelData,
      filename_hint: filenameHint,
    },
    "prompt2cad-solidworks.zip",
  );
}

export function editModelParameters(modelData, updates, filenameHint) {
  return postJson("/edit-parameters", {
    model_data: modelData,
    updates,
    filename_hint: filenameHint,
  });
}

export function suggestBase({ profile, description, distance }) {
  return postJson("/suggest-base", {
    profile,
    description,
    distance,
  });
}

export function suggestFeature({ operationType, target, profile, description }) {
  return postJson("/suggest-feature", {
    operation_type: operationType,
    target,
    profile,
    description,
  });
}

export function getDownloadUrl(downloadUrl) {
  if (!downloadUrl) {
    return null;
  }

  if (downloadUrl.startsWith("http")) {
    return downloadUrl;
  }

  return `${API_BASE_URL}${downloadUrl}`;
}
