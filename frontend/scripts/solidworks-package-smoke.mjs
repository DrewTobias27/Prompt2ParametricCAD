import assert from "node:assert/strict";

import { createSolidWorksPackage } from "../src/api.js";
import { formatSolidWorksDownloadStatus } from "../src/solidWorksDownload.js";

const requests = [];
globalThis.fetch = async (url, options) => {
  requests.push({ url, options });
  const responseHeaders = {
    "content-disposition": 'attachment; filename="demo-solidworks.zip"',
    "x-prompt2cad-numeric-parameters": "15",
    "x-prompt2cad-named-bindings": "9",
    "x-prompt2cad-relation-controls": "2",
    "x-prompt2cad-derived-geometry": "3",
    "x-prompt2cad-unsupported-parameters": "1",
    "x-prompt2cad-control-coverage": "0.7333333333",
  };
  return {
    ok: true,
    headers: {
      get: (name) => responseHeaders[name.toLowerCase()] ?? null,
    },
    blob: async () => new Blob(["zip-content"], { type: "application/zip" }),
  };
};

const modelData = {
  operations: [
    {
      type: "extrude",
      id: "base",
      plane: "XY",
      profile: "rectangle",
      width: 80,
      height: 50,
      distance: 6,
    },
  ],
};

const download = await createSolidWorksPackage(modelData, "demo model");

assert.equal(download.filename, "demo-solidworks.zip");
assert.equal(download.blob.type, "application/zip");
assert.deepEqual(download.editability, {
  numericParameterCount: 15,
  namedBindingCount: 9,
  relationControlledCount: 2,
  derivedGeometryCount: 3,
  unsupportedCount: 1,
  controlCoverageRatio: 0.7333333333,
});
assert.equal(requests.length, 1);
assert.equal(requests[0].url, "/solidworks-package");
assert.deepEqual(JSON.parse(requests[0].options.body), {
  model_data: modelData,
  filename_hint: "demo model",
});
assert.equal(
  formatSolidWorksDownloadStatus(download.editability),
  "Package downloaded. 11 of 15 source values have automated native controls; 3 are retained as derived native reference geometry; 1 requires manual SolidWorks editing. Extract it on a Windows computer with SolidWorks.",
);
assert.equal(
  formatSolidWorksDownloadStatus({
    numericParameterCount: 11,
    namedBindingCount: 9,
    relationControlledCount: 2,
    derivedGeometryCount: 0,
    unsupportedCount: 0,
  }),
  "Package downloaded. 11 of 11 source values have automated native controls. Extract it on a Windows computer with SolidWorks.",
);
assert.equal(
  formatSolidWorksDownloadStatus(null),
  "Package downloaded. Extract it on a Windows computer with SolidWorks.",
);

console.log("PASS SolidWorks package request contract");
