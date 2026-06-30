export function buildManualModelData({ base, features }) {
  const operations = [buildBaseOperation(base)];

  for (const [index, feature] of features.entries()) {
    operations.push(buildFeatureOperation(feature, index + 1));
  }

  return { operations };
}

function numberValue(value) {
  return Number(value);
}

function buildBaseOperation(base) {
  const common = {
    type: "extrude",
    id: "base",
    plane: "XY",
    profile: base.profile,
    distance: numberValue(base.thickness),
  };

  if (base.profile === "rectangle") {
    return {
      ...common,
      width: numberValue(base.width),
      height: numberValue(base.height),
    };
  }

  if (base.profile === "circle") {
    return {
      ...common,
      diameter: numberValue(base.diameter),
    };
  }

  return {
    ...common,
    profile: "polygon",
    diameter: numberValue(base.diameter),
    sides: numberValue(base.sides),
  };
}

function buildFeatureOperation(feature, featureNumber) {
  const operation = {
    type: feature.operation,
    target: feature.target,
    profile: feature.profile,
    positions: [[numberValue(feature.x), numberValue(feature.y)]],
  };

  if (feature.operation === "add_extrude") {
    operation.id = `feature_${featureNumber}`;
    operation.distance = numberValue(feature.amount);
  } else {
    operation.depth = feature.depthMode === "through" ? "through" : numberValue(feature.amount);
  }

  if (feature.profile === "rectangle") {
    operation.width = numberValue(feature.width);
    operation.height = numberValue(feature.height);
  } else {
    operation.diameter = numberValue(feature.diameter);
  }

  return operation;
}
