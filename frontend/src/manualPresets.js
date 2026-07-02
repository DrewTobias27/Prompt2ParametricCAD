export const MANUAL_PRESETS = [
  {
    id: "mounting_plate",
    name: "Mounting plate",
    description: "Rectangular plate with four through holes.",
    base: { profile: "rectangle", width: 100, height: 70, thickness: 8 },
    features: [
      { operation: "cut", profile: "circle", pattern: "circular", x: 35, y: 22, copies: 4, diameter: 6, depthMode: "through" },
    ],
  },
  {
    id: "flange",
    name: "Flange",
    description: "Circular base, center boss, and bolt circle.",
    base: { profile: "circle", diameter: 90, thickness: 10 },
    features: [
      { operation: "add_extrude", profile: "circle", target: "base.top", diameter: 32, amount: 12 },
      { operation: "cut", profile: "circle", target: "base.top", pattern: "circular", x: 30, y: 0, copies: 6, diameter: 6, depthMode: "through" },
      { operation: "cut", profile: "circle", target: "feature_1.top", diameter: 12, depthMode: "through" },
    ],
  },
  {
    id: "boss_block",
    name: "Boss block",
    description: "Rectangular block with raised boss and side cut.",
    base: { profile: "rectangle", width: 90, height: 55, thickness: 10 },
    features: [
      { operation: "add_extrude", profile: "rectangle", target: "base.top", width: 28, height: 20, amount: 12 },
      { operation: "cut", profile: "circle", target: "feature_1.top", diameter: 8, depthMode: "through" },
      { operation: "cut", profile: "rectangle", target: "base.right", width: 24, height: 5, amount: 6, depthMode: "blind" },
    ],
  },
];
