import { defaultBase } from "./modelBuilders.js";
import { DIAMETER_SYMBOL, MULTIPLY_SYMBOL } from "./symbols.js";

export function modelDataToTreeView(modelData) {
  const operations = Array.isArray(modelData?.operations) ? modelData.operations : [];
  if (operations.length === 0) {
    return null;
  }

  return {
    base: baseFromOperation(operations[0]),
    features: operations.slice(1).map((operation, index) => featureFromOperation(operation, index + 1)),
  };
}

function baseFromOperation(operation) {
  if (operation.type === "extrude") {
    return {
      ...defaultBase,
      profile: operation.profile ?? "rectangle",
      width: operation.width ?? defaultBase.width,
      height: operation.height ?? defaultBase.height,
      diameter: operation.diameter ?? defaultBase.diameter,
      sides: operation.sides ?? defaultBase.sides,
      thickness: operation.distance ?? defaultBase.thickness,
      summary: baseSummary(operation),
    };
  }

  if (operation.type === "revolve") {
    return {
      ...defaultBase,
      profile: "revolve",
      thickness: operation.angle ?? 360,
      summary: baseSummary(operation),
    };
  }

  return {
    ...defaultBase,
    profile: operation.profile ?? "unknown",
    summary: baseSummary(operation),
  };
}

function featureFromOperation(operation, featureNumber) {
  const id = operation.id ?? `feature_${featureNumber}`;
  const common = {
    localId: `${id}-${featureNumber}`,
    operation: operation.type,
    target: operation.target ?? "base.top",
    profile: operation.profile ?? "rectangle",
    width: operation.width ?? "",
    height: operation.height ?? "",
    diameter: operation.diameter ?? "",
    sides: operation.sides ?? "",
    amount: operation.distance ?? operation.depth ?? operation.radius ?? "",
    depthMode: operation.depth === "through" ? "through" : "blind",
    pattern: operation.positions?.length > 1 ? "multi-instance" : "single",
    summary: featureSummary(operation),
  };

  if (operation.type === "chamfer") {
    return {
      ...common,
      operation: "chamfer",
      amount: operation.distance ?? "",
    };
  }

  if (operation.type === "fillet") {
    return {
      ...common,
      operation: "fillet",
      amount: operation.radius ?? "",
    };
  }

  return common;
}

function baseSummary(operation) {
  if (operation.type === "revolve") {
    return `Revolved ${operation.profile ?? "profile"} ${operation.angle ?? 360}${DEGREE_SYMBOL}`;
  }

  if (operation.profile === "rectangle") {
    return `Rectangle ${operation.width ?? "?"} ${MULTIPLY_SYMBOL} ${operation.height ?? "?"} ${MULTIPLY_SYMBOL} ${operation.distance ?? "?"}`;
  }

  if (operation.profile === "circle") {
    return `Circle ${DIAMETER_SYMBOL}${operation.diameter ?? "?"} ${MULTIPLY_SYMBOL} ${operation.distance ?? "?"}`;
  }

  if (operation.profile === "polygon") {
    return `${operation.sides ?? "?"}-sided polygon ${DIAMETER_SYMBOL}${operation.diameter ?? "?"} ${MULTIPLY_SYMBOL} ${operation.distance ?? "?"}`;
  }

  return `${titleCase(operation.type ?? "base")} ${operation.profile ?? "profile"}`;
}

function featureSummary(operation) {
  const operationLabel = operationLabelForType(operation.type);

  if (operation.type === "chamfer") {
    return `Chamfer - ${operation.distance ?? "?"} distance`;
  }

  if (operation.type === "fillet") {
    return `Fillet - ${operation.radius ?? "?"} radius`;
  }

  if (operation.type === "add_revolve" || operation.type === "cut_revolve") {
    return `${operationLabel} - ${operation.profile ?? "profile"} - ${operation.angle ?? 360}${DEGREE_SYMBOL}`;
  }

  return [
    operationLabel,
    shapeSummary(operation),
    depthSummary(operation),
    instanceSummary(operation),
  ].filter(Boolean).join(" - ");
}

function operationLabelForType(type) {
  if (type === "add_extrude") {
    return "Extrusion";
  }
  if (type === "cut") {
    return "Cut";
  }
  if (type === "add_revolve") {
    return "Revolved addition";
  }
  if (type === "cut_revolve") {
    return "Revolved cut";
  }

  return titleCase(type ?? "feature");
}

function shapeSummary(operation) {
  if (operation.profile === "rectangle") {
    return `${operation.width ?? "?"} ${MULTIPLY_SYMBOL} ${operation.height ?? "?"} rectangle`;
  }

  if (operation.profile === "circle") {
    return `${DIAMETER_SYMBOL}${operation.diameter ?? "?"} circle`;
  }

  if (operation.profile === "polygon") {
    return `${operation.sides ?? "?"}-sided polygon ${DIAMETER_SYMBOL}${operation.diameter ?? "?"}`;
  }

  return operation.profile ?? "profile";
}

function depthSummary(operation) {
  if (operation.type === "cut") {
    return operation.depth === "through" ? "through" : `${operation.depth ?? "?"} deep`;
  }

  if (operation.type === "add_extrude") {
    return `${operation.distance ?? "?"} tall`;
  }

  return "";
}

function instanceSummary(operation) {
  const count = Array.isArray(operation.positions) ? operation.positions.length : 0;
  if (count <= 1) {
    return "";
  }

  return `${count} instances`;
}

function titleCase(value) {
  return String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

const DEGREE_SYMBOL = "\u00B0";
