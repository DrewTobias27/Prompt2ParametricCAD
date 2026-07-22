import assert from "node:assert/strict";

import { resolveManualModelData } from "../src/manualAssistance.js";
import { createFeature, defaultBase } from "../src/modelBuilders.js";

const success = (operation) => ({
  status: "success",
  model_data: { operations: [operation] },
});

await testReasonableBaseStaysOneBase();
await testPolylineBaseKeepsExactThickness();
await testReasonableFeatureKeepsUserPlacementAndDepth();
await testPolylineFeatureKeepsUserPlacementAndDepth();
await testEdgeTreatmentSkipsApiAssistance();
await testChildSuggestionUsesResolvedParentDimensions();

console.log("PASS manual assistance preserves builder intent");

async function testReasonableBaseStaysOneBase() {
  const base = { ...defaultBase, reasonable: true };
  let requestPayload = null;
  const result = await resolveManualModelData(
    { base, features: [] },
    {
      requestBaseSuggestion: async (payload) => {
        requestPayload = payload;
        return success({
          type: "extrude",
          id: "base",
          plane: "XY",
          profile: "rectangle",
          width: 100,
          height: 60,
          distance: 8,
        });
      },
    },
  );

  assert.equal(result.operations.length, 1);
  assert.equal(result.operations[0].profile, "rectangle");
  assert.equal(requestPayload.distance, null);
}

async function testPolylineBaseKeepsExactThickness() {
  const base = {
    ...defaultBase,
    profile: "polyline",
    thickness: 7,
    polylineDescription: "an L-shaped plate",
  };
  const result = await resolveManualModelData(
    { base, features: [] },
    {
      requestBaseSuggestion: async () => success({
        type: "extrude",
        id: "base",
        plane: "XY",
        profile: "polyline",
        points: [[0, 0], [40, 0], [40, 10], [10, 10], [10, 30], [0, 30]],
        distance: 99,
      }),
    },
  );

  assert.equal(result.operations[0].distance, 7);
  assert.equal(result.operations[0].points.length, 6);
}

async function testReasonableFeatureKeepsUserPlacementAndDepth() {
  const feature = {
    ...createFeature(1),
    profile: "circle",
    reasonable: true,
    pattern: "circular",
    copies: 4,
    x: 20,
    y: 0,
    amount: 5,
  };
  const result = await resolveManualModelData(
    { base: defaultBase, features: [feature] },
    {
      requestFeatureSuggestion: async () => success({
        type: "add_extrude",
        target: "base.top",
        profile: "circle",
        positions: [[999, 999]],
        diameter: 12,
        distance: 99,
      }),
    },
  );
  const operation = result.operations[1];

  assert.equal(operation.diameter, 12);
  assert.equal(operation.distance, 5);
  assert.equal(operation.id, "feature_1");
  assert.deepEqual(operation.positions, [[20, 0], [0, 20], [-20, 0], [0, -20]]);
}

async function testPolylineFeatureKeepsUserPlacementAndDepth() {
  const feature = {
    ...createFeature(1),
    operation: "cut",
    profile: "polyline",
    polylineDescription: "a triangular notch",
    depthMode: "blind",
    amount: 2,
    x: 3,
    y: 4,
  };
  const result = await resolveManualModelData(
    { base: defaultBase, features: [feature] },
    {
      requestFeatureSuggestion: async () => success({
        type: "cut",
        target: "base.top",
        profile: "polyline",
        positions: [[999, 999]],
        points: [[0, 0], [8, 0], [4, 6]],
        depth: 99,
      }),
    },
  );
  const operation = result.operations[1];

  assert.equal(operation.depth, 2);
  assert.deepEqual(operation.positions, [[3, 4]]);
  assert.deepEqual(operation.points, [[0, 0], [8, 0], [4, 6]]);
}

async function testEdgeTreatmentSkipsApiAssistance() {
  const feature = {
    ...createFeature(1),
    operation: "fillet",
    target: "base.vertical_edges",
    amount: 2,
  };
  let requestCount = 0;
  const result = await resolveManualModelData(
    { base: defaultBase, features: [feature] },
    {
      requestFeatureSuggestion: async () => {
        requestCount += 1;
        throw new Error("Edge treatments should not request assistance");
      },
    },
  );

  assert.equal(requestCount, 0);
  assert.equal(result.operations[1].type, "fillet");
  assert.equal(result.operations[1].radius, 2);
}

async function testChildSuggestionUsesResolvedParentDimensions() {
  const parent = {
    ...createFeature(1),
    reasonable: true,
  };
  const child = {
    ...createFeature(2),
    reasonable: true,
    operation: "cut",
    profile: "circle",
    target: "feature_1.top",
  };
  let childDescription = "";

  const result = await resolveManualModelData(
    { base: defaultBase, features: [parent, child] },
    {
      requestFeatureSuggestion: async (request) => {
        if (request.target === "base.top") {
          return success({
            type: "add_extrude",
            target: "base.top",
            profile: "rectangle",
            positions: [[0, 0]],
            width: 30,
            height: 18,
            distance: 6,
          });
        }

        childDescription = request.description;
        return success({
          type: "cut",
          target: "feature_1.top",
          profile: "circle",
          positions: [[0, 0]],
          diameter: 6,
          depth: 4,
        });
      },
    },
  );

  assert.equal(result.operations.length, 3);
  assert.match(childDescription, /30 mm by 18 mm rectangular target face/);
}
