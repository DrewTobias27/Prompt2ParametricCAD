import assert from "node:assert/strict";

import { createSolidWorksPackage } from "../src/api.js";

const requests = [];
globalThis.fetch = async (url, options) => {
  requests.push({ url, options });
  return {
    ok: true,
    headers: {
      get: (name) => name.toLowerCase() === "content-disposition"
        ? 'attachment; filename="demo-solidworks.zip"'
        : null,
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
assert.equal(requests.length, 1);
assert.equal(requests[0].url, "/solidworks-package");
assert.deepEqual(JSON.parse(requests[0].options.body), {
  model_data: modelData,
  filename_hint: "demo model",
});

console.log("PASS SolidWorks package request contract");
