const BASE_OPERATION_TYPES = new Set(["extrude", "revolve"]);
const FEATURE_OPERATION_TYPES = new Set([
  "add_extrude",
  "cut",
  "add_revolve",
  "cut_revolve",
  "chamfer",
  "fillet",
]);
const PROFILE_DIMENSIONS = {
  rectangle: ["width", "height"],
  circle: ["diameter"],
  polygon: ["diameter", "sides"],
  polyline: ["points"],
  sketch: ["start", "segments"],
};
const EDGE_OPERATIONS = new Set(["chamfer", "fillet"]);

export function reviewGeneratedModel(modelData) {
  const operations = Array.isArray(modelData?.operations) ? modelData.operations : [];
  const reviewItems = [];
  const knownFeatureIds = new Set(["base"]);
  const knownTargets = new Set([
    "base.top",
    "base.bottom",
    "base.front",
    "base.back",
    "base.left",
    "base.right",
    "base.top_outer_edges",
    "base.bottom_outer_edges",
    "base.vertical_edges",
    "base.all_edges",
  ]);

  if (!modelData) {
    return [];
  }

  if (operations.length === 0) {
    return [
      reviewItem({
        severity: "error",
        title: "No CAD operations found",
        message: "The API response did not include an operations list, so there is no build plan to validate.",
        suggestion: "Regenerate the model and require an operations array with a base operation first.",
      }),
    ];
  }

  const baseOperation = operations[0];
  if (!BASE_OPERATION_TYPES.has(baseOperation.type)) {
    reviewItems.push(reviewItem({
      severity: "error",
      title: "First operation is not a base feature",
      message: `Operation 1 is '${baseOperation.type}', but the first operation should create the root solid.`,
      suggestion: "Start the model with an extrude or revolve operation that creates the base body.",
      operationNumber: 1,
    }));
  }

  reviewOperationDimensions(baseOperation, 1, reviewItems);
  registerOperationReferences(baseOperation, 1, knownFeatureIds, knownTargets);

  operations.slice(1).forEach((operation, index) => {
    const operationNumber = index + 2;
    if (!FEATURE_OPERATION_TYPES.has(operation.type)) {
      reviewItems.push(reviewItem({
        severity: "error",
        title: `Operation ${operationNumber} uses an unsupported feature type`,
        message: `'${operation.type}' is not one of the supported generated feature operations.`,
        suggestion: "Use add_extrude, cut, add_revolve, cut_revolve, chamfer, or fillet.",
        operationNumber,
      }));
    }

    reviewTarget(operation, operationNumber, knownFeatureIds, knownTargets, reviewItems);
    reviewOperationDimensions(operation, operationNumber, reviewItems);
    reviewPositions(operation, operationNumber, reviewItems);
    registerOperationReferences(operation, operationNumber, knownFeatureIds, knownTargets);
  });

  if (reviewItems.length === 0) {
    return [
      reviewItem({
        severity: "success",
        title: "Generated model structure looks valid",
        message: "The API output has a base operation, valid build order, recognizable targets, and the required basic dimensions.",
      }),
    ];
  }

  return reviewItems;
}

function reviewTarget(operation, operationNumber, knownFeatureIds, knownTargets, reviewItems) {
  if (!requiresTarget(operation)) {
    return;
  }

  if (!operation.target) {
    reviewItems.push(reviewItem({
      severity: "error",
      title: `Operation ${operationNumber} is missing a target`,
      message: `${operation.type} needs a face or edge-group target so it knows where to attach.`,
      suggestion: EDGE_OPERATIONS.has(operation.type)
        ? "Use an edge-group target like base.top_outer_edges or feature_1.vertical_edges."
        : "Use a face target like base.top or feature_1.front.",
      operationNumber,
    }));
    return;
  }

  const targetOwner = String(operation.target).split(".")[0];
  if (!knownFeatureIds.has(targetOwner)) {
    reviewItems.push(reviewItem({
      severity: "error",
      title: `Operation ${operationNumber} targets a future or missing feature`,
      message: `${operation.target} is not available before operation ${operationNumber} runs.`,
      suggestion: "Move the parent feature earlier in the operations list or target an already-created feature.",
      operationNumber,
    }));
    return;
  }

  if (!knownTargets.has(operation.target)) {
    reviewItems.push(reviewItem({
      severity: "warning",
      title: `Operation ${operationNumber} targets an unknown reference`,
      message: `${operation.target} is not in the known reference set inferred from earlier operations.`,
      suggestion: "Use a registered face or edge-group target, or add reference metadata if this is a valid advanced target.",
      operationNumber,
    }));
  }

  const targetLooksLikeEdge = /edges|edge/.test(operation.target);
  if (EDGE_OPERATIONS.has(operation.type) && !targetLooksLikeEdge) {
    reviewItems.push(reviewItem({
      severity: "warning",
      title: `Operation ${operationNumber} may need an edge target`,
      message: `${operation.type} usually expects an edge group, but it targets ${operation.target}.`,
      suggestion: "Use a target like base.top_outer_edges or feature_1.vertical_edges.",
      operationNumber,
    }));
  }

  if (!EDGE_OPERATIONS.has(operation.type) && targetLooksLikeEdge) {
    reviewItems.push(reviewItem({
      severity: "warning",
      title: `Operation ${operationNumber} may need a face target`,
      message: `${operation.type} usually starts from a face, but it targets edge group ${operation.target}.`,
      suggestion: "Use a target like base.top, base.front, or feature_1.top.",
      operationNumber,
    }));
  }
}

function reviewOperationDimensions(operation, operationNumber, reviewItems) {
  if (operation.type === "extrude" || operation.type === "add_extrude") {
    reviewPositiveNumber(operation.distance, "distance", operationNumber, reviewItems);
  }

  if (operation.type === "revolve" || operation.type === "add_revolve" || operation.type === "cut_revolve") {
    reviewPositiveNumber(operation.angle ?? 360, "angle", operationNumber, reviewItems);
    if (!Array.isArray(operation.axis_start) || !Array.isArray(operation.axis_end)) {
      reviewItems.push(reviewItem({
        severity: "error",
        title: `Operation ${operationNumber} is missing a revolve axis`,
        message: "Revolved features need axis_start and axis_end points.",
        suggestion: "Add axis_start and axis_end as two different 2D points in the sketch plane.",
        operationNumber,
      }));
    }
  }

  if (operation.type === "cut" && operation.depth !== "through") {
    reviewPositiveNumber(operation.depth, "depth", operationNumber, reviewItems);
  }

  if (operation.type === "chamfer") {
    reviewPositiveNumber(operation.distance, "distance", operationNumber, reviewItems);
  }

  if (operation.type === "fillet") {
    reviewPositiveNumber(operation.radius, "radius", operationNumber, reviewItems);
  }

  const requiredFields = PROFILE_DIMENSIONS[operation.profile] ?? [];
  for (const field of requiredFields) {
    if (Array.isArray(operation[field])) {
      if (operation[field].length === 0) {
        reviewItems.push(missingFieldItem(operationNumber, field));
      }
    } else if (field === "segments") {
      if (!Array.isArray(operation.segments) || operation.segments.length === 0) {
        reviewItems.push(missingFieldItem(operationNumber, field));
      }
    } else if (operation[field] === undefined || operation[field] === null || operation[field] === "") {
      reviewItems.push(missingFieldItem(operationNumber, field));
    } else if (field !== "points") {
      reviewPositiveNumber(operation[field], field, operationNumber, reviewItems);
    }
  }
}

function reviewPositions(operation, operationNumber, reviewItems) {
  if (!["add_extrude", "cut"].includes(operation.type)) {
    return;
  }

  if (!Array.isArray(operation.positions) || operation.positions.length === 0) {
    reviewItems.push(reviewItem({
      severity: "warning",
      title: `Operation ${operationNumber} has no explicit position`,
      message: `${operation.type} should usually include at least one sketch position on the target face.`,
      suggestion: "Add positions like [[0, 0]] for centered features or multiple points for patterns.",
      operationNumber,
    }));
    return;
  }

  for (const [positionIndex, position] of operation.positions.entries()) {
    if (!Array.isArray(position) || position.length !== 2 || position.some((value) => !Number.isFinite(Number(value)))) {
      reviewItems.push(reviewItem({
        severity: "error",
        title: `Operation ${operationNumber} has an invalid position`,
        message: `Position ${positionIndex + 1} should be a two-number [x, y] pair.`,
        suggestion: "Use positions like [[0, 0], [20, 10]].",
        operationNumber,
      }));
    }
  }
}

function registerOperationReferences(operation, operationNumber, knownFeatureIds, knownTargets) {
  if (!operation.id) {
    return;
  }

  knownFeatureIds.add(operation.id);
  knownTargets.add(`${operation.id}.top`);
  knownTargets.add(`${operation.id}.bottom`);
  knownTargets.add(`${operation.id}.top_outer_edges`);
  knownTargets.add(`${operation.id}.vertical_edges`);

  if (operation.profile === "rectangle") {
    knownTargets.add(`${operation.id}.front`);
    knownTargets.add(`${operation.id}.back`);
    knownTargets.add(`${operation.id}.left`);
    knownTargets.add(`${operation.id}.right`);
  }

  if (operation.type === "revolve" || operation.type === "add_revolve") {
    knownTargets.add(`${operation.id}.axis`);
    knownTargets.add(`${operation.id}.outer_surface`);
    knownTargets.add(`${operation.id}.start_face`);
    knownTargets.add(`${operation.id}.end_face`);
    knownTargets.add(`${operation.id}.end_edges`);
  }

  if (!operation.id.startsWith("feature_") && operationNumber > 1) {
    knownFeatureIds.add(`feature_${operationNumber - 1}`);
  }
}

function reviewPositiveNumber(value, field, operationNumber, reviewItems) {
  if (!Number.isFinite(Number(value)) || Number(value) <= 0) {
    reviewItems.push(reviewItem({
      severity: "error",
      title: `Operation ${operationNumber} has invalid ${field}`,
      message: `${field} should be a positive number, but received ${JSON.stringify(value)}.`,
      suggestion: `Set ${field} to a practical positive dimension.`,
      operationNumber,
    }));
  }
}

function missingFieldItem(operationNumber, field) {
  return reviewItem({
    severity: "error",
    title: `Operation ${operationNumber} is missing ${field}`,
    message: `The selected profile requires ${field}.`,
    suggestion: `Add ${field} to operation ${operationNumber}.`,
    operationNumber,
  });
}

function requiresTarget(operation) {
  return operation.type !== "extrude" && operation.type !== "revolve";
}

function reviewItem({
  severity,
  title,
  message,
  suggestion = "",
  operationNumber = null,
}) {
  return {
    severity,
    title,
    message,
    suggestion,
    operationNumber,
  };
}
