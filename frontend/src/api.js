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
