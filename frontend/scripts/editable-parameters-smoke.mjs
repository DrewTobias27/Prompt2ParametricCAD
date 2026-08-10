import assert from "node:assert/strict";

import {
  editModelParameters,
  getEditableModel,
} from "../src/api.js";
import {
  collectParameterUpdates,
  createEditableDraft,
  editableParameterGroups,
  parameterInputLimits,
} from "../src/editableParameters.js";

const modelData = {
  operations: [
    {
      type: "extrude",
      id: "base",
      plane: "XY",
      profile: "rectangle",
      width: 80,
      height: 50,
      distance: 8,
    },
  ],
};
const editableModel = {
  features: [
    {
      id: "base",
      operation_type: "extrude",
      parameters: [
        {
          id: "base.sketch.width",
          name: "Width",
          role: "sketch_dimension",
          value_type: "length",
          value: 80,
          unit: "mm",
        },
        {
          id: "base.reference.axis_start.x",
          name: "Axis start X",
          role: "reference_geometry",
          value_type: "coordinate",
          value: 0,
          unit: "mm",
        },
      ],
    },
  ],
};

const coreGroups = editableParameterGroups(editableModel);
assert.equal(coreGroups.length, 1);
assert.deepEqual(
  coreGroups[0].parameters.map((parameter) => parameter.id),
  ["base.sketch.width"],
);
assert.equal(editableParameterGroups(editableModel, true)[0].parameters.length, 2);

const draft = createEditableDraft(editableModel);
assert.deepEqual(draft, {
  "base.sketch.width": 80,
  "base.reference.axis_start.x": 0,
});
draft["base.sketch.width"] = 100;
assert.deepEqual(collectParameterUpdates(editableModel, draft), {
  "base.sketch.width": 100,
});
assert.deepEqual(parameterInputLimits(coreGroups[0].parameters[0]), {
  min: 0.001,
  step: "any",
});

const requests = [];
globalThis.fetch = async (url, options) => {
  requests.push({ url, options });
  return {
    ok: true,
    json: async () => ({ status: "success", editable_model: editableModel }),
  };
};

await getEditableModel(modelData);
await editModelParameters(
  modelData,
  { "base.sketch.width": 100 },
  "edited plate",
);

assert.equal(requests[0].url, "/editable-model");
assert.deepEqual(JSON.parse(requests[0].options.body), {
  model_data: modelData,
});
assert.equal(requests[1].url, "/edit-parameters");
assert.deepEqual(JSON.parse(requests[1].options.body), {
  model_data: modelData,
  updates: { "base.sketch.width": 100 },
  filename_hint: "edited plate",
});

console.log("PASS editable parameter UI contract");
