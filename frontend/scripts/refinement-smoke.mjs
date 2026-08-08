import assert from "node:assert/strict";

import { refineGeneratedDesign } from "../src/api.js";

const requests = [];
globalThis.fetch = async (url, options) => {
  requests.push({ url, options });
  return {
    ok: true,
    json: async () => ({ status: "success", revision: 2 }),
  };
};

const designIntent = {
  required_concepts: ["plate"],
  base: { id: "base", profile: "rectangle" },
  features: [],
  edge_treatments: [],
};

const result = await refineGeneratedDesign({
  originalPrompt: "Create a rectangular plate.",
  correction: "Make it thicker.",
  designIntent,
  revision: 1,
});

assert.equal(result.revision, 2);
assert.equal(requests.length, 1);
assert.equal(requests[0].url, "/refine");
assert.deepEqual(JSON.parse(requests[0].options.body), {
  original_prompt: "Create a rectangular plate.",
  correction: "Make it thicker.",
  design_intent: designIntent,
  revision: 1,
});

console.log("PASS refinement request contract");
