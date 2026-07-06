import { createFeature, defaultBase } from "../src/modelBuilders.js";
import { MANUAL_PRESETS } from "../src/manualPresets.js";
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

function testFrontFaceCutProjectsToOtherViews() {
  const model = buildPreviewModel({
    base: {
      ...defaultBase,
      profile: "rectangle",
      width: 80,
      height: 50,
      thickness: 12,
    },
    features: [
      feature({
        localId: "front_hole",
        operation: "cut",
        target: "base.front",
        profile: "circle",
        diameter: 8,
        depthMode: "through",
      }),
    ],
  });

  assert(recordsFor(model, "front", 1).some((record) => record.isPrimary), "front-face cut should have a primary front-view record");
  assert(recordsFor(model, "top", 1).some((record) => !record.isPrimary), "front-face cut should project into top view");
  assert(recordsFor(model, "right", 1).some((record) => !record.isPrimary), "front-face cut should project into right view");
}

function testRightFaceRectangularCutProjectsToOtherViews() {
  const model = buildPreviewModel({
    base: {
      ...defaultBase,
      profile: "rectangle",
      width: 80,
      height: 50,
      thickness: 12,
    },
    features: [
      feature({
        localId: "right_slot",
        operation: "cut",
        target: "base.right",
        profile: "rectangle",
        width: 18,
        height: 6,
        amount: 4,
        depthMode: "blind",
      }),
    ],
  });

  assert(recordsFor(model, "right", 1).some((record) => record.isPrimary), "right-face cut should have a primary right-view record");
  assert(recordsFor(model, "top", 1).some((record) => !record.isPrimary), "right-face cut should project into top view");
  assert(recordsFor(model, "front", 1).some((record) => !record.isPrimary), "right-face cut should project into front view");
}

function testCutCanTargetPriorFeatureTopFace() {
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
        width: 24,
        height: 18,
        amount: 6,
      }),
      feature({
        localId: "boss_hole",
        operation: "cut",
        target: "feature_1.top",
        profile: "circle",
        diameter: 6,
        depthMode: "through",
      }),
    ],
  });

  assert(recordsFor(model, "top", 2).some((record) => record.isPrimary), "cut on feature_1.top should have a primary top-view record");
  assert(recordsFor(model, "front", 2).some((record) => !record.isPrimary), "cut on feature_1.top should project into front view");
  assert(recordsFor(model, "right", 2).some((record) => !record.isPrimary), "cut on feature_1.top should project into right view");
}

function testMirroredFeatureCreatesFourPrimaryRecords() {
  const model = buildPreviewModel({
    base: {
      ...defaultBase,
      profile: "rectangle",
      width: 90,
      height: 60,
      thickness: 8,
    },
    features: [
      feature({
        localId: "mirrored_posts",
        operation: "add_extrude",
        target: "base.top",
        profile: "circle",
        x: 25,
        y: 15,
        diameter: 8,
        amount: 6,
        mirrorX: true,
        mirrorY: true,
      }),
    ],
  });

  const topPosts = recordsFor(model, "top", 1).filter((record) => record.isPrimary);
  assert(topPosts.length === 4, `expected 4 mirrored primary records, found ${topPosts.length}`);
}

function testMountingPlatePresetKeepsCornerHolesInsideBase() {
  const preset = MANUAL_PRESETS.find((manualPreset) => manualPreset.id === "mounting_plate");
  assert(preset, "mounting plate preset should exist");

  const model = buildPreviewModel({
    base: {
      ...defaultBase,
      ...preset.base,
      reasonable: false,
      polylineDescription: "",
    },
    features: preset.features.map((featureData, index) => ({
      ...createFeature(index + 1),
      ...featureData,
      localId: featureData.localId ?? `preset_feature_${index + 1}`,
      reasonable: false,
      polylineDescription: "",
    })),
  });

  const topHoles = recordsFor(model, "top", 1).filter((record) => record.isPrimary);
  const linkedWarnings = model.warnings.filter((warning) => warning.featureNumbers?.includes(1));
  assert(topHoles.length === 4, `expected 4 mirrored corner holes, found ${topHoles.length}`);
  assert(linkedWarnings.length === 0, `mounting plate preset should not warn, found ${linkedWarnings.length} warnings`);
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
  testFrontFaceCutProjectsToOtherViews,
  testRightFaceRectangularCutProjectsToOtherViews,
  testCutCanTargetPriorFeatureTopFace,
  testMirroredFeatureCreatesFourPrimaryRecords,
  testMountingPlatePresetKeepsCornerHolesInsideBase,
  testFeatureLinkedWarningsIncludeSuggestions,
];

for (const test of tests) {
  test();
  console.log(`PASS ${test.name}`);
}
