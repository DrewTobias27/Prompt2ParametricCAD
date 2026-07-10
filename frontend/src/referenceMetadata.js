import { isEdgeTreatment } from "./modelBuilders.js";

export const REFERENCE_KINDS = {
  FACE: "face",
  EDGE: "edge",
  VERTEX: "vertex",
  SKETCH_PLANE: "sketch_plane",
};

export const CAD_REFERENCE_KINDS = {
  PLANE: "plane",
  EDGE_GROUP: "edge_group",
  SURFACE: "surface",
  VERTEX: "vertex",
};

const BASE_FACE_ROLES = [
  ["top", "top face"],
  ["bottom", "bottom face"],
  ["front", "front face"],
  ["back", "back face"],
  ["left", "left face"],
  ["right", "right face"],
];

const BASE_EDGE_ROLES = [
  ["top_outer_edges", "top outer edges"],
  ["bottom_outer_edges", "bottom outer edges"],
  ["vertical_edges", "vertical edges"],
  ["all_edges", "all edges"],
];

const ADDED_FEATURE_EDGE_ROLES = [
  ["top_outer_edges", "top outer edges"],
  ["vertical_edges", "vertical edges"],
];

export function baseReferences(base, { kind } = {}) {
  const references = [
    referenceMetadata({
      ownerId: "base",
      ownerLabel: "Base",
      role: "top",
      label: "top face",
      kind: REFERENCE_KINDS.FACE,
      cadKind: CAD_REFERENCE_KINDS.PLANE,
      geometryRole: "planar_start_face",
      allowedOperations: ["add_extrude", "cut"],
    }),
    referenceMetadata({
      ownerId: "base",
      ownerLabel: "Base",
      role: "bottom",
      label: "bottom face",
      kind: REFERENCE_KINDS.FACE,
      cadKind: CAD_REFERENCE_KINDS.PLANE,
      geometryRole: "planar_start_face",
      allowedOperations: ["add_extrude", "cut"],
    }),
  ];

  if (base?.profile === "rectangle") {
    references.push(
      ...BASE_FACE_ROLES.slice(2).map(([role, label]) => referenceMetadata({
        ownerId: "base",
        ownerLabel: "Base",
        role,
        label,
        kind: REFERENCE_KINDS.FACE,
        cadKind: CAD_REFERENCE_KINDS.PLANE,
        geometryRole: "planar_side_face",
        allowedOperations: ["add_extrude", "cut"],
      })),
    );
  }

  references.push(
    ...edgeRolesForBase(base).map(([role, label]) => edgeReference("base", "Base", role, label)),
  );

  return filterReferencesByKind(references, kind);
}

export function featureReferences(feature, featureNumber, { kind } = {}) {
  if (feature.operation !== "add_extrude") {
    return [];
  }

  const ownerId = `feature_${featureNumber}`;
  const ownerLabel = `Feature ${featureNumber}`;
  const references = [
    referenceMetadata({
      ownerId,
      ownerLabel,
      role: "top",
      label: "top face",
      kind: REFERENCE_KINDS.FACE,
      cadKind: CAD_REFERENCE_KINDS.PLANE,
      geometryRole: "planar_end_face",
      sourceFeatureId: ownerId,
      allowedOperations: ["add_extrude", "cut"],
    }),
    referenceMetadata({
      ownerId,
      ownerLabel,
      role: "bottom",
      label: "bottom face",
      kind: REFERENCE_KINDS.FACE,
      cadKind: CAD_REFERENCE_KINDS.PLANE,
      geometryRole: "planar_start_face",
      sourceFeatureId: ownerId,
      allowedOperations: ["add_extrude", "cut"],
    }),
  ];

  if (feature.profile === "rectangle") {
    references.push(
      ...BASE_FACE_ROLES.slice(2).map(([role, label]) => referenceMetadata({
        ownerId,
        ownerLabel,
        role,
        label,
        kind: REFERENCE_KINDS.FACE,
        cadKind: CAD_REFERENCE_KINDS.PLANE,
        geometryRole: "planar_side_face",
        sourceFeatureId: ownerId,
        allowedOperations: ["add_extrude", "cut"],
      })),
    );
  }

  references.push(
    ...ADDED_FEATURE_EDGE_ROLES.map(([role, label]) => edgeReference(ownerId, ownerLabel, role, label)),
  );

  return filterReferencesByKind(references, kind);
}

export function targetOptionGroupsForFeature({ base, features, featureIndex, feature }) {
  const referenceKind = isEdgeTreatment(feature)
    ? REFERENCE_KINDS.EDGE
    : REFERENCE_KINDS.FACE;
  const groups = [
    {
      label: referenceKind === REFERENCE_KINDS.EDGE ? "Base edge groups" : "Base faces",
      references: baseReferences(base, { kind: referenceKind }),
    },
  ];

  for (let priorIndex = 0; priorIndex < featureIndex; priorIndex += 1) {
    const priorFeature = features[priorIndex];
    const references = featureReferences(priorFeature, priorIndex + 1, { kind: referenceKind });
    if (references.length === 0) {
      continue;
    }

    groups.push({
      label: referenceKind === REFERENCE_KINDS.EDGE
        ? `Feature ${priorIndex + 1} edge groups`
        : `Feature ${priorIndex + 1} faces`,
      references,
    });
  }

  return groups.map((group) => ({
    ...group,
    options: group.references.map((reference) => [reference.name, reference.optionLabel]),
  }));
}

export function flattenOptionGroups(groups) {
  return groups.flatMap((group) => group.options);
}

export function humanizeTarget(target) {
  const [id, ...rest] = String(target).split(".");
  const reference = rest.join(".");
  if (!id || !reference) {
    return target;
  }

  const readableReference = reference.replaceAll("_", " ");
  if (id === "base") {
    return `base ${readableReference}`;
  }

  return `${id.replace("_", " ")} ${readableReference}`;
}

function referenceMetadata({
  ownerId,
  ownerLabel,
  role,
  label,
  kind,
  cadKind,
  geometryRole,
  sourceFeatureId = null,
  allowedOperations = [],
}) {
  return {
    name: `${ownerId}.${role}`,
    target: `${ownerId}.${role}`,
    label,
    optionLabel: `${ownerLabel} ${label}`,
    kind,
    cadKind,
    ownerId,
    ownerLabel,
    role,
    roleLabel: label,
    geometryRole,
    sourceFeatureId,
    allowedOperations,
  };
}

function edgeReference(ownerId, ownerLabel, role, label) {
  return referenceMetadata({
    ownerId,
    ownerLabel,
    role,
    label,
    kind: REFERENCE_KINDS.EDGE,
    cadKind: CAD_REFERENCE_KINDS.EDGE_GROUP,
    geometryRole: "edge_group",
    sourceFeatureId: ownerId === "base" ? null : ownerId,
    allowedOperations: ["chamfer", "fillet"],
  });
}

function edgeRolesForBase(base) {
  if (base?.profile === "rectangle") {
    return BASE_EDGE_ROLES.slice(0, 3);
  }

  return [
    ["top_outer_edges", "top outer edges"],
    ["bottom_outer_edges", "bottom outer edges"],
    ["all_edges", "all edges"],
  ];
}

function filterReferencesByKind(references, kind) {
  if (!kind) {
    return references;
  }

  return references.filter((reference) => reference.kind === kind);
}
