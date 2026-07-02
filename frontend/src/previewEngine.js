const REVIEW_EDGE_MARGIN = 3;
const REVIEW_FEATURE_FRACTION_LIMIT = 0.75;
const REVIEW_MIN_FEATURE_SPACING = 2;

export const PREVIEW_WIDTH = 820;
export const PREVIEW_HEIGHT = 500;
export const SMALL_FEATURE_CALLOUT_THRESHOLD = 48;

export function buildPreviewModel({ base, features }) {
  const baseGeometry = baseReviewGeometry(base);
  if (baseGeometry === null) {
    return {
      baseGeometry: null,
      views: emptyViews(),
      warnings: [
        reviewWarning(
          "info",
          "Exact design review is waiting for dimensions",
          "Turn off reasonable dimensions and use rectangle, circle, or polygon base dimensions to enable live boundary checks.",
        ),
      ],
      skippedCount: features.length,
      primaryCount: 0,
    };
  }

  const { records, skippedCount, depthWarnings } = collectExactFeaturePreviewData(baseGeometry, features);
  const primaryRecords = records.filter((record) => record.isPrimary);
  const warnings = [
    ...checkFeatureBoundaryWarnings(primaryRecords),
    ...checkFeatureSizeWarnings(primaryRecords),
    ...depthWarnings,
    ...checkHoleSpacingWarnings(primaryRecords),
    ...checkPatternSymmetryWarnings(primaryRecords, features),
    ...checkSharpInternalCornerWarnings(features),
  ];

  if (features.length === 0) {
    warnings.push(
      reviewWarning(
        "info",
        "No feature warnings yet",
        "Add a cut or extrusion to see live spacing, boundary, and manufacturability warnings.",
      ),
    );
  }

  if (skippedCount > 0) {
    warnings.push(
      reviewWarning(
        "info",
        "Some features use API-assisted dimensions",
        "Live boundary checks only run on exact rectangle, circle, and polygon features on base top, front, and side faces.",
      ),
    );
  }

  if (warnings.length === 0) {
    warnings.push(
      reviewWarning(
        "success",
        "No obvious design-review warnings",
        "The exact manual features look inside the base and reasonably spaced. This is not a full engineering or DFM approval.",
      ),
    );
  }

  return {
    baseGeometry,
    views: {
      top: {
        baseGeometry: baseViewGeometry(baseGeometry, "top"),
        features: records.filter((record) => record.viewName === "top"),
      },
      front: {
        baseGeometry: baseViewGeometry(baseGeometry, "front"),
        features: records.filter((record) => record.viewName === "front"),
      },
      right: {
        baseGeometry: baseViewGeometry(baseGeometry, "right"),
        features: records.filter((record) => record.viewName === "right"),
      },
    },
    warnings,
    skippedCount,
    primaryCount: primaryRecords.length,
  };
}

export function boundsWidth(bounds) {
  return bounds[2] - bounds[0];
}

export function boundsHeight(bounds) {
  return bounds[3] - bounds[1];
}

export function boundsCenter(bounds) {
  return [
    (bounds[0] + bounds[2]) / 2,
    (bounds[1] + bounds[3]) / 2,
  ];
}

export function validBounds(bounds) {
  return (
    Array.isArray(bounds)
    && bounds.length === 4
    && bounds.every((value) => Number.isFinite(value))
    && bounds[2] > bounds[0]
    && bounds[3] > bounds[1]
  );
}

export function allPreviewBounds(baseGeometry, featureData) {
  const boundsList = [baseGeometry.bounds];
  for (const feature of featureData) {
    if (validBounds(feature.bounds)) {
      boundsList.push(feature.bounds);
    }
  }

  const minX = Math.min(...boundsList.map((bounds) => bounds[0]));
  const minY = Math.min(...boundsList.map((bounds) => bounds[1]));
  const maxX = Math.max(...boundsList.map((bounds) => bounds[2]));
  const maxY = Math.max(...boundsList.map((bounds) => bounds[3]));
  const width = Math.max(maxX - minX, 1);
  const height = Math.max(maxY - minY, 1);
  const padding = Math.max(width, height) * 0.18;

  return [
    minX - padding,
    minY - padding,
    maxX + padding,
    maxY + padding,
  ];
}

export function previewScaleForBounds(worldBounds) {
  const worldWidth = worldBounds[2] - worldBounds[0];
  const worldHeight = worldBounds[3] - worldBounds[1];

  return Math.min(
    (PREVIEW_WIDTH - 60) / worldWidth,
    (PREVIEW_HEIGHT - 60) / worldHeight,
  );
}

export function createPreviewMapper(worldBounds, fixedScale = null) {
  const worldWidth = worldBounds[2] - worldBounds[0];
  const worldHeight = worldBounds[3] - worldBounds[1];
  const scale = fixedScale || previewScaleForBounds(worldBounds);
  const usedWidth = worldWidth * scale;
  const usedHeight = worldHeight * scale;
  const offsetX = (PREVIEW_WIDTH - usedWidth) / 2 - worldBounds[0] * scale;
  const offsetY = (PREVIEW_HEIGHT + usedHeight) / 2 + worldBounds[1] * scale;

  return {
    point(x, y) {
      return [
        offsetX + x * scale,
        offsetY - y * scale,
      ];
    },
    length(value) {
      return value * scale;
    },
  };
}

export function formatDimension(value) {
  if (!Number.isFinite(value)) {
    return "";
  }

  if (Math.abs(value - Math.round(value)) < 0.001) {
    return String(Math.round(value));
  }

  return value.toFixed(2).replace(/\.?0+$/, "");
}

export function regularPolygonPoints(center, radius, sides, mapper) {
  const points = [];
  const startAngle = -Math.PI / 2;
  for (let index = 0; index < sides; index += 1) {
    const angle = startAngle + (2 * Math.PI * index) / sides;
    const x = center[0] + radius * Math.cos(angle);
    const y = center[1] + radius * Math.sin(angle);
    points.push(mapper.point(x, y).join(","));
  }

  return points.join(" ");
}

function emptyViews() {
  return {
    top: { baseGeometry: null, features: [] },
    front: { baseGeometry: null, features: [] },
    right: { baseGeometry: null, features: [] },
  };
}

function reviewWarning(severity, title, message) {
  return { severity, title, message };
}

function numberValue(value) {
  return Number(value) || 0;
}

function baseReviewGeometry(base) {
  const thickness = numberValue(base.thickness);
  if (base.reasonable || base.profile === "polyline" || thickness <= 0) {
    return null;
  }

  if (base.profile === "rectangle") {
    const width = numberValue(base.width);
    const height = numberValue(base.height);
    if (width <= 0 || height <= 0) {
      return null;
    }
    return {
      profile: "rectangle",
      width,
      height,
      thickness,
      bounds: [-width / 2, -height / 2, width / 2, height / 2],
    };
  }

  if (base.profile === "circle") {
    const diameter = numberValue(base.diameter);
    if (diameter <= 0) {
      return null;
    }
    return {
      profile: "circle",
      diameter,
      radius: diameter / 2,
      thickness,
      bounds: [-diameter / 2, -diameter / 2, diameter / 2, diameter / 2],
    };
  }

  if (base.profile === "polygon") {
    const diameter = numberValue(base.diameter);
    const sides = numberValue(base.sides);
    if (diameter <= 0 || sides < 3) {
      return null;
    }
    return {
      profile: "polygon",
      diameter,
      radius: diameter / 2,
      sides,
      thickness,
      bounds: [-diameter / 2, -diameter / 2, diameter / 2, diameter / 2],
    };
  }

  return null;
}

function featureLocalGeometry(feature) {
  if (feature.reasonable || feature.profile === "polyline") {
    return null;
  }

  if (feature.profile === "rectangle") {
    const width = numberValue(feature.width);
    const height = numberValue(feature.height);
    if (width <= 0 || height <= 0) {
      return null;
    }
    return {
      width,
      height,
      bounds: [-width / 2, -height / 2, width / 2, height / 2],
    };
  }

  if (feature.profile === "circle") {
    const diameter = numberValue(feature.diameter);
    if (diameter <= 0) {
      return null;
    }
    return {
      width: diameter,
      height: diameter,
      radius: diameter / 2,
      bounds: [-diameter / 2, -diameter / 2, diameter / 2, diameter / 2],
    };
  }

  if (feature.profile === "polygon") {
    const diameter = numberValue(feature.diameter);
    const sides = numberValue(feature.sides);
    if (diameter <= 0 || sides < 3) {
      return null;
    }
    return {
      width: diameter,
      height: diameter,
      radius: diameter / 2,
      sides,
      bounds: [-diameter / 2, -diameter / 2, diameter / 2, diameter / 2],
    };
  }

  return null;
}

function moveBounds(bounds, position) {
  return [
    bounds[0] + position[0],
    bounds[1] + position[1],
    bounds[2] + position[0],
    bounds[3] + position[1],
  ];
}

function rectangleContainsBounds(containerBounds, innerBounds, margin = 0) {
  return (
    innerBounds[0] >= containerBounds[0] + margin
    && innerBounds[1] >= containerBounds[1] + margin
    && innerBounds[2] <= containerBounds[2] - margin
    && innerBounds[3] <= containerBounds[3] - margin
  );
}

function circularBaseContainsBounds(baseGeometry, innerBounds, margin = 0) {
  const radius = baseGeometry.radius - margin;
  if (radius <= 0) {
    return false;
  }

  const corners = [
    [innerBounds[0], innerBounds[1]],
    [innerBounds[0], innerBounds[3]],
    [innerBounds[2], innerBounds[1]],
    [innerBounds[2], innerBounds[3]],
  ];

  return corners.every(([x, y]) => Math.hypot(x, y) <= radius);
}

function baseContainsFeatureBounds(baseGeometry, featureBounds, margin = 0) {
  if (baseGeometry.profile === "rectangle" || baseGeometry.profile === "projection") {
    return rectangleContainsBounds(baseGeometry.bounds, featureBounds, margin);
  }

  if (baseGeometry.profile === "circle" || baseGeometry.profile === "polygon") {
    return circularBaseContainsBounds(baseGeometry, featureBounds, margin);
  }

  return true;
}

function distanceBetweenPoints(a, b) {
  return Math.hypot(a[0] - b[0], a[1] - b[1]);
}

function baseViewGeometry(baseGeometry, viewName) {
  if (viewName === "top") {
    return { ...baseGeometry, viewName: "top", dimensionAxes: ["x", "y"] };
  }

  const topWidth = boundsWidth(baseGeometry.bounds);
  const topDepth = boundsHeight(baseGeometry.bounds);

  if (viewName === "front") {
    return {
      profile: "projection",
      viewName: "front",
      dimensionAxes: ["x", "z"],
      width: topWidth,
      height: baseGeometry.thickness,
      bounds: [-topWidth / 2, -baseGeometry.thickness / 2, topWidth / 2, baseGeometry.thickness / 2],
    };
  }

  if (viewName === "right") {
    return {
      profile: "projection",
      viewName: "right",
      dimensionAxes: ["y", "z"],
      width: topDepth,
      height: baseGeometry.thickness,
      bounds: [-topDepth / 2, -baseGeometry.thickness / 2, topDepth / 2, baseGeometry.thickness / 2],
    };
  }

  return null;
}

function basePreviewVolume(baseGeometry) {
  return {
    id: "base",
    x: [baseGeometry.bounds[0], baseGeometry.bounds[2]],
    y: [baseGeometry.bounds[1], baseGeometry.bounds[3]],
    z: [-baseGeometry.thickness / 2, baseGeometry.thickness / 2],
  };
}

function volumeCenter(volume) {
  return {
    x: (volume.x[0] + volume.x[1]) / 2,
    y: (volume.y[0] + volume.y[1]) / 2,
    z: (volume.z[0] + volume.z[1]) / 2,
  };
}

function targetParts(target) {
  const parts = String(target).split(".");
  if (parts.length !== 2) {
    return null;
  }

  return { id: parts[0], face: parts[1] };
}

function faceInfoFromVolume(volume, faceName) {
  const center = volumeCenter(volume);
  const faceMap = {
    top: {
      viewName: "top",
      axes: ["x", "y"],
      normalAxis: "z",
      outwardDirection: 1,
      planeCoordinate: volume.z[1],
      center: [center.x, center.y],
    },
    bottom: {
      viewName: "top",
      axes: ["x", "y"],
      normalAxis: "z",
      outwardDirection: -1,
      planeCoordinate: volume.z[0],
      center: [center.x, center.y],
    },
    front: {
      viewName: "front",
      axes: ["x", "z"],
      normalAxis: "y",
      outwardDirection: -1,
      planeCoordinate: volume.y[0],
      center: [center.x, center.z],
    },
    back: {
      viewName: "front",
      axes: ["x", "z"],
      normalAxis: "y",
      outwardDirection: 1,
      planeCoordinate: volume.y[1],
      center: [center.x, center.z],
    },
    right: {
      viewName: "right",
      axes: ["y", "z"],
      normalAxis: "x",
      outwardDirection: 1,
      planeCoordinate: volume.x[1],
      center: [center.y, center.z],
    },
    left: {
      viewName: "right",
      axes: ["y", "z"],
      normalAxis: "x",
      outwardDirection: -1,
      planeCoordinate: volume.x[0],
      center: [center.y, center.z],
    },
  };

  if (!(faceName in faceMap)) {
    return null;
  }

  return {
    ...faceMap[faceName],
    targetId: volume.id,
    faceName,
    volume,
  };
}

function faceInfoForTarget(target, volumeById) {
  const parts = targetParts(target);
  if (parts === null || !volumeById.has(parts.id)) {
    return null;
  }

  return faceInfoFromVolume(volumeById.get(parts.id), parts.face);
}

function facePlaneBounds(faceInfo) {
  const [horizontalAxis, verticalAxis] = faceInfo.axes;
  return [
    faceInfo.volume[horizontalAxis][0],
    faceInfo.volume[verticalAxis][0],
    faceInfo.volume[horizontalAxis][1],
    faceInfo.volume[verticalAxis][1],
  ];
}

function faceReviewGeometry(faceInfo, baseGeometry) {
  if (faceInfo.targetId === "base") {
    return baseViewGeometry(baseGeometry, faceInfo.viewName);
  }

  return {
    profile: "projection",
    viewName: faceInfo.viewName,
    bounds: facePlaneBounds(faceInfo),
  };
}

function faceBoundsFromLocal(faceInfo, localBounds, position) {
  return moveBounds(localBounds, [
    faceInfo.center[0] + position[0],
    faceInfo.center[1] + position[1],
  ]);
}

function facePositionFromLocal(faceInfo, position) {
  return [
    faceInfo.center[0] + position[0],
    faceInfo.center[1] + position[1],
  ];
}

function faceDepth(faceInfo) {
  const axisBounds = faceInfo.volume[faceInfo.normalAxis];
  return axisBounds[1] - axisBounds[0];
}

function volumeFromFaceBounds(faceInfo, faceBounds, startCoordinate, endCoordinate, id = null) {
  const volume = {
    id,
    x: [faceInfo.volume.x[0], faceInfo.volume.x[1]],
    y: [faceInfo.volume.y[0], faceInfo.volume.y[1]],
    z: [faceInfo.volume.z[0], faceInfo.volume.z[1]],
  };
  const [horizontalAxis, verticalAxis] = faceInfo.axes;

  volume[horizontalAxis] = [faceBounds[0], faceBounds[2]];
  volume[verticalAxis] = [faceBounds[1], faceBounds[3]];
  volume[faceInfo.normalAxis] = [
    Math.min(startCoordinate, endCoordinate),
    Math.max(startCoordinate, endCoordinate),
  ];

  return volume;
}

function extrudeVolumeFromFace(faceInfo, faceBounds, distance, id) {
  return volumeFromFaceBounds(
    faceInfo,
    faceBounds,
    faceInfo.planeCoordinate,
    faceInfo.planeCoordinate + faceInfo.outwardDirection * distance,
    id,
  );
}

function cutVolumeFromFace(faceInfo, faceBounds, depth) {
  return volumeFromFaceBounds(
    faceInfo,
    faceBounds,
    faceInfo.planeCoordinate,
    faceInfo.planeCoordinate - faceInfo.outwardDirection * depth,
  );
}

function modelAxisBounds(volumeById, axisName) {
  const volumes = Array.from(volumeById.values());
  return [
    Math.min(...volumes.map((volume) => volume[axisName][0])),
    Math.max(...volumes.map((volume) => volume[axisName][1])),
  ];
}

function throughCutVolumeFromFace(faceInfo, faceBounds, volumeById) {
  const modelBounds = modelAxisBounds(volumeById, faceInfo.normalAxis);
  const farSideCoordinate = faceInfo.outwardDirection > 0
    ? modelBounds[0]
    : modelBounds[1];
  return volumeFromFaceBounds(
    faceInfo,
    faceBounds,
    faceInfo.planeCoordinate,
    farSideCoordinate,
  );
}

function projectionBoundsForVolume(volume, viewName) {
  if (viewName === "top") {
    return [volume.x[0], volume.y[0], volume.x[1], volume.y[1]];
  }

  if (viewName === "front") {
    return [volume.x[0], volume.z[0], volume.x[1], volume.z[1]];
  }

  if (viewName === "right") {
    return [volume.y[0], volume.z[0], volume.y[1], volume.z[1]];
  }

  return null;
}

function previewRecordFromFace({
  operation,
  target,
  profile,
  featureNumber,
  feature,
  localGeometry,
  faceInfo,
  baseGeometry,
  position,
  bounds,
}) {
  return {
    featureNumber,
    operation,
    target,
    profile,
    feature,
    featureId: feature.localId,
    position: facePositionFromLocal(faceInfo, position),
    bounds,
    width: localGeometry.width,
    height: localGeometry.height,
    radius: localGeometry.radius || 0,
    sides: localGeometry.sides || 0,
    baseGeometry: faceReviewGeometry(faceInfo, baseGeometry),
    viewName: faceInfo.viewName,
    dimensionAxes: faceInfo.axes,
    isPrimary: true,
  };
}

function projectionRecordFromVolume({
  operation,
  target,
  featureNumber,
  feature,
  volume,
  viewName,
  baseGeometry,
}) {
  const bounds = projectionBoundsForVolume(volume, viewName);
  if (bounds === null || !validBounds(bounds)) {
    return null;
  }

  return {
    featureNumber,
    operation,
    target,
    profile: "rectangle",
    feature,
    featureId: feature.localId,
    position: boundsCenter(bounds),
    bounds,
    width: boundsWidth(bounds),
    height: boundsHeight(bounds),
    radius: 0,
    sides: 0,
    baseGeometry: baseViewGeometry(baseGeometry, viewName),
    viewName,
    dimensionAxes: viewAxes(viewName),
    isPrimary: false,
  };
}

function viewAxes(viewName) {
  if (viewName === "top") {
    return ["x", "y"];
  }

  if (viewName === "front") {
    return ["x", "z"];
  }

  if (viewName === "right") {
    return ["y", "z"];
  }

  return ["x", "y"];
}

function addProjectionRecords(records, recordOptions, volume, primaryViewName) {
  for (const viewName of ["top", "front", "right"]) {
    if (viewName === primaryViewName) {
      continue;
    }

    const record = projectionRecordFromVolume({
      ...recordOptions,
      volume,
      viewName,
    });

    if (record !== null) {
      records.push(record);
    }
  }
}

function collectExactFeaturePreviewData(baseGeometry, features) {
  const records = [];
  const depthWarnings = [];
  const volumeById = new Map();
  volumeById.set("base", basePreviewVolume(baseGeometry));

  let skippedCount = 0;

  for (const [featureIndex, feature] of features.entries()) {
    const featureNumber = featureIndex + 1;
    const localGeometry = featureLocalGeometry(feature);
    const faceInfo = faceInfoForTarget(feature.target, volumeById);

    if (localGeometry === null || faceInfo === null) {
      skippedCount += 1;
      continue;
    }

    const amount = numberValue(feature.amount);
    if (
      feature.operation === "cut"
      && feature.depthMode !== "through"
      && amount > faceDepth(faceInfo)
    ) {
      depthWarnings.push(
        reviewWarning(
          "warning",
          `Feature ${featureNumber} cut is deeper than its target`,
          "This blind cut is deeper than the material available normal to its target face. Use a through cut if that is intentional.",
        ),
      );
    }

    const seedPosition = [numberValue(feature.x), numberValue(feature.y)];
    const positions = expandFeatureInstances(feature, seedPosition);
    let addedAnyPrimaryRecord = false;

    for (const position of positions) {
      const bounds = faceBoundsFromLocal(faceInfo, localGeometry.bounds, position);
      records.push(
        previewRecordFromFace({
          operation: feature.operation,
          target: feature.target,
          profile: feature.profile,
          featureNumber,
          feature,
          localGeometry,
          faceInfo,
          baseGeometry,
          position,
          bounds,
        }),
      );
      addedAnyPrimaryRecord = true;

      const recordOptions = {
        operation: feature.operation,
        target: feature.target,
        featureNumber,
        feature,
        baseGeometry,
      };

      if (feature.operation === "add_extrude") {
        const featureId = `feature_${featureNumber}`;
        const extrudeVolume = extrudeVolumeFromFace(faceInfo, bounds, amount, featureId);
        if (!volumeById.has(featureId)) {
          volumeById.set(featureId, extrudeVolume);
        }
        addProjectionRecords(records, recordOptions, extrudeVolume, faceInfo.viewName);
      } else if (feature.operation === "cut") {
        const cutVolume = feature.depthMode === "through"
          ? throughCutVolumeFromFace(faceInfo, bounds, volumeById)
          : cutVolumeFromFace(faceInfo, bounds, amount);
        addProjectionRecords(records, recordOptions, cutVolume, faceInfo.viewName);
      }
    }

    if (!addedAnyPrimaryRecord) {
      skippedCount += 1;
    }
  }

  return { records, skippedCount, depthWarnings };
}

function expandFeatureInstances(feature, seedPosition) {
  const [x, y] = seedPosition;

  if (feature.pattern === "circular") {
    const copies = Math.max(1, Math.floor(numberValue(feature.copies) || 1));
    const radius = Math.hypot(x, y);
    const startAngle = Math.atan2(y, x);
    return Array.from({ length: copies }, (_, index) => {
      const angle = startAngle + (2 * Math.PI * index) / copies;
      return [
        radius * Math.cos(angle),
        radius * Math.sin(angle),
      ];
    });
  }

  const xValues = feature.mirrorY ? [x, -x] : [x];
  const yValues = feature.mirrorX ? [y, -y] : [y];
  const positions = [];

  for (const instanceX of xValues) {
    for (const instanceY of yValues) {
      const key = `${instanceX.toFixed(3)},${instanceY.toFixed(3)}`;
      if (!positions.some(([px, py]) => `${px.toFixed(3)},${py.toFixed(3)}` === key)) {
        positions.push([instanceX, instanceY]);
      }
    }
  }

  return positions;
}

function checkFeatureBoundaryWarnings(featureData) {
  const warnings = [];

  for (const feature of featureData) {
    const severity = feature.operation === "add_extrude" ? "error" : "warning";
    const action = feature.operation === "add_extrude" ? "extrusion" : "cut";

    if (!baseContainsFeatureBounds(feature.baseGeometry, feature.bounds, 0)) {
      warnings.push(
        reviewWarning(
          severity,
          `Feature ${feature.featureNumber} may hang off the base`,
          `This ${action} extends outside the base boundary. Move it inward or reduce its size.`,
        ),
      );
      continue;
    }

    if (!baseContainsFeatureBounds(feature.baseGeometry, feature.bounds, REVIEW_EDGE_MARGIN)) {
      warnings.push(
        reviewWarning(
          "warning",
          `Feature ${feature.featureNumber} is close to an edge`,
          `This ${action} is within about ${REVIEW_EDGE_MARGIN} mm of the base edge. That may leave weak material near the feature.`,
        ),
      );
    }
  }

  return warnings;
}

function checkFeatureSizeWarnings(featureData) {
  const warnings = [];

  for (const feature of featureData) {
    const baseWidth = boundsWidth(feature.baseGeometry.bounds);
    const baseHeight = boundsHeight(feature.baseGeometry.bounds);

    if (
      feature.width > baseWidth * REVIEW_FEATURE_FRACTION_LIMIT
      || feature.height > baseHeight * REVIEW_FEATURE_FRACTION_LIMIT
    ) {
      warnings.push(
        reviewWarning(
          "warning",
          `Feature ${feature.featureNumber} is very large`,
          "This feature is large relative to the base. Check that it is intentional and leaves enough surrounding material.",
        ),
      );
    }
  }

  return warnings;
}

function checkHoleSpacingWarnings(featureData) {
  const warnings = [];
  const circularCuts = featureData.filter(
    (feature) => feature.operation === "cut" && feature.profile === "circle",
  );
  const cutsByView = new Map();

  for (const cut of circularCuts) {
    const viewName = cut.viewName || "top";
    if (!cutsByView.has(viewName)) {
      cutsByView.set(viewName, []);
    }
    cutsByView.get(viewName).push(cut);
  }

  for (const viewCuts of cutsByView.values()) {
    for (let i = 0; i < viewCuts.length; i += 1) {
      for (let j = i + 1; j < viewCuts.length; j += 1) {
        const first = viewCuts[i];
        const second = viewCuts[j];
        const centerDistance = distanceBetweenPoints(first.position, second.position);
        const clearDistance = centerDistance - first.radius - second.radius;

        if (clearDistance < 0) {
          warnings.push(
            reviewWarning(
              "error",
              "Circular cuts overlap",
              `Features ${first.featureNumber} and ${second.featureNumber} overlap in the same drawing view. Move them apart or reduce their diameters.`,
            ),
          );
        } else if (clearDistance < REVIEW_MIN_FEATURE_SPACING) {
          warnings.push(
            reviewWarning(
              "warning",
              "Circular cuts are very close",
              `Features ${first.featureNumber} and ${second.featureNumber} leave only ${clearDistance.toFixed(1)} mm between holes in the same drawing view.`,
            ),
          );
        }
      }
    }
  }

  return warnings;
}

function checkPatternSymmetryWarnings(featureData, features) {
  const warnings = [];

  for (const [index, feature] of features.entries()) {
    const records = featureData.filter((record) => record.featureId === feature.localId);
    const featureNumber = index + 1;

    if (feature.pattern === "circular") {
      const requestedCount = numberValue(feature.copies);
      if (requestedCount < 2) {
        warnings.push(
          reviewWarning(
            "warning",
            `Feature ${featureNumber} circular pattern needs more copies`,
            "Use at least 2 copies for a circular pattern.",
          ),
        );
      } else if (records.length > 0 && records.length < requestedCount) {
        warnings.push(
          reviewWarning(
            "warning",
            `Feature ${featureNumber} circular pattern collapses`,
            "The seed position is probably at the origin, so rotated copies land on top of each other. Move the feature away from [0, 0].",
          ),
        );
      }
    }

    if ((feature.mirrorX || feature.mirrorY) && records.length === 1) {
      warnings.push(
        reviewWarning(
          "warning",
          `Feature ${featureNumber} mirror pattern collapses`,
          "The feature may be centered on the mirror axis, so the mirrored copy lands on the original position.",
        ),
      );
    }
  }

  return warnings;
}

function checkSharpInternalCornerWarnings(features) {
  const warnings = [];

  for (const [index, feature] of features.entries()) {
    if (feature.operation === "cut" && feature.profile === "rectangle" && !feature.reasonable) {
      warnings.push(
        reviewWarning(
          "info",
          `Feature ${index + 1} has sharp internal corners`,
          "Rectangular CNC pockets and slots usually need internal corner radii or relief cuts.",
        ),
      );
    }
  }

  return warnings;
}
