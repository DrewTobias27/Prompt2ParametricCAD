export function formatSolidWorksDownloadStatus(editability) {
  const {
    numericParameterCount,
    namedBindingCount,
    relationControlledCount,
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
  const coverageSummary = unsupportedCount === 0
    ? `${controlledCount} of ${numericParameterCount} editable values have native controls.`
    : `${controlledCount} of ${numericParameterCount} editable values have native controls; ${unsupportedCount} ${unsupportedCount === 1 ? "value requires" : "values require"} manual SolidWorks editing.`;

  return `Package downloaded. ${coverageSummary} Extract it on a Windows computer with SolidWorks.`;
}
