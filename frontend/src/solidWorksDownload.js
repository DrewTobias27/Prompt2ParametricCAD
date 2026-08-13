export function formatSolidWorksDownloadStatus(editability) {
  const {
    packageVersion,
    numericParameterCount,
    namedBindingCount,
    relationControlledCount,
    derivedGeometryCount,
    unsupportedCount,
    restrictedCount,
  } = editability || {};
  const hasCoverage = [
    numericParameterCount,
    namedBindingCount,
    relationControlledCount,
    unsupportedCount,
  ].every(Number.isFinite);

  if (!hasCoverage) {
    return "Package downloaded. Extract it on a Windows computer with SolidWorks.";
  }

  const packageLabel = Number.isFinite(packageVersion)
    ? `Package v${packageVersion}`
    : "Package";
  const coverageDetails = [];
  if (namedBindingCount > 0) {
    coverageDetails.push(
      `${namedBindingCount} ${namedBindingCount === 1 ? "has an" : "have"} automated edit ${namedBindingCount === 1 ? "binding" : "bindings"}`,
    );
  }
  if (relationControlledCount > 0) {
    coverageDetails.push(
      `${relationControlledCount} zero ${relationControlledCount === 1 ? "coordinate is" : "coordinates are"} held by sketch relations`,
    );
  }
  if (Number.isFinite(derivedGeometryCount) && derivedGeometryCount > 0) {
    coverageDetails.push(
      `${derivedGeometryCount} ${derivedGeometryCount === 1 ? "is" : "are"} retained as reference geometry`,
    );
  }
  if (unsupportedCount > 0) {
    coverageDetails.push(
      `${unsupportedCount} ${unsupportedCount === 1 ? "requires" : "require"} manual SolidWorks editing`,
    );
  }
  let restrictionSummary = "";
  if (Number.isFinite(restrictedCount) && restrictedCount > 0) {
    restrictionSummary = ` ${restrictedCount} coordinate ${restrictedCount === 1 ? "binding cannot" : "bindings cannot"} cross the sketch origin without regenerating.`;
  }
  const coverageSummary = coverageDetails.length > 0
    ? ` Of ${numericParameterCount} source values: ${coverageDetails.join("; ")}.`
    : "";

  return `${packageLabel} downloaded.${coverageSummary}${restrictionSummary} Extract it on Windows with SolidWorks.`;
}
