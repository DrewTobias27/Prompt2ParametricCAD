import { reviewGeneratedModel } from "../src/generatedModelReview.js";

const validModel = {
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
    {
      type: "add_extrude",
      id: "feature_1",
      target: "base.top",
      profile: "circle",
      positions: [[0, 0]],
      diameter: 20,
      distance: 8,
    },
    {
      type: "chamfer",
      id: "feature_2",
      target: "feature_1.top_outer_edges",
      distance: 1,
    },
  ],
};

const brokenModel = {
  operations: [
    {
      type: "cut",
      target: "base.top",
      profile: "circle",
      diameter: 10,
      depth: "through",
    },
    {
      type: "add_extrude",
      id: "feature_1",
      target: "feature_9.top",
      profile: "rectangle",
      positions: [],
      width: 20,
      height: -5,
      distance: 0,
    },
    {
      type: "fillet",
      id: "feature_2",
      target: "base.top",
      radius: "large",
    },
  ],
};

printReview("valid model", validModel);
printReview("broken model", brokenModel);

function printReview(label, modelData) {
  console.log(`\n${label.toUpperCase()}`);
  for (const item of reviewGeneratedModel(modelData)) {
    const operationText = item.operationNumber ? ` operation ${item.operationNumber}` : "";
    console.log(`- [${item.severity}]${operationText} ${item.title}`);
    console.log(`  ${item.message}`);
    if (item.suggestion) {
      console.log(`  Suggested fix: ${item.suggestion}`);
    }
  }
}
