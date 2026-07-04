import { createFeature, defaultBase } from "../src/modelBuilders.js";
import { buildPreviewModel } from "../src/previewEngine.js";

function feature(overrides) {
  return {
    ...createFeature(1),
    ...overrides,
    localId: overrides.localId ?? crypto.randomUUID(),
    reasonable: false,
    polylineDescription: "",
  };
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

function recordsFor(model, viewName, featureNumber = null) {
  const records = model.views[viewName].features;
  if (featureNumber === null) {
    return records;
  }
  return records.filter((record) => record.featureNumber === featureNumber);
}

function testTopBossProjectsToFrontAndRight() {
  const model = buildPreviewModel({
    base: {
      ...defaultBase,
      profile: "rectangle",
      width: 80,
      height: 50,
      thickness: 8,
    },
    features: [
      feature({
        localId: "boss",
        operation: "add_extrude",
        target: "base.top",
        profile: "rectangle",
        width: 20,
        height: 12,
        amount: 6,
      }),
    ],
  });

  assert(recordsFor(model, "top", 1).some((record) => record.isPrimary), "top boss should have a primary top-view record");
  assert(recordsFor(model, "front", 1).some((record) => !record.isPrimary), "top boss should project into front view");
  assert(recordsFor(model, "right", 1).some((record) => !record.isPrimary), "top boss should project into right view");
}

function testCircularPatternCreatesRepeatedHoleRecords() {
  const model = buildPreviewModel({
    base: {
      ...defaultBase,
      profile: "circle",
      diameter: 90,
      thickness: 10,
    },
    features: [
      feature({
        localId: "bolt_circle",
        operation: "cut",
        target: "base.top",
        profile: "circle",
        pattern: "circular",
        x: 30,
        y: 0,
        copies: 6,
        diameter: 6,
        depthMode: "through",
      }),
    ],
  });

  const topHoles = recordsFor(model, "top", 1).filter((record) => record.isPrimary);
  assert(topHoles.length === 6, `expected 6 top-view hole records, found ${topHoles.length}`);
  assert(topHoles.every((record) => record.profile === "circle"), "all repeated hole records should remain circular");
}

function testFeatureLinkedWarningsIncludeSuggestions() {
  const model = buildPreviewModel({
    base: {
      ...defaultBase,
      profile: "rectangle",
      width: 40,
      height: 30,
      thickness: 6,
    },
    features: [
      feature({
        localId: "bad_hole",
        operation: "cut",
        target: "base.top",
        profile: "circle",
        x: 20,
        y: 0,
        diameter: 12,
        depthMode: "through",
      }),
    ],
  });

  const linkedWarnings = model.warnings.filter((warning) => warning.featureNumbers?.includes(1));
  assert(linkedWarnings.length > 0, "expected at least one warning linked to feature 1");
  assert(linkedWarnings.some((warning) => warning.suggestion), "linked warnings should include suggested fixes");
}

const tests = [
  testTopBossProjectsToFrontAndRight,
  testCircularPatternCreatesRepeatedHoleRecords,
  testFeatureLinkedWarningsIncludeSuggestions,
];

for (const test of tests) {
  test();
  console.log(`PASS ${test.name}`);
}
