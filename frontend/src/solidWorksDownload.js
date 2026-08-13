export function formatSolidWorksDownloadStatus(editability) {
  const {
    numericParameterCount,
    namedBindingCount,
    relationControlledCount,
    derivedGeometryCount,
    unsupportedCount,
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

  const controlledCount = namedBindingCount + relationControlledCount;
  const coverageDetails = [
    `${controlledCount} of ${numericParameterCount} source values have automated native controls`,
  ];
  if (Number.isFinite(derivedGeometryCount) && derivedGeometryCount > 0) {
    coverageDetails.push(
      `${derivedGeometryCount} ${derivedGeometryCount === 1 ? "is" : "are"} retained as derived native reference geometry`,
    );
  }
  if (unsupportedCount > 0) {
    coverageDetails.push(
      `${unsupportedCount} ${unsupportedCount === 1 ? "requires" : "require"} manual SolidWorks editing`,
    );
  }
  const coverageSummary = `${coverageDetails.join("; ")}.`;

  return `Package downloaded. ${coverageSummary} Extract it on a Windows computer with SolidWorks.`;
}
