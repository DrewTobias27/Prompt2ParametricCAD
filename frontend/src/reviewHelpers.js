export function featureWarningsByNumber(warnings) {
  const map = new Map();

  for (const warning of warnings) {
    for (const featureNumber of warning.featureNumbers ?? []) {
      if (!map.has(featureNumber)) {
        map.set(featureNumber, []);
      }
      map.get(featureNumber).push(warning);
    }
  }

  for (const [featureNumber, featureWarnings] of map.entries()) {
    map.set(featureNumber, featureWarnings.sort((first, second) => (
      severityRank(second.severity) - severityRank(first.severity)
    )));
  }

  return map;
}

function severityRank(severity) {
  if (severity === "error") {
    return 3;
  }
  if (severity === "warning") {
    return 2;
  }
  if (severity === "info") {
    return 1;
  }
  return 0;
}
