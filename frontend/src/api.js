const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

async function postJson(path, payload) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Request failed with status ${response.status}`);
  }

  return response.json();
}

export function generateFromPrompt(prompt) {
  return postJson("/generate", { prompt });
}

export function generateFromPromptIntent(prompt) {
  return postJson("/generate-intent", { prompt });
}

export function buildFromModelData(modelData, filenameHint) {
  return postJson("/build", {
    model_data: modelData,
    filename_hint: filenameHint,
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
