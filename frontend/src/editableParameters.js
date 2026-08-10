const CORE_PARAMETER_ROLES = new Set([
  "sketch_dimension",
  "feature_control",
  "placement",
]);

export function editableParameterGroups(editableModel, includeAdvanced = false) {
  if (!editableModel?.features) {
    return [];
  }

  return editableModel.features
    .map((feature) => ({
      id: feature.id,
      operationType: feature.operation_type,
      parameters: (feature.parameters || []).filter((parameter) => (
        includeAdvanced || CORE_PARAMETER_ROLES.has(parameter.role)
      )),
    }))
    .filter((feature) => feature.parameters.length > 0);
}

export function createEditableDraft(editableModel) {
  return Object.fromEntries(
    editableParameterGroups(editableModel, true)
      .flatMap((feature) => feature.parameters)
      .map((parameter) => [parameter.id, parameter.value]),
  );
}

export function collectParameterUpdates(editableModel, draft) {
  const updates = {};
  for (const feature of editableParameterGroups(editableModel, true)) {
    for (const parameter of feature.parameters) {
      if (
        Object.prototype.hasOwnProperty.call(draft, parameter.id)
        && !Object.is(draft[parameter.id], parameter.value)
      ) {
        updates[parameter.id] = draft[parameter.id];
      }
    }
  }

  return updates;
}

export function parameterInputLimits(parameter) {
  if (parameter.value_type === "count") {
    return { min: 3, step: 1 };
  }
  if (["length", "angle"].includes(parameter.value_type)) {
    return { min: 0.001, step: "any" };
  }
  return { step: "any" };
}
