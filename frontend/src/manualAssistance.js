import { suggestBase, suggestFeature } from "./api.js";
import {
  buildBaseOperation,
  buildFeatureOperation,
  expandFeatureInstances,
  isEdgeTreatment,
} from "./modelBuilders.js";

const PROFILE_DIMENSION_FIELDS = {
  rectangle: ["width", "height"],
  circle: ["diameter"],
  polygon: ["diameter", "sides"],
  polyline: ["points"],
};

export async function resolveManualModelData(
  { base, features },
  {
    requestBaseSuggestion = suggestBase,
    requestFeatureSuggestion = suggestFeature,
  } = {},
) {
  const baseOperation = await resolveBaseOperation(base, requestBaseSuggestion);
  const featureOperationPromises = [];

  for (const [index, feature] of features.entries()) {
    const parentPromise = parentOperationPromise(
      feature.target,
      baseOperation,
      featureOperationPromises,
    );
    featureOperationPromises.push(parentPromise.then((targetOperation) => (
      resolveFeatureOperation({
        baseOperation,
        targetOperation,
        feature,
        featureNumber: index + 1,
        requestFeatureSuggestion,
      })
    )));
  }

  const featureOperations = await Promise.all(featureOperationPromises);

  return { operations: [baseOperation, ...featureOperations] };
}

async function resolveBaseOperation(base, requestBaseSuggestion) {
  if (!base.reasonable && base.profile !== "polyline") {
    return buildBaseOperation(base);
  }

  const data = await requestBaseSuggestion({
    profile: base.profile,
    description: baseSuggestionDescription(base),
    distance: base.reasonable ? null : Number(base.thickness),
  });
  const suggested = singleSuggestedOperation(data, "base");
  const operation = {
    ...suggested,
    type: "extrude",
    id: "base",
    plane: "XY",
    profile: base.profile,
  };

  if (!base.reasonable) {
    operation.distance = Number(base.thickness);
  }

  return operation;
}

async function resolveFeatureOperation({
  baseOperation,
  targetOperation,
  feature,
  featureNumber,
  requestFeatureSuggestion,
}) {
  const instances = expandFeatureInstances(feature);
  const exactOperation = buildFeatureOperation(feature, featureNumber, instances);
  const needsSuggestion = !isEdgeTreatment(feature)
    && (feature.reasonable || feature.profile === "polyline");

  if (!needsSuggestion) {
    return exactOperation;
  }

  const data = await requestFeatureSuggestion({
    operationType: feature.operation,
    target: feature.target,
    profile: feature.profile,
    description: featureSuggestionDescription(feature, targetOperation, baseOperation),
  });
  const suggested = singleSuggestedOperation(data, `feature ${featureNumber}`);
  const operation = { ...exactOperation };

  for (const field of PROFILE_DIMENSION_FIELDS[feature.profile] ?? []) {
    if (feature.reasonable || field === "points") {
      operation[field] = suggested[field];
    }
  }

  return operation;
}

function singleSuggestedOperation(data, label) {
  if (data?.status !== "success") {
    throw new Error(data?.message || `Could not suggest ${label} geometry.`);
  }

  const operations = data?.model_data?.operations;
  if (!Array.isArray(operations) || operations.length !== 1) {
    throw new Error(`The ${label} suggestion must contain exactly one operation.`);
  }

  return operations[0];
}

function baseSuggestionDescription(base) {
  if (base.profile === "polyline") {
    return base.polylineDescription || "Create a simple closed custom base profile.";
  }

  return `Choose practical dimensions for one simple ${base.profile} base only.`;
}

function featureSuggestionDescription(feature, targetOperation, baseOperation) {
  const targetContext = compactOperationContext(targetOperation ?? baseOperation);
  if (feature.profile === "polyline") {
    const requestedShape = feature.polylineDescription || "a simple closed custom feature";
    return `${requestedShape}. Keep only this one profile practical for ${targetContext}.`;
  }

  return (
    `Choose practical ${feature.profile} profile dimensions for one feature on ${targetContext}. `
    + "Do not add any other features."
  );
}

function parentOperationPromise(target, baseOperation, featureOperationPromises) {
  const [ownerId] = String(target).split(".");
  if (ownerId === "base") {
    return Promise.resolve(baseOperation);
  }

  const match = ownerId.match(/^feature_(\d+)$/);
  const parentIndex = match ? Number(match[1]) - 1 : -1;
  return featureOperationPromises[parentIndex] ?? Promise.resolve(baseOperation);
}

function compactOperationContext(operation) {
  if (operation.profile === "rectangle") {
    return `a ${operation.width} mm by ${operation.height} mm rectangular target face`;
  }
  if (operation.profile === "circle") {
    return `a ${operation.diameter} mm diameter circular target face`;
  }
  if (operation.profile === "polygon") {
    return `a ${operation.diameter} mm diameter polygon target face`;
  }
  return "the selected target face";
}
