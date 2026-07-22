import { createLocalId } from "./localIds.js";

export const defaultBase = {
  profile: "rectangle",
  width: 80,
  height: 50,
  diameter: 60,
  sides: 6,
  thickness: 6,
  reasonable: false,
  polylineDescription: "",
};

export function createFeature(featureNumber = 1) {
  return {
    localId: createLocalId(),
    operation: "add_extrude",
    target: "base.top",
    edgeSelector: "top_outer_edges",
    profile: "rectangle",
    pattern: "single",
    mirrorX: false,
    mirrorY: false,
    copies: 4,
    width: 20,
    height: 12,
    diameter: 10,
    sides: 6,
    x: 0,
    y: 0,
    amount: 6,
    depthMode: "through",
    reasonable: false,
    polylineDescription: "",
    requestedName: `feature_${featureNumber}`,
  };
}

export function isEdgeTreatment(feature) {
  return feature.operation === "chamfer" || feature.operation === "fillet";
}

export function hasApiAssistedFields({ base, features }) {
  return (
    base.reasonable ||
    base.profile === "polyline" ||
    features.some((feature) => (
      !isEdgeTreatment(feature)
      && (feature.reasonable || feature.profile === "polyline")
    ))
  );
}

export function buildManualModelData({ base, features }) {
  const operations = [buildBaseOperation(base)];

  for (const [index, feature] of features.entries()) {
    const instances = expandFeatureInstances(feature);
    operations.push(buildFeatureOperation(feature, index + 1, instances));
  }

  return { operations };
}

export function buildManualPrompt({ base, features }) {
  const baseDescription = describeBase(base);
  const featureDescriptions = features.map((feature, index) => describeFeature(feature, index + 1));

  return [
    `Create a CAD model with ${baseDescription}.`,
    ...featureDescriptions,
    "Return valid Prompt2ParametricCAD JSON only.",
    "Make every added extrusion physically overlap or touch its target face so the final result is one connected solid.",
    "Use exact dimensions where provided. If reasonable dimensions are requested, choose practical dimensions proportional to the base.",
  ].join(" ");
}

export function buildBaseOperation(base) {
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

export function buildFeatureOperation(feature, featureNumber, instances) {
  if (isEdgeTreatment(feature)) {
    const operation = {
      type: feature.operation,
      id: `feature_${featureNumber}`,
      target: feature.target,
    };

    if (feature.operation === "chamfer") {
      operation.distance = numberValue(feature.amount);
    } else {
      operation.radius = numberValue(feature.amount);
    }

    return operation;
  }

  const operation = {
    type: feature.operation,
    target: feature.target,
    profile: feature.profile,
    positions: instances.map((instance) => [
      roundNumber(instance.x),
      roundNumber(instance.y),
    ]),
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
  } else if (feature.profile === "circle") {
    operation.diameter = numberValue(feature.diameter);
  } else if (feature.profile === "polygon") {
    operation.diameter = numberValue(feature.diameter);
    operation.sides = numberValue(feature.sides);
  }

  return operation;
}

export function expandFeatureInstances(feature) {
  const x = numberValue(feature.x);
  const y = numberValue(feature.y);

  if (feature.pattern === "circular") {
    const copies = Math.max(1, Math.floor(numberValue(feature.copies) || 1));
    const radius = Math.hypot(x, y);
    const startAngle = Math.atan2(y, x);
    return Array.from({ length: copies }, (_, index) => {
      const angle = startAngle + (2 * Math.PI * index) / copies;
      return {
        x: radius * Math.cos(angle),
        y: radius * Math.sin(angle),
      };
    });
  }

  const xValues = feature.mirrorY ? [x, -x] : [x];
  const yValues = feature.mirrorX ? [y, -y] : [y];
  const instances = [];

  for (const instanceX of xValues) {
    for (const instanceY of yValues) {
      if (!instances.some((instance) => instance.x === instanceX && instance.y === instanceY)) {
        instances.push({ x: instanceX, y: instanceY });
      }
    }
  }

  return instances;
}

function describeBase(base) {
  if (base.reasonable) {
    return `a reasonably sized ${base.profile} base`;
  }

  if (base.profile === "polyline") {
    return `a custom closed polyline base shaped like: ${base.polylineDescription || "a simple closed profile"}`;
  }

  if (base.profile === "rectangle") {
    return `an ${base.width} mm by ${base.height} mm rectangular base that is ${base.thickness} mm thick`;
  }

  if (base.profile === "circle") {
    return `a ${base.diameter} mm diameter circular base that is ${base.thickness} mm thick`;
  }

  return `a ${base.sides}-sided polygon base with a ${base.diameter} mm outer diameter that is ${base.thickness} mm thick`;
}

function describeFeature(feature, featureNumber) {
  if (isEdgeTreatment(feature)) {
    const treatmentText = feature.operation === "chamfer" ? "chamfer" : "fillet";
    const dimensionText = feature.operation === "chamfer"
      ? `${feature.amount} mm chamfer distance`
      : `${feature.amount} mm fillet radius`;
    return `Add feature ${featureNumber}: a ${treatmentText} on ${feature.target.replace(".", " ")}, using ${dimensionText}.`;
  }

  const operationText = feature.operation === "cut" ? "cut" : "extrusion";
  const shapeText = describeFeatureShape(feature);
  const targetText = feature.target.replace(".", " ");
  const patternText = describePattern(feature);
  const depthText = feature.operation === "cut"
    ? feature.depthMode === "through" ? "through the target" : `${feature.amount} mm deep`
    : `${feature.amount} mm tall`;

  return `Add feature ${featureNumber}: a ${shapeText} ${operationText} on ${targetText}, positioned at X ${feature.x} mm and Y ${feature.y} mm, ${depthText}${patternText}.`;
}

function describeFeatureShape(feature) {
  if (feature.reasonable) {
    return `reasonably sized ${feature.profile}`;
  }

  if (feature.profile === "polyline") {
    return `custom closed polyline shaped like: ${feature.polylineDescription || "a simple closed feature"}`;
  }

  if (feature.profile === "rectangle") {
    return `${feature.width} mm by ${feature.height} mm rectangular`;
  }

  if (feature.profile === "circle") {
    return `${feature.diameter} mm diameter circular`;
  }

  return `${feature.sides}-sided polygon with a ${feature.diameter} mm outer diameter`;
}

function describePattern(feature) {
  if (feature.pattern === "circular") {
    return `, repeated as ${feature.copies} evenly spaced circular-pattern instances around the origin`;
  }

  const mirrors = [];
  if (feature.mirrorX) {
    mirrors.push("mirrored across the X axis");
  }
  if (feature.mirrorY) {
    mirrors.push("mirrored across the Y axis");
  }

  return mirrors.length > 0 ? `, ${mirrors.join(" and ")}` : "";
}

function numberValue(value) {
  return Number(value) || 0;
}

function roundNumber(value) {
  const rounded = Math.round(value * 1000) / 1000;
  return Object.is(rounded, -0) ? 0 : rounded;
}
