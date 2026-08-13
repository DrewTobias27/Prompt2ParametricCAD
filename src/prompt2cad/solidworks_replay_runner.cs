using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Runtime.Serialization;
using System.Runtime.Serialization.Json;
using SolidWorks.Interop.sldworks;
using SolidWorks.Interop.swconst;

namespace Prompt2Cad.SolidWorks
{
    [DataContract]
    public sealed class ReplayPlan
    {
        [DataMember(Name = "format")]
        public string Format { get; set; }

        [DataMember(Name = "version")]
        public int Version { get; set; }

        [DataMember(Name = "features")]
        public ReplayStep[] Features { get; set; }
    }

    [DataContract]
    public sealed class MutationDocument
    {
        [DataMember(Name = "format")]
        public string Format { get; set; }

        [DataMember(Name = "version")]
        public int Version { get; set; }

        [DataMember(Name = "mutations")]
        public ParameterMutation[] Mutations { get; set; }
    }

    [DataContract]
    public sealed class ParameterMutation
    {
        [DataMember(Name = "parameter_id")]
        public string ParameterId { get; set; }

        [DataMember(Name = "value")]
        public double Value { get; set; }

        [DataMember(Name = "unit")]
        public string Unit { get; set; }
    }

    [DataContract]
    public sealed class ReplayStep
    {
        [DataMember(Name = "id")]
        public string Id { get; set; }

        [DataMember(Name = "feature_name")]
        public string FeatureName { get; set; }

        [DataMember(Name = "sketch_name")]
        public string SketchName { get; set; }

        [DataMember(Name = "support")]
        public SketchSupport Support { get; set; }

        [DataMember(Name = "sketch")]
        public SketchSpec Sketch { get; set; }

        [DataMember(Name = "feature")]
        public FeatureSpec Feature { get; set; }

        [DataMember(Name = "pattern")]
        public PatternSpec Pattern { get; set; }

        [DataMember(Name = "parameter_bindings")]
        public NativeParameterBinding[] ParameterBindings { get; set; }

        [DataMember(Name = "publish_references")]
        public NativeReferenceSpec[] PublishReferences { get; set; }
    }

    [DataContract]
    public sealed class SketchSupport
    {
        [DataMember(Name = "kind")]
        public string Kind { get; set; }

        [DataMember(Name = "name")]
        public string Name { get; set; }

        [DataMember(Name = "datum_name")]
        public string DatumName { get; set; }

        [DataMember(Name = "semantic_plane")]
        public string SemanticPlane { get; set; }

        [DataMember(Name = "offset_mm")]
        public double OffsetMillimeters { get; set; }

        [DataMember(Name = "flip_offset")]
        public bool FlipOffset { get; set; }

        [DataMember(Name = "reverse_direction")]
        public bool ReverseDirection { get; set; }

        [DataMember(Name = "entity_name")]
        public string EntityName { get; set; }

        [DataMember(Name = "parent_feature_id")]
        public string ParentFeatureId { get; set; }

        [DataMember(Name = "target_feature_name")]
        public string TargetFeatureName { get; set; }

        [DataMember(Name = "selector")]
        public string Selector { get; set; }

        [DataMember(Name = "frame")]
        public FrameSpec Frame { get; set; }

        [DataMember(Name = "members")]
        public ReferenceMemberSpec[] Members { get; set; }
    }

    [DataContract]
    public sealed class ReferenceMemberSpec
    {
        [DataMember(Name = "reference_id")]
        public string ReferenceId { get; set; }

        [DataMember(Name = "center_mm")]
        public double[] CenterMillimeters { get; set; }

        [DataMember(Name = "bounding_box_mm")]
        public double[] BoundingBoxMillimeters { get; set; }
    }

    [DataContract]
    public sealed class FrameSpec
    {
        [DataMember(Name = "origin_mm")]
        public double[] OriginMillimeters { get; set; }

        [DataMember(Name = "x_axis")]
        public double[] XAxis { get; set; }

        [DataMember(Name = "normal")]
        public double[] Normal { get; set; }
    }

    [DataContract]
    public sealed class SketchSpec
    {
        [DataMember(Name = "profile")]
        public string Profile { get; set; }

        [DataMember(Name = "width_mm")]
        public double WidthMillimeters { get; set; }

        [DataMember(Name = "height_mm")]
        public double HeightMillimeters { get; set; }

        [DataMember(Name = "diameter_mm")]
        public double DiameterMillimeters { get; set; }

        [DataMember(Name = "sides")]
        public int Sides { get; set; }

        [DataMember(Name = "positions_mm")]
        public double[][] PositionsMillimeters { get; set; }

        [DataMember(Name = "points_mm")]
        public double[][] PointsMillimeters { get; set; }

        [DataMember(Name = "start_mm")]
        public double[] StartMillimeters { get; set; }

        [DataMember(Name = "segments")]
        public SketchPathSegment[] Segments { get; set; }

        [DataMember(Name = "close")]
        public bool Close { get; set; }

        [DataMember(Name = "driving_dimensions")]
        public DimensionSpec[] DrivingDimensions { get; set; }

        [DataMember(Name = "placement_controls")]
        public PlacementControl[] PlacementControls { get; set; }

        [DataMember(Name = "coordinate_controls")]
        public CoordinateControl[] CoordinateControls { get; set; }

        [DataMember(Name = "constraint_plan")]
        public SketchConstraintPlan ConstraintPlan { get; set; }
    }

    [DataContract]
    public sealed class SketchConstraintPlan
    {
        [DataMember(Name = "strategy")]
        public string Strategy { get; set; }

        [DataMember(Name = "profile")]
        public string Profile { get; set; }

        [DataMember(Name = "relations")]
        public string[] Relations { get; set; }

        [DataMember(Name = "horizontal_dimension_scheme")]
        public string HorizontalDimensionScheme { get; set; }

        [DataMember(Name = "vertical_dimension_scheme")]
        public string VerticalDimensionScheme { get; set; }

        [DataMember(Name = "require_fully_defined")]
        public bool RequireFullyDefined { get; set; }

        [DataMember(Name = "source_feature_id")]
        public string SourceFeatureId { get; set; }
    }

    [DataContract]
    public sealed class PlacementControl
    {
        [DataMember(Name = "instance_index")]
        public int InstanceIndex { get; set; }

        [DataMember(Name = "position_mm")]
        public double[] PositionMillimeters { get; set; }

        [DataMember(Name = "x_dimension")]
        public DimensionSpec XDimension { get; set; }

        [DataMember(Name = "y_dimension")]
        public DimensionSpec YDimension { get; set; }
    }

    [DataContract]
    public sealed class CoordinateControl
    {
        [DataMember(Name = "kind")]
        public string Kind { get; set; }

        [DataMember(Name = "segment_index")]
        public int? SegmentIndex { get; set; }

        [DataMember(Name = "position_mm")]
        public double[] PositionMillimeters { get; set; }

        [DataMember(Name = "x_dimension")]
        public DimensionSpec XDimension { get; set; }

        [DataMember(Name = "y_dimension")]
        public DimensionSpec YDimension { get; set; }
    }

    [DataContract]
    public sealed class SketchPathSegment
    {
        [DataMember(Name = "type")]
        public string Type { get; set; }

        [DataMember(Name = "through")]
        public double[] ThroughMillimeters { get; set; }

        [DataMember(Name = "to")]
        public double[] ToMillimeters { get; set; }
    }

    [DataContract]
    public sealed class FeatureSpec
    {
        [DataMember(Name = "kind")]
        public string Kind { get; set; }

        [DataMember(Name = "end_condition")]
        public string EndCondition { get; set; }

        [DataMember(Name = "depth_mm")]
        public double? DepthMillimeters { get; set; }

        [DataMember(Name = "reverse_depth_mm")]
        public double? ReverseDepthMillimeters { get; set; }

        [DataMember(Name = "merge_result")]
        public bool MergeResult { get; set; }

        [DataMember(Name = "driving_dimension")]
        public DimensionSpec DrivingDimension { get; set; }

        [DataMember(Name = "reverse_driving_dimension")]
        public DimensionSpec ReverseDrivingDimension { get; set; }

        [DataMember(Name = "angle_deg")]
        public double AngleDegrees { get; set; }

        [DataMember(Name = "axis_start_mm")]
        public double[] AxisStartMillimeters { get; set; }

        [DataMember(Name = "axis_end_mm")]
        public double[] AxisEndMillimeters { get; set; }

        [DataMember(Name = "canonical_axis")]
        public CanonicalAxisSpec CanonicalAxis { get; set; }

        [DataMember(Name = "hole_diameter_mm")]
        public double HoleDiameterMillimeters { get; set; }

        [DataMember(Name = "countersink_diameter_mm")]
        public double CountersinkDiameterMillimeters { get; set; }

        [DataMember(Name = "countersink_angle_deg")]
        public double CountersinkAngleDegrees { get; set; }

        [DataMember(Name = "distance_mm")]
        public double DistanceMillimeters { get; set; }

        [DataMember(Name = "radius_mm")]
        public double RadiusMillimeters { get; set; }

        [DataMember(Name = "driving_dimensions")]
        public DimensionSpec[] DrivingDimensions { get; set; }
    }

    [DataContract]
    public sealed class CanonicalAxisSpec
    {
        [DataMember(Name = "kind")]
        public string Kind { get; set; }

        [DataMember(Name = "anchor_mm")]
        public double[] AnchorMillimeters { get; set; }

        [DataMember(Name = "direction")]
        public double[] Direction { get; set; }

        [DataMember(Name = "normal")]
        public double[] Normal { get; set; }

        [DataMember(Name = "signed_offset_mm")]
        public double SignedOffsetMillimeters { get; set; }

        [DataMember(Name = "direction_angle_deg")]
        public double DirectionAngleDegrees { get; set; }

        [DataMember(Name = "automated_mutation")]
        public bool AutomatedMutation { get; set; }

        [DataMember(Name = "edit_strategy")]
        public string EditStrategy { get; set; }
    }

    [DataContract]
    public sealed class PatternSpec
    {
        [DataMember(Name = "kind")]
        public string Kind { get; set; }

        [DataMember(Name = "seed_feature_name")]
        public string SeedFeatureName { get; set; }

        [DataMember(Name = "reference_sketch_name")]
        public string ReferenceSketchName { get; set; }

        [DataMember(Name = "axis_name")]
        public string AxisName { get; set; }

        [DataMember(Name = "placement_sketch_name")]
        public string PlacementSketchName { get; set; }

        [DataMember(Name = "seed_position_mm")]
        public double[] SeedPositionMillimeters { get; set; }

        [DataMember(Name = "positions_mm")]
        public double[][] PositionsMillimeters { get; set; }

        [DataMember(Name = "center_mm")]
        public double[] CenterMillimeters { get; set; }

        [DataMember(Name = "count")]
        public int Count { get; set; }

        [DataMember(Name = "total_angle_deg")]
        public double TotalAngleDegrees { get; set; }

        [DataMember(Name = "direction_1")]
        public double[] Direction1 { get; set; }

        [DataMember(Name = "count_1")]
        public int Count1 { get; set; }

        [DataMember(Name = "spacing_1_mm")]
        public double Spacing1Millimeters { get; set; }

        [DataMember(Name = "direction_2")]
        public double[] Direction2 { get; set; }

        [DataMember(Name = "count_2")]
        public int Count2 { get; set; }

        [DataMember(Name = "spacing_2_mm")]
        public double Spacing2Millimeters { get; set; }

        [DataMember(Name = "axes")]
        public string[] Axes { get; set; }
    }

    [DataContract]
    public sealed class DimensionSpec
    {
        [DataMember(Name = "parameter_id")]
        public string ParameterId { get; set; }

        [DataMember(Name = "native_name")]
        public string NativeName { get; set; }

        [DataMember(Name = "value_mm")]
        public double ValueMillimeters { get; set; }

        [DataMember(Name = "unit")]
        public string Unit { get; set; }
    }

    [DataContract]
    public sealed class NativeParameterBinding
    {
        [DataMember(Name = "parameter_id")]
        public string ParameterId { get; set; }

        [DataMember(Name = "native_name")]
        public string NativeName { get; set; }

        [DataMember(Name = "binding_kind")]
        public string BindingKind { get; set; }

        [DataMember(Name = "owner_kind")]
        public string OwnerKind { get; set; }

        [DataMember(Name = "owner_name")]
        public string OwnerName { get; set; }

        [DataMember(Name = "native_properties")]
        public string[] NativeProperties { get; set; }

        [DataMember(Name = "value")]
        public double Value { get; set; }

        [DataMember(Name = "unit")]
        public string Unit { get; set; }

        [DataMember(Name = "mutation_mode", EmitDefaultValue = false)]
        public string MutationMode { get; set; }

        [DataMember(Name = "source_value", EmitDefaultValue = false)]
        public double? SourceValue { get; set; }

        [DataMember(Name = "minimum_value", EmitDefaultValue = false)]
        public double? MinimumValue { get; set; }

        [DataMember(Name = "minimum_inclusive", EmitDefaultValue = false)]
        public bool MinimumInclusive { get; set; }

        [DataMember(Name = "maximum_value", EmitDefaultValue = false)]
        public double? MaximumValue { get; set; }

        [DataMember(Name = "maximum_inclusive", EmitDefaultValue = false)]
        public bool MaximumInclusive { get; set; }

        [DataMember(Name = "integer_only", EmitDefaultValue = false)]
        public bool IntegerOnly { get; set; }
    }

    [DataContract]
    public sealed class NativeReferenceSpec
    {
        [DataMember(Name = "reference_id")]
        public string ReferenceId { get; set; }

        [DataMember(Name = "semantic_name")]
        public string SemanticName { get; set; }

        [DataMember(Name = "entity_name")]
        public string EntityName { get; set; }

        [DataMember(Name = "entity_type")]
        public string EntityType { get; set; }

        [DataMember(Name = "selector")]
        public NativeReferenceSelector Selector { get; set; }
    }

    [DataContract]
    public sealed class NativeReferenceSelector
    {
        [DataMember(Name = "kind")]
        public string Kind { get; set; }

        [DataMember(Name = "direction")]
        public double[] Direction { get; set; }

        [DataMember(Name = "center_mm")]
        public double[] CenterMillimeters { get; set; }

        [DataMember(Name = "area_mm2")]
        public double? AreaSquareMillimeters { get; set; }
    }

    internal sealed class NativeSketchResult
    {
        public Feature SketchFeature { get; set; }
        public Sketch Sketch { get; set; }
        public SketchSegment RevolveAxis { get; set; }
        public SketchPoint[] FeaturePoints { get; set; }
    }

    [DataContract]
    public sealed class ReplayResult
    {
        [DataMember(Name = "status")]
        public string Status { get; set; }

        [DataMember(Name = "output_path")]
        public string OutputPath { get; set; }

        [DataMember(Name = "native_features")]
        public string[] NativeFeatures { get; set; }

        [DataMember(Name = "feature_count")]
        public int FeatureCount { get; set; }

        [DataMember(Name = "verification_passed")]
        public bool VerificationPassed { get; set; }

        [DataMember(Name = "reopened")]
        public bool Reopened { get; set; }

        [DataMember(Name = "verified_dimension_count")]
        public int VerifiedDimensionCount { get; set; }

        [DataMember(Name = "declared_parameter_count")]
        public int DeclaredParameterCount { get; set; }

        [DataMember(Name = "verified_parameter_count")]
        public int VerifiedParameterCount { get; set; }

        [DataMember(Name = "verified_parameter_ids")]
        public string[] VerifiedParameterIds { get; set; }

        [DataMember(Name = "declared_helper_count")]
        public int DeclaredHelperCount { get; set; }

        [DataMember(Name = "verified_helper_count")]
        public int VerifiedHelperCount { get; set; }

        [DataMember(Name = "verified_helper_names")]
        public string[] VerifiedHelperNames { get; set; }

        [DataMember(Name = "health")]
        public NativeHealthResult Health { get; set; }

        [DataMember(Name = "geometry")]
        public NativeGeometryResult Geometry { get; set; }

        [DataMember(Name = "published_references")]
        public PersistentReferenceResult[] PublishedReferences { get; set; }
    }

    [DataContract]
    public sealed class NativeGeometryResult
    {
        [DataMember(Name = "solid_body_count")]
        public int SolidBodyCount { get; set; }

        [DataMember(Name = "volume_mm3")]
        public double VolumeCubicMillimeters { get; set; }

        [DataMember(Name = "surface_area_mm2")]
        public double SurfaceAreaSquareMillimeters { get; set; }

        [DataMember(Name = "center_of_mass_mm")]
        public double[] CenterOfMassMillimeters { get; set; }

        [DataMember(Name = "bounding_box_mm")]
        public double[] BoundingBoxMillimeters { get; set; }
    }

    [DataContract]
    public sealed class EditabilityResult
    {
        [DataMember(Name = "status")]
        public string Status { get; set; }

        [DataMember(Name = "source_path")]
        public string SourcePath { get; set; }

        [DataMember(Name = "output_path")]
        public string OutputPath { get; set; }

        [DataMember(Name = "mutation_count")]
        public int MutationCount { get; set; }

        [DataMember(Name = "mutated_parameter_ids")]
        public string[] MutatedParameterIds { get; set; }

        [DataMember(Name = "reopened")]
        public bool Reopened { get; set; }

        [DataMember(Name = "declared_parameter_count")]
        public int DeclaredParameterCount { get; set; }

        [DataMember(Name = "verified_parameter_count")]
        public int VerifiedParameterCount { get; set; }

        [DataMember(Name = "verified_parameter_ids")]
        public string[] VerifiedParameterIds { get; set; }

        [DataMember(Name = "declared_helper_count")]
        public int DeclaredHelperCount { get; set; }

        [DataMember(Name = "verified_helper_count")]
        public int VerifiedHelperCount { get; set; }

        [DataMember(Name = "verified_helper_names")]
        public string[] VerifiedHelperNames { get; set; }

        [DataMember(Name = "before_geometry")]
        public NativeGeometryResult BeforeGeometry { get; set; }

        [DataMember(Name = "after_geometry")]
        public NativeGeometryResult AfterGeometry { get; set; }

        [DataMember(Name = "health")]
        public NativeHealthResult Health { get; set; }

        [DataMember(Name = "published_references")]
        public PersistentReferenceResult[] PublishedReferences { get; set; }
    }

    [DataContract]
    public sealed class PersistentReferenceResult
    {
        [DataMember(Name = "reference_id")]
        public string ReferenceId { get; set; }

        [DataMember(Name = "entity_name")]
        public string EntityName { get; set; }

        [DataMember(Name = "entity_type")]
        public string EntityType { get; set; }

        [DataMember(Name = "persistent_id_base64")]
        public string PersistentIdBase64 { get; set; }

        [DataMember(Name = "resolved")]
        public bool Resolved { get; set; }

        [DataMember(Name = "resolution_error_code")]
        public int ResolutionErrorCode { get; set; }
    }

    [DataContract]
    public sealed class NativeHealthResult
    {
        [DataMember(Name = "features")]
        public FeatureHealthResult[] Features { get; set; }

        [DataMember(Name = "sketches")]
        public SketchHealthResult[] Sketches { get; set; }

        [DataMember(Name = "feature_error_count")]
        public int FeatureErrorCount { get; set; }

        [DataMember(Name = "feature_warning_count")]
        public int FeatureWarningCount { get; set; }

        [DataMember(Name = "fully_defined_sketch_count")]
        public int FullyDefinedSketchCount { get; set; }

        [DataMember(Name = "under_defined_sketch_count")]
        public int UnderDefinedSketchCount { get; set; }
    }

    [DataContract]
    public sealed class FeatureHealthResult
    {
        [DataMember(Name = "feature_name")]
        public string FeatureName { get; set; }

        [DataMember(Name = "error_code")]
        public int ErrorCode { get; set; }

        [DataMember(Name = "is_warning")]
        public bool IsWarning { get; set; }

        [DataMember(Name = "status")]
        public string Status { get; set; }
    }

    [DataContract]
    public sealed class SketchHealthResult
    {
        [DataMember(Name = "sketch_name")]
        public string SketchName { get; set; }

        [DataMember(Name = "constraint_code")]
        public int ConstraintCode { get; set; }

        [DataMember(Name = "constraint_status")]
        public string ConstraintStatus { get; set; }

        [DataMember(Name = "is_valid")]
        public bool IsValid { get; set; }

        [DataMember(Name = "constraint_strategy")]
        public string ConstraintStrategy { get; set; }

        [DataMember(Name = "fully_defined_required")]
        public bool FullyDefinedRequired { get; set; }
    }

    public static class NativeReplayRunner
    {
        private const double MillimetersPerMeter = 1000.0;
        private const string ReplayFormat = "prompt2cad.solidworks-replay-plan";
        private const int ReplayVersion = 10;
        private static string tracePath;

        public static int ValidatePlanFile(string planPath)
        {
            ReplayPlan plan = ReadPlan(planPath);
            ValidateReplayPlan(plan);
            return plan.Features.Length;
        }

        public static string Execute(
            string planPath,
            string outputPath,
            string templatePath,
            bool visible)
        {
            tracePath = Path.GetFullPath(outputPath) + ".replay.log";
            if (File.Exists(tracePath))
            {
                File.Delete(tracePath);
            }
            Trace("Reading replay plan");
            ReplayPlan plan = ReadPlan(planPath);
            ValidateReplayPlan(plan);

            string resolvedOutput = PrepareNewOutputPath(outputPath);
            string stagedOutput = CreateStagedOutputPath(resolvedOutput);

            SldWorks application = null;
            bool startedApplication = false;
            ModelDoc2 model = null;
            string modelTitle = null;
            bool? originalInputDimensionPreference = null;

            try
            {
                Type applicationType = Type.GetTypeFromProgID("SldWorks.Application");
                if (applicationType == null)
                {
                    throw new InvalidOperationException(
                        "SOLIDWORKS is not registered as a Windows COM application."
                    );
                }

                try
                {
                    application = (SldWorks)Marshal.GetActiveObject(
                        "SldWorks.Application"
                    );
                    Trace("Attached to running SOLIDWORKS instance");
                }
                catch (COMException)
                {
                    Trace("Starting SOLIDWORKS");
                    application = (SldWorks)Activator.CreateInstance(applicationType);
                    startedApplication = true;
                }
                if (visible)
                {
                    application.Visible = true;
                }
                int inputDimensionPreference =
                    (int)swUserPreferenceToggle_e.swInputDimValOnCreate;
                originalInputDimensionPreference =
                    application.GetUserPreferenceToggle(inputDimensionPreference);
                application.SetUserPreferenceToggle(inputDimensionPreference, false);
                Trace("Disabled interactive dimension-value prompts");

                Trace("Resolving part template");
                string resolvedTemplate = ResolvePartTemplate(application, templatePath);
                Trace("Creating part document from " + resolvedTemplate);
                object modelObject = application.NewDocument(
                    resolvedTemplate,
                    0,
                    0.0,
                    0.0
                );
                if (modelObject == null)
                {
                    throw new InvalidOperationException(
                        "SOLIDWORKS could not create a part from '" + resolvedTemplate + "'."
                    );
                }

                model = (ModelDoc2)modelObject;
                PartDoc part = (PartDoc)modelObject;
                modelTitle = model.GetTitle();

                var createdNames = new List<string>();
                foreach (ReplayStep step in plan.Features)
                {
                    try
                    {
                        Feature nativeFeature;
                        if (step.Feature.Kind == "edge_chamfer" ||
                            step.Feature.Kind == "edge_fillet")
                        {
                            Trace("Creating edge treatment " + step.FeatureName);
                            nativeFeature = CreateNativeEdgeTreatment(model, step);
                        }
                        else
                        {
                            Trace("Creating sketch " + step.SketchName);
                            NativeSketchResult nativeSketch = CreateNativeSketch(
                                application,
                                model,
                                part,
                                step
                            );
                            if (step.Feature.Kind == "countersink")
                            {
                                Trace("Creating countersink " + step.FeatureName);
                                nativeFeature = CreateNativeCountersink(
                                    model,
                                    step,
                                    nativeSketch
                                );
                                if (step.Pattern != null)
                                {
                                    Trace(
                                        "Creating native pattern " +
                                        step.FeatureName
                                    );
                                    nativeFeature = CreateNativePattern(
                                        application,
                                        model,
                                        part,
                                        step,
                                        nativeFeature
                                    );
                                }
                            }
                            else
                            {
                                Trace("Creating feature " + step.FeatureName);
                                nativeFeature = CreateNativeFeature(
                                    model,
                                    step,
                                    nativeSketch
                                );
                                if (step.Pattern != null)
                                {
                                    Trace("Creating native pattern " + step.FeatureName);
                                    nativeFeature = CreateNativePattern(
                                        application,
                                        model,
                                        part,
                                        step,
                                        nativeFeature
                                    );
                                }
                            }
                        }
                        if (step.PublishReferences != null &&
                            step.PublishReferences.Length > 0)
                        {
                            Trace("Publishing native references for " + step.FeatureName);
                            PublishNativeReferences(
                                part,
                                nativeFeature,
                                step
                            );
                        }
                        createdNames.Add(nativeFeature.Name);
                    }
                    catch (Exception error)
                    {
                        throw new InvalidOperationException(
                            "Native replay failed for feature '" + step.Id + "': " +
                            error.Message,
                            error
                        );
                    }
                }

                Trace("Verifying native feature history and dimensions");
                ParameterVerificationResult parameterVerification =
                    VerifyReplay(model, part, plan);
                Trace("Checking native feature and sketch health");
                NativeHealthResult health = InspectNativeHealth(model, plan);
                RequireHealthyModel(health, "before saving");
                Trace("Saving native part");
                int saveStatus = model.SaveAs3(
                    stagedOutput,
                    (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                    (int)swSaveAsOptions_e.swSaveAsOptions_Silent
                );
                if (saveStatus != 0 || !File.Exists(stagedOutput))
                {
                    throw new InvalidOperationException(
                        "SOLIDWORKS failed to save staged output '" + stagedOutput +
                        "' (status " + saveStatus + ")."
                    );
                }
                modelTitle = model.GetTitle();
                IDictionary<string, byte[]> persistentReferenceIds =
                    CapturePersistentReferenceIds(model, part, plan);

                Trace("Closing and reopening the staged native part");
                application.CloseDoc(modelTitle);
                ReleaseComObject(model);
                model = null;
                modelTitle = null;

                model = OpenNativePart(application, stagedOutput);
                modelTitle = model.GetTitle();
                part = (PartDoc)model;
                Trace("Verifying reopened feature history and dimensions");
                parameterVerification = VerifyReplay(model, part, plan);
                health = InspectNativeHealth(model, plan);
                RequireHealthyModel(health, "after reopening");
                PersistentReferenceResult[] publishedReferences =
                    VerifyPersistentReferenceIds(
                        model,
                        part,
                        plan,
                        persistentReferenceIds
                    );

                Trace("Replay complete");
                NativeGeometryResult geometry = MeasureNativeGeometry(part);
                application.CloseDoc(modelTitle);
                ReleaseComObject(model);
                model = null;
                modelTitle = null;
                PublishStagedOutput(stagedOutput, resolvedOutput);
                stagedOutput = null;
                string resultJson = WriteJson(
                    new ReplayResult
                    {
                        Status = "success",
                        OutputPath = resolvedOutput,
                        NativeFeatures = createdNames.ToArray(),
                        FeatureCount = createdNames.Count,
                        VerificationPassed = true,
                        Reopened = true,
                        VerifiedDimensionCount =
                            parameterVerification.VerifiedDimensionCount,
                        DeclaredParameterCount =
                            parameterVerification.DeclaredParameterCount,
                        VerifiedParameterCount =
                            parameterVerification.VerifiedParameterCount,
                        VerifiedParameterIds =
                            parameterVerification.VerifiedParameterIds,
                        DeclaredHelperCount =
                            parameterVerification.DeclaredHelperCount,
                        VerifiedHelperCount =
                            parameterVerification.VerifiedHelperCount,
                        VerifiedHelperNames =
                            parameterVerification.VerifiedHelperNames,
                        Health = health,
                        Geometry = geometry,
                        PublishedReferences = publishedReferences,
                    }
                );
                if (!String.Equals(
                    System.Environment.GetEnvironmentVariable(
                        "P2P_KEEP_SOLIDWORKS_TRACE"
                    ),
                    "1",
                    StringComparison.Ordinal))
                {
                    TryDeleteTrace();
                }
                return resultJson;
            }
            finally
            {
                if (application != null && originalInputDimensionPreference.HasValue)
                {
                    try
                    {
                        application.SetUserPreferenceToggle(
                            (int)swUserPreferenceToggle_e.swInputDimValOnCreate,
                            originalInputDimensionPreference.Value
                        );
                    }
                    catch
                    {
                    }
                }
                if (model != null && application != null &&
                    !String.IsNullOrWhiteSpace(modelTitle))
                {
                    try
                    {
                        application.CloseDoc(modelTitle);
                    }
                    catch
                    {
                    }
                }
                if (startedApplication && application != null)
                {
                    try
                    {
                        application.ExitApp();
                    }
                    catch
                    {
                    }
                }

                ReleaseComObject(model);
                ReleaseComObject(application);
                TryDeleteFile(stagedOutput);
            }
        }

        public static string VerifyEditablePart(
            string planPath,
            string sourcePath,
            string outputPath,
            string mutationPath,
            bool visible)
        {
            ReplayPlan plan = ReadPlan(planPath);
            ValidateReplayPlan(plan);
            MutationDocument mutationDocument = ReadMutations(mutationPath);
            if (!String.Equals(
                mutationDocument.Format,
                "prompt2cad.solidworks-mutations",
                StringComparison.Ordinal) || mutationDocument.Version != 1)
            {
                throw new InvalidOperationException(
                    "Unsupported SOLIDWORKS mutation document."
                );
            }
            ParameterMutation[] mutations =
                mutationDocument.Mutations ?? new ParameterMutation[0];
            if (mutations.Length == 0)
            {
                throw new InvalidOperationException(
                    "The mutation document contains no parameter changes."
                );
            }

            string resolvedSource = Path.GetFullPath(sourcePath);
            string resolvedOutput = PrepareNewOutputPath(outputPath);
            if (String.Equals(
                resolvedSource,
                resolvedOutput,
                StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidOperationException(
                    "Editability verification must save to a separate output part."
                );
            }
            string stagedOutput = CreateStagedOutputPath(resolvedOutput);
            if (!File.Exists(resolvedSource))
            {
                throw new FileNotFoundException(
                    "The source SOLIDWORKS part was not found.",
                    resolvedSource
                );
            }
            SldWorks application = null;
            bool startedApplication = false;
            ModelDoc2 model = null;
            string modelTitle = null;
            try
            {
                Type applicationType = Type.GetTypeFromProgID(
                    "SldWorks.Application"
                );
                if (applicationType == null)
                {
                    throw new InvalidOperationException(
                        "SOLIDWORKS is not registered as a Windows COM application."
                    );
                }
                try
                {
                    application = (SldWorks)Marshal.GetActiveObject(
                        "SldWorks.Application"
                    );
                }
                catch (COMException)
                {
                    application = (SldWorks)Activator.CreateInstance(applicationType);
                    startedApplication = true;
                }
                if (visible)
                {
                    application.Visible = true;
                }

                model = OpenNativePart(application, resolvedSource);
                modelTitle = model.GetTitle();
                PartDoc part = (PartDoc)model;
                NativeGeometryResult beforeGeometry = MeasureNativeGeometry(part);
                IDictionary<string, byte[]> persistentReferenceIds =
                    CapturePersistentReferenceIds(model, part, plan);

                ApplyParameterMutations(model, plan, mutations);
                if (!model.EditRebuild3())
                {
                    throw new InvalidOperationException(
                        "SOLIDWORKS rebuild failed after parameter mutation."
                    );
                }
                NativeHealthResult beforeSaveHealth = InspectNativeHealth(
                    model,
                    plan
                );
                RequireHealthyModel(beforeSaveHealth, "after mutation");

                int saveStatus = model.SaveAs3(
                    stagedOutput,
                    (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                    (int)swSaveAsOptions_e.swSaveAsOptions_Silent
                );
                if (saveStatus != 0 || !File.Exists(stagedOutput))
                {
                    throw new InvalidOperationException(
                        "SOLIDWORKS failed to save staged mutated part '" +
                        stagedOutput + "' (status " + saveStatus + ")."
                    );
                }

                application.CloseDoc(model.GetTitle());
                ReleaseComObject(model);
                model = null;
                modelTitle = null;

                model = OpenNativePart(application, stagedOutput);
                modelTitle = model.GetTitle();
                part = (PartDoc)model;
                ParameterVerificationResult verification = VerifyReplay(
                    model,
                    part,
                    plan
                );
                NativeHealthResult reopenedHealth = InspectNativeHealth(
                    model,
                    plan
                );
                RequireHealthyModel(reopenedHealth, "after reopening");
                NativeGeometryResult afterGeometry = MeasureNativeGeometry(part);
                PersistentReferenceResult[] publishedReferences =
                    VerifyPersistentReferenceIds(
                        model,
                        part,
                        plan,
                        persistentReferenceIds
                    );

                application.CloseDoc(modelTitle);
                ReleaseComObject(model);
                model = null;
                modelTitle = null;
                PublishStagedOutput(stagedOutput, resolvedOutput);
                stagedOutput = null;

                return WriteEditabilityJson(
                    new EditabilityResult
                    {
                        Status = "success",
                        SourcePath = resolvedSource,
                        OutputPath = resolvedOutput,
                        MutationCount = mutations.Length,
                        MutatedParameterIds = mutations
                            .Select(item => item.ParameterId)
                            .OrderBy(item => item, StringComparer.Ordinal)
                            .ToArray(),
                        Reopened = true,
                        DeclaredParameterCount =
                            verification.DeclaredParameterCount,
                        VerifiedParameterCount =
                            verification.VerifiedParameterCount,
                        VerifiedParameterIds = verification.VerifiedParameterIds,
                        DeclaredHelperCount =
                            verification.DeclaredHelperCount,
                        VerifiedHelperCount =
                            verification.VerifiedHelperCount,
                        VerifiedHelperNames = verification.VerifiedHelperNames,
                        BeforeGeometry = beforeGeometry,
                        AfterGeometry = afterGeometry,
                        Health = reopenedHealth,
                        PublishedReferences = publishedReferences,
                    }
                );
            }
            finally
            {
                if (model != null && application != null &&
                    !String.IsNullOrWhiteSpace(modelTitle))
                {
                    try
                    {
                        application.CloseDoc(modelTitle);
                    }
                    catch
                    {
                    }
                }
                if (startedApplication && application != null)
                {
                    try
                    {
                        application.ExitApp();
                    }
                    catch
                    {
                    }
                }
                ReleaseComObject(model);
                ReleaseComObject(application);
                TryDeleteFile(stagedOutput);
            }
        }

        private static string PrepareNewOutputPath(string outputPath)
        {
            string resolvedOutput = Path.GetFullPath(outputPath);
            if (!String.Equals(
                Path.GetExtension(resolvedOutput),
                ".SLDPRT",
                StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS output must use the .SLDPRT suffix."
                );
            }
            if (File.Exists(resolvedOutput))
            {
                throw new InvalidOperationException(
                    "Refusing to overwrite existing SOLIDWORKS output '" +
                    resolvedOutput + "'."
                );
            }
            string outputDirectory = Path.GetDirectoryName(resolvedOutput);
            if (!String.IsNullOrWhiteSpace(outputDirectory))
            {
                Directory.CreateDirectory(outputDirectory);
            }
            return resolvedOutput;
        }

        private static string CreateStagedOutputPath(string resolvedOutput)
        {
            string directory = Path.GetDirectoryName(resolvedOutput);
            string filename = Path.GetFileNameWithoutExtension(resolvedOutput);
            return Path.Combine(
                directory,
                filename + ".prompt2cad-" + Guid.NewGuid().ToString("N") +
                ".SLDPRT"
            );
        }

        private static void PublishStagedOutput(
            string stagedOutput,
            string resolvedOutput)
        {
            if (!File.Exists(stagedOutput))
            {
                throw new InvalidOperationException(
                    "Verified staged SOLIDWORKS output is missing."
                );
            }
            if (File.Exists(resolvedOutput))
            {
                throw new InvalidOperationException(
                    "Refusing to overwrite existing SOLIDWORKS output '" +
                    resolvedOutput + "'."
                );
            }
            File.Move(stagedOutput, resolvedOutput);
        }

        private static void TryDeleteFile(string path)
        {
            if (String.IsNullOrWhiteSpace(path))
            {
                return;
            }
            try
            {
                if (File.Exists(path))
                {
                    File.Delete(path);
                }
            }
            catch
            {
            }
        }

        private static ModelDoc2 OpenNativePart(
            SldWorks application,
            string path)
        {
            int errors = 0;
            int warnings = 0;
            ModelDoc2 model = application.OpenDoc6(
                path,
                (int)swDocumentTypes_e.swDocPART,
                (int)swOpenDocOptions_e.swOpenDocOptions_Silent,
                "",
                ref errors,
                ref warnings
            ) as ModelDoc2;
            if (model == null)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS could not open '" + path +
                    "' (error " + errors + ", warning " + warnings + ")."
                );
            }
            return model;
        }

        private static ReplayPlan ReadPlan(string path)
        {
            var serializer = new DataContractJsonSerializer(typeof(ReplayPlan));
            using (FileStream stream = File.OpenRead(path))
            {
                return (ReplayPlan)serializer.ReadObject(stream);
            }
        }

        private static void ValidateReplayPlan(ReplayPlan plan)
        {
            if (plan == null || plan.Format != ReplayFormat ||
                plan.Version != ReplayVersion)
            {
                throw new InvalidOperationException(
                    "Unsupported SOLIDWORKS replay plan format or version."
                );
            }
            if (plan.Features == null || plan.Features.Length == 0)
            {
                throw new InvalidOperationException(
                    "The replay plan has no features."
                );
            }
            var featureIds = new HashSet<string>(StringComparer.Ordinal);
            var nativeNames = new HashSet<string>(
                StringComparer.OrdinalIgnoreCase
            );
            var parameterIds = new HashSet<string>(StringComparer.Ordinal);
            var qualifiedParameterNames = new HashSet<string>(
                StringComparer.OrdinalIgnoreCase
            );
            var referenceIds = new HashSet<string>(StringComparer.Ordinal);
            var entityNames = new HashSet<string>(
                StringComparer.OrdinalIgnoreCase
            );
            foreach (ReplayStep step in plan.Features)
            {
                if (step == null || step.Feature == null)
                {
                    throw new InvalidOperationException(
                        "Every replay step must contain a native feature."
                    );
                }
                RequireUniqueValue(featureIds, step.Id, "feature ID");
                RequireUniqueValue(nativeNames, step.FeatureName, "native feature name");
                if (!String.IsNullOrWhiteSpace(step.SketchName))
                {
                    RequireUniqueValue(nativeNames, step.SketchName, "native sketch name");
                }
                if (step.Support != null && step.Support.Kind == "offset_plane")
                {
                    RequireUniqueValue(
                        nativeNames,
                        step.Support.Name,
                        "native offset-plane name"
                    );
                }
                if (step.Support != null &&
                    (step.Support.Kind == "datum_plane" ||
                     step.Support.Kind == "offset_plane") &&
                    DatumPlaneOrdinal(step.Support.SemanticPlane) == 0)
                {
                    throw new InvalidOperationException(
                        "Native datum support for feature '" + step.Id +
                        "' requires semantic plane XY, XZ, or YZ."
                    );
                }
                if (step.Pattern != null)
                {
                    RequireUniqueValue(
                        nativeNames,
                        step.Pattern.SeedFeatureName,
                        "native pattern seed name"
                    );
                    if (step.Pattern.Kind == "circular_pattern" ||
                        step.Pattern.Kind == "linear_pattern")
                    {
                        RequireUniqueValue(
                            nativeNames,
                            step.Pattern.ReferenceSketchName,
                            "native pattern reference-sketch name"
                        );
                    }
                    if (step.Pattern.Kind == "circular_pattern")
                    {
                        RequireUniqueValue(
                            nativeNames,
                            step.Pattern.AxisName,
                            "native circular-pattern axis name"
                        );
                    }
                    else if (step.Pattern.Kind == "mirror_pattern")
                    {
                        RequireUniqueValue(
                            nativeNames,
                            step.Pattern.PlacementSketchName,
                            "native mirror-placement sketch name"
                        );
                    }
                }
                if (step.Feature.Kind == "boss_revolve" ||
                    step.Feature.Kind == "cut_revolve")
                {
                    ValidateCanonicalRevolveAxis(step);
                }
            }
            foreach (ReplayStep step in plan.Features)
            {
                foreach (NativeParameterBinding binding in
                    step.ParameterBindings ?? new NativeParameterBinding[0])
                {
                    RequireUniqueValue(
                        parameterIds,
                        binding.ParameterId,
                        "native parameter ID"
                    );
                    if (String.IsNullOrWhiteSpace(binding.OwnerName) ||
                        !nativeNames.Contains(binding.OwnerName))
                    {
                        throw new InvalidOperationException(
                            "Native parameter '" + binding.ParameterId +
                            "' references unknown owner '" +
                            binding.OwnerName + "'."
                        );
                    }
                    RequireUniqueValue(
                        qualifiedParameterNames,
                        binding.NativeName + "@" + binding.OwnerName,
                        "qualified native parameter name"
                    );
                }
                foreach (NativeReferenceSpec reference in
                    step.PublishReferences ?? new NativeReferenceSpec[0])
                {
                    RequireUniqueValue(
                        referenceIds,
                        reference.ReferenceId,
                        "semantic reference ID"
                    );
                    RequireUniqueValue(
                        entityNames,
                        reference.EntityName,
                        "native entity name"
                    );
                }
            }
        }

        private static void RequireUniqueValue(
            ISet<string> values,
            string value,
            string label)
        {
            if (String.IsNullOrWhiteSpace(value))
            {
                throw new InvalidOperationException(label + " cannot be blank.");
            }
            if (!values.Add(value))
            {
                throw new InvalidOperationException(
                    "Replay plan contains duplicate " + label + " '" +
                    value + "'."
                );
            }
        }

        private static void ValidateCanonicalRevolveAxis(ReplayStep step)
        {
            FeatureSpec feature = step.Feature;
            RequireFinitePair(
                feature.AxisStartMillimeters,
                step.Id + " revolve axis start"
            );
            RequireFinitePair(
                feature.AxisEndMillimeters,
                step.Id + " revolve axis end"
            );
            CanonicalAxisSpec canonical = feature.CanonicalAxis;
            if (canonical == null || !String.Equals(
                canonical.Kind,
                "canonical_line_2d",
                StringComparison.Ordinal))
            {
                throw new InvalidOperationException(
                    "Revolve feature '" + step.Id +
                    "' is missing canonical axis metadata."
                );
            }
            RequireFinitePair(canonical.AnchorMillimeters, "canonical axis anchor");
            RequireFinitePair(canonical.Direction, "canonical axis direction");
            RequireFinitePair(canonical.Normal, "canonical axis normal");
            RequireFiniteValue(
                canonical.SignedOffsetMillimeters,
                "canonical axis signed offset"
            );
            RequireFiniteValue(
                canonical.DirectionAngleDegrees,
                "canonical axis direction angle"
            );

            double deltaX = feature.AxisEndMillimeters[0] -
                feature.AxisStartMillimeters[0];
            double deltaY = feature.AxisEndMillimeters[1] -
                feature.AxisStartMillimeters[1];
            double sourceSpan = Math.Sqrt(deltaX * deltaX + deltaY * deltaY);
            if (sourceSpan <= 1e-12)
            {
                throw new InvalidOperationException(
                    "Revolve feature '" + step.Id +
                    "' has coincident axis endpoints."
                );
            }
            double directionX = deltaX / sourceSpan;
            double directionY = deltaY / sourceSpan;
            if (directionX < -1e-12 ||
                (Math.Abs(directionX) <= 1e-12 && directionY < 0.0))
            {
                directionX *= -1.0;
                directionY *= -1.0;
            }
            double normalX = -directionY;
            double normalY = directionX;
            double signedOffset = feature.AxisStartMillimeters[0] * normalX +
                feature.AxisStartMillimeters[1] * normalY;
            double anchorX = normalX * signedOffset;
            double anchorY = normalY * signedOffset;
            double directionAngle = Math.Atan2(directionY, directionX) *
                180.0 / Math.PI;

            RequireNear(canonical.Direction[0], directionX, "axis direction X");
            RequireNear(canonical.Direction[1], directionY, "axis direction Y");
            RequireNear(canonical.Normal[0], normalX, "axis normal X");
            RequireNear(canonical.Normal[1], normalY, "axis normal Y");
            RequireNear(canonical.AnchorMillimeters[0], anchorX, "axis anchor X");
            RequireNear(canonical.AnchorMillimeters[1], anchorY, "axis anchor Y");
            RequireNear(
                canonical.SignedOffsetMillimeters,
                signedOffset,
                "axis signed offset"
            );
            RequireNear(
                canonical.DirectionAngleDegrees,
                directionAngle,
                "axis direction angle"
            );
            if (canonical.AutomatedMutation || !String.Equals(
                canonical.EditStrategy,
                "edit_native_construction_line_or_regenerate",
                StringComparison.Ordinal))
            {
                throw new InvalidOperationException(
                    "Revolve feature '" + step.Id +
                    "' declares an unsupported canonical-axis edit strategy."
                );
            }
        }

        private static void RequireFinitePair(double[] values, string label)
        {
            if (values == null || values.Length != 2)
            {
                throw new InvalidOperationException(
                    label + " must contain exactly two values."
                );
            }
            RequireFiniteValue(values[0], label + " X");
            RequireFiniteValue(values[1], label + " Y");
        }

        private static void RequireFiniteValue(double value, string label)
        {
            if (Double.IsNaN(value) || Double.IsInfinity(value))
            {
                throw new InvalidOperationException(label + " must be finite.");
            }
        }

        private static void RequireNear(
            double actual,
            double expected,
            string label)
        {
            double tolerance = 1e-8 * Math.Max(1.0, Math.Abs(expected));
            if (Math.Abs(actual - expected) > tolerance)
            {
                throw new InvalidOperationException(
                    "Canonical " + label + " does not match the source endpoints."
                );
            }
        }

        private static MutationDocument ReadMutations(string path)
        {
            var serializer = new DataContractJsonSerializer(
                typeof(MutationDocument)
            );
            using (FileStream stream = File.OpenRead(path))
            {
                return (MutationDocument)serializer.ReadObject(stream);
            }
        }

        private static string WriteJson(ReplayResult result)
        {
            var serializer = new DataContractJsonSerializer(typeof(ReplayResult));
            using (var stream = new MemoryStream())
            {
                serializer.WriteObject(stream, result);
                return System.Text.Encoding.UTF8.GetString(stream.ToArray());
            }
        }

        private static string WriteEditabilityJson(EditabilityResult result)
        {
            var serializer = new DataContractJsonSerializer(
                typeof(EditabilityResult)
            );
            using (var stream = new MemoryStream())
            {
                serializer.WriteObject(stream, result);
                return System.Text.Encoding.UTF8.GetString(stream.ToArray());
            }
        }

        private static NativeGeometryResult MeasureNativeGeometry(PartDoc part)
        {
            object[] bodyObjects = ObjectItems(part.GetBodies2(
                (int)swBodyType_e.swSolidBody,
                true
            )).ToArray();
            if (bodyObjects.Length == 0)
            {
                throw new InvalidOperationException(
                    "The native part contains no visible solid body."
                );
            }

            double volumeCubicMeters = 0.0;
            double surfaceAreaSquareMeters = 0.0;
            double[] volumeWeightedCenter = new double[3];
            double[] boundingBox = null;
            foreach (object bodyObject in bodyObjects)
            {
                Body2 body = bodyObject as Body2;
                if (body == null)
                {
                    continue;
                }
                double[] massProperties = ObjectItems(
                    body.GetMassProperties(1.0)
                ).Select(value => Convert.ToDouble(
                    value,
                    CultureInfo.InvariantCulture
                )).ToArray();
                if (massProperties.Length < 5)
                {
                    throw new InvalidOperationException(
                        "SOLIDWORKS did not return solid-body mass properties."
                    );
                }
                double bodyVolume = massProperties[3];
                if (Double.IsNaN(bodyVolume) ||
                    Double.IsInfinity(bodyVolume) || bodyVolume <= 0.0)
                {
                    throw new InvalidOperationException(
                        "SOLIDWORKS returned an invalid solid-body volume."
                    );
                }
                volumeCubicMeters += bodyVolume;
                surfaceAreaSquareMeters += massProperties[4];
                for (int axis = 0; axis < 3; axis++)
                {
                    volumeWeightedCenter[axis] +=
                        massProperties[axis] * bodyVolume;
                }
                double[] bodyBox = ObjectItems(body.GetBodyBox())
                    .Select(value => Convert.ToDouble(
                        value,
                        CultureInfo.InvariantCulture
                    ) * MillimetersPerMeter)
                    .ToArray();
                if (bodyBox.Length != 6)
                {
                    throw new InvalidOperationException(
                        "SOLIDWORKS did not return a six-value solid-body " +
                        "bounding box."
                    );
                }
                if (boundingBox == null)
                {
                    boundingBox = bodyBox;
                }
                else
                {
                    boundingBox[0] = Math.Min(boundingBox[0], bodyBox[0]);
                    boundingBox[1] = Math.Min(boundingBox[1], bodyBox[1]);
                    boundingBox[2] = Math.Min(boundingBox[2], bodyBox[2]);
                    boundingBox[3] = Math.Max(boundingBox[3], bodyBox[3]);
                    boundingBox[4] = Math.Max(boundingBox[4], bodyBox[4]);
                    boundingBox[5] = Math.Max(boundingBox[5], bodyBox[5]);
                }
            }
            if (boundingBox == null)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS did not return a solid-body bounding box."
                );
            }
            if (volumeCubicMeters <= 0.0 ||
                Double.IsNaN(surfaceAreaSquareMeters) ||
                Double.IsInfinity(surfaceAreaSquareMeters) ||
                surfaceAreaSquareMeters <= 0.0)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS returned invalid aggregate mass properties."
                );
            }
            return new NativeGeometryResult
            {
                SolidBodyCount = bodyObjects.Length,
                VolumeCubicMillimeters =
                    volumeCubicMeters * Math.Pow(MillimetersPerMeter, 3),
                SurfaceAreaSquareMillimeters =
                    surfaceAreaSquareMeters *
                    Math.Pow(MillimetersPerMeter, 2),
                CenterOfMassMillimeters = new[]
                {
                    volumeWeightedCenter[0] / volumeCubicMeters *
                        MillimetersPerMeter,
                    volumeWeightedCenter[1] / volumeCubicMeters *
                        MillimetersPerMeter,
                    volumeWeightedCenter[2] / volumeCubicMeters *
                        MillimetersPerMeter,
                },
                BoundingBoxMillimeters = boundingBox,
            };
        }

        private static string ResolvePartTemplate(
            SldWorks application,
            string requestedTemplate)
        {
            if (!String.IsNullOrWhiteSpace(requestedTemplate))
            {
                string resolvedRequested = Path.GetFullPath(requestedTemplate);
                if (!File.Exists(resolvedRequested))
                {
                    throw new FileNotFoundException(
                        "The requested SOLIDWORKS part template was not found.",
                        resolvedRequested
                    );
                }
                return resolvedRequested;
            }

            try
            {
                string configured = application.GetUserPreferenceStringValue(
                    (int)swUserPreferenceStringValue_e.swDefaultTemplatePart
                );
                if (!String.IsNullOrWhiteSpace(configured) && File.Exists(configured))
                {
                    return configured;
                }
            }
            catch
            {
            }

            try
            {
                string discovered = application.GetDocumentTemplate(
                    (int)swDocumentTypes_e.swDocPART,
                    "",
                    0,
                    0.0,
                    0.0
                );
                if (!String.IsNullOrWhiteSpace(discovered) &&
                    File.Exists(discovered))
                {
                    Trace(
                        "Resolved part template through the SOLIDWORKS " +
                        "document-template API"
                    );
                    return discovered;
                }
            }
            catch
            {
            }

            string root = Path.Combine(
                System.Environment.GetFolderPath(
                    System.Environment.SpecialFolder.CommonApplicationData
                ),
                "SOLIDWORKS"
            );
            if (Directory.Exists(root))
            {
                string fallback = Directory.GetDirectories(root, "SOLIDWORKS *")
                    .Select(directory => Path.Combine(directory, "templates", "Part.PRTDOT"))
                    .Where(File.Exists)
                    .OrderByDescending(File.GetLastWriteTimeUtc)
                    .FirstOrDefault();
                if (!String.IsNullOrWhiteSpace(fallback))
                {
                    return fallback;
                }
            }

            throw new InvalidOperationException(
                "A valid SOLIDWORKS part template is required."
            );
        }

        private static NativeSketchResult CreateNativeSketch(
            SldWorks application,
            ModelDoc2 model,
            PartDoc part,
            ReplayStep step)
        {
            Trace("Selecting support for " + step.SketchName);
            SelectSketchSupport(application, model, part, step.Support);
            SketchManager sketchManager = model.SketchManager;
            Trace("Entering sketch " + step.SketchName);
            sketchManager.InsertSketch(true);

            object activeSketch = model.GetActiveSketch2();
            if (activeSketch == null)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS did not enter sketch '" + step.SketchName + "'."
                );
            }
            Feature sketchFeature = (Feature)activeSketch;
            sketchFeature.Name = step.SketchName;
            Trace("Named active sketch " + step.SketchName);

            Sketch sketchDefinition = model.IGetActiveSketch2();
            if (sketchDefinition == null)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS did not expose the active sketch transform."
                );
            }
            MathUtility mathUtility = application.IGetMathUtility();
            MathTransform modelToSketch = sketchDefinition.ModelToSketchTransform;

            SketchPoint[] featurePoints;
            bool previousAddToDatabase = sketchManager.AddToDB;
            try
            {
                // Native replay must preserve the coordinates in the replay plan.
                // Direct database insertion disables interactive inference and
                // snapping that can otherwise move an offset profile to the
                // sketch origin on a side face.
                sketchManager.AddToDB = true;
                featurePoints = CreateProfileInstances(
                    model,
                    sketchManager,
                    step,
                    mathUtility,
                    modelToSketch
                );
            }
            finally
            {
                sketchManager.AddToDB = previousAddToDatabase;
            }

            SketchSegment revolveAxis = null;
            if (step.Feature.Kind == "boss_revolve" ||
                step.Feature.Kind == "cut_revolve")
            {
                double[] axisStart = ToSketchPoint(
                    step.Support.Frame,
                    step.Feature.AxisStartMillimeters,
                    mathUtility,
                    modelToSketch
                );
                double[] axisEnd = ToSketchPoint(
                    step.Support.Frame,
                    step.Feature.AxisEndMillimeters,
                    mathUtility,
                    modelToSketch
                );
                revolveAxis = FindCoincidentAxisSegment(
                    sketchDefinition,
                    axisStart,
                    axisEnd
                );
                if (revolveAxis == null)
                {
                    revolveAxis = sketchManager.CreateLine(
                        axisStart[0], axisStart[1], axisStart[2],
                        axisEnd[0], axisEnd[1], axisEnd[2]
                    );
                    if (revolveAxis != null)
                    {
                        revolveAxis.ConstructionGeometry = true;
                    }
                }
                if (revolveAxis == null)
                {
                    throw new InvalidOperationException(
                        "SOLIDWORKS did not create the revolve axis."
                    );
                }
            }

            CompleteRemainingSketchDefinition(
                model,
                sketchManager,
                sketchDefinition,
                step
            );

            Trace("Exiting sketch " + step.SketchName);
            sketchManager.InsertSketch(true);
            Trace("Selecting sketch " + step.SketchName + " for feature creation");
            model.ClearSelection2(true);
            if (!sketchFeature.Select2(false, 0))
            {
                throw new InvalidOperationException(
                    "Could not select sketch '" + step.SketchName + "'."
                );
            }
            return new NativeSketchResult
            {
                SketchFeature = sketchFeature,
                Sketch = sketchDefinition,
                RevolveAxis = revolveAxis,
                FeaturePoints = featurePoints,
            };
        }

        private static void CompleteRemainingSketchDefinition(
            ModelDoc2 model,
            SketchManager sketchManager,
            Sketch sketch,
            ReplayStep step)
        {
            SketchConstraintPlan plan = step.Sketch == null
                ? null
                : step.Sketch.ConstraintPlan;
            if (plan == null || !String.Equals(
                plan.Strategy,
                "complete_remaining_degrees_of_freedom",
                StringComparison.Ordinal))
            {
                return;
            }
            int initialStatus = sketch.GetConstrainedStatus();
            if (initialStatus ==
                (int)swConstrainedStatus_e.swFullyConstrained)
            {
                return;
            }
            if (initialStatus ==
                    (int)swConstrainedStatus_e.swOverConstrained ||
                initialStatus ==
                    (int)swConstrainedStatus_e.swNoSolution ||
                initialStatus ==
                    (int)swConstrainedStatus_e.swInvalidSolution)
            {
                throw new InvalidOperationException(
                    "Sketch '" + step.SketchName +
                    "' is invalid before constraint completion (" +
                    ConstraintStatusName(initialStatus) + ")."
                );
            }

            int relationMask = 0;
            foreach (string relation in plan.Relations ?? new string[0])
            {
                relationMask |= FullyDefineRelationValue(relation);
            }
            int horizontalScheme = String.Equals(
                plan.HorizontalDimensionScheme,
                "baseline",
                StringComparison.OrdinalIgnoreCase
            ) ? 1 : 0;
            int verticalScheme = String.Equals(
                plan.VerticalDimensionScheme,
                "baseline",
                StringComparison.OrdinalIgnoreCase
            ) ? 1 : 0;
            model.ClearSelection2(true);
            const int horizontalDatumMark = 2;
            const int verticalDatumMark = 4;
            bool selectedOriginDatum = model.Extension.SelectByID2(
                "Point1@Origin",
                "EXTSKETCHPOINT",
                0.0,
                0.0,
                0.0,
                false,
                horizontalDatumMark | verticalDatumMark,
                null,
                0
            );
            if (!selectedOriginDatum)
            {
                throw new InvalidOperationException(
                    "Sketch '" + step.SketchName +
                    "' could not select the model origin as its generalized " +
                    "horizontal and vertical dimension datum."
                );
            }
            sketchManager.FullyDefineSketch(
                true,
                true,
                relationMask,
                true,
                horizontalScheme,
                null,
                verticalScheme,
                null,
                1,
                1
            );
            int finalStatus = sketch.GetConstrainedStatus();
            if (plan.RequireFullyDefined && finalStatus !=
                (int)swConstrainedStatus_e.swFullyConstrained)
            {
                throw new InvalidOperationException(
                    "Sketch '" + step.SketchName +
                    "' remained " + ConstraintStatusName(finalStatus) +
                    " after generalized constraint completion."
                );
            }
        }

        private static int FullyDefineRelationValue(string relation)
        {
            switch (relation)
            {
                case "coincident":
                    return (int)swSketchFullyDefineRelationType_e
                        .swSketchFullyDefineRelationType_Coincident;
                case "horizontal":
                    return (int)swSketchFullyDefineRelationType_e
                        .swSketchFullyDefineRelationType_Horizontal;
                case "vertical":
                    return (int)swSketchFullyDefineRelationType_e
                        .swSketchFullyDefineRelationType_Vertical;
                case "collinear":
                    return (int)swSketchFullyDefineRelationType_e
                        .swSketchFullyDefineRelationType_Colinear;
                case "concentric":
                    return (int)swSketchFullyDefineRelationType_e
                        .swSketchFullyDefineRelationType_Concentric;
                case "equal":
                    return (int)swSketchFullyDefineRelationType_e
                        .swSketchFullyDefineRelationType_Equal;
                case "parallel":
                    return (int)swSketchFullyDefineRelationType_e
                        .swSketchFullyDefineRelationType_Parallel;
                case "perpendicular":
                    return (int)swSketchFullyDefineRelationType_e
                        .swSketchFullyDefineRelationType_Perpendicular;
                case "tangent":
                    return (int)swSketchFullyDefineRelationType_e
                        .swSketchFullyDefineRelationType_Tangent;
                case "midpoint":
                    return (int)swSketchFullyDefineRelationType_e
                        .swSketchFullyDefineRelationType_Midpoint;
                default:
                    throw new InvalidOperationException(
                        "Unsupported generalized sketch relation '" +
                        relation + "'."
                    );
            }
        }

        private static void SelectSketchSupport(
            SldWorks application,
            ModelDoc2 model,
            PartDoc part,
            SketchSupport support)
        {
            model.ClearSelection2(true);
            if (support.Kind == "datum_plane")
            {
                bool selected = SelectDatumPlane(
                    model,
                    support.Name,
                    support.SemanticPlane
                );
                if (!selected)
                {
                    throw new InvalidOperationException(
                        "Could not select datum plane '" + support.Name +
                        "' for semantic plane '" + support.SemanticPlane + "'."
                    );
                }
                return;
            }
            if (support.Kind == "offset_plane")
            {
                SelectOrCreateOffsetPlane(application, model, support);
                return;
            }
            if (support.Kind == "resolved_feature_face")
            {
                Feature parentFeature = FindFeatureByName(
                    model,
                    support.TargetFeatureName
                );
                if (parentFeature == null)
                {
                    throw new InvalidOperationException(
                        "Pattern parent feature '" + support.TargetFeatureName +
                        "' was not found."
                    );
                }
                Face2 resolvedFace = FindPlanarFaceNearFrame(
                    parentFeature,
                    support.Frame
                );
                if (resolvedFace == null)
                {
                    throw new InvalidOperationException(
                        "Could not resolve patterned face '" +
                        support.EntityName + "'."
                    );
                }
                part.SetEntityName(resolvedFace, support.EntityName);
                if (!((Entity)resolvedFace).Select4(false, null))
                {
                    throw new InvalidOperationException(
                        "Resolved patterned face could not be selected."
                    );
                }
                return;
            }
            if (support.Kind != "named_face")
            {
                throw new InvalidOperationException(
                    "Unsupported sketch support '" + support.Kind + "'."
                );
            }

            object faceObject = part.GetEntityByName(
                support.EntityName,
                (int)swSelectType_e.swSelFACES
            );
            if (faceObject == null)
            {
                throw new InvalidOperationException(
                    "Named support face '" + support.EntityName + "' was not found."
                );
            }
            Entity entity = (Entity)faceObject;
            Face2 face = (Face2)faceObject;
            if (!entity.Select4(false, null))
            {
                throw new InvalidOperationException(
                    "Named support face '" + support.EntityName + "' could not be selected."
                );
            }
        }

        private static void SelectOrCreateOffsetPlane(
            SldWorks application,
            ModelDoc2 model,
            SketchSupport support)
        {
            bool selectedExisting = model.Extension.SelectByID2(
                support.Name,
                "PLANE",
                0.0,
                0.0,
                0.0,
                false,
                0,
                null,
                0
            );
            if (selectedExisting)
            {
                Feature existingPlane = FindFeatureByName(model, support.Name);
                ValidateOffsetPlaneTransform(
                    application,
                    existingPlane,
                    support
                );
                return;
            }
            if (String.IsNullOrWhiteSpace(support.DatumName) ||
                support.OffsetMillimeters <= 0.0)
            {
                throw new InvalidOperationException(
                    "Offset-plane support requires a datum name and a " +
                    "positive offset."
                );
            }

            bool selectedDatum = SelectDatumPlane(
                model,
                support.DatumName,
                support.SemanticPlane
            );
            if (!selectedDatum)
            {
                throw new InvalidOperationException(
                    "Could not select offset-plane datum '" +
                    support.DatumName + "'."
                );
            }

            int constraint = (int)swRefPlaneReferenceConstraints_e
                .swRefPlaneReferenceConstraint_Distance;
            if (support.FlipOffset)
            {
                constraint |= (int)swRefPlaneReferenceConstraints_e
                    .swRefPlaneReferenceConstraint_OptionFlip;
            }
            object createdPlane = model.FeatureManager.InsertRefPlane(
                constraint,
                ToMeters(support.OffsetMillimeters),
                0,
                0.0,
                0,
                0.0
            );
            Feature planeFeature = createdPlane as Feature;
            if (planeFeature == null)
            {
                planeFeature = model.IFeatureByPositionReverse(0);
            }
            if (planeFeature == null)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS did not create offset plane '" +
                    support.Name + "'."
                );
            }
            planeFeature.Name = support.Name;
            ValidateOffsetPlaneTransform(application, planeFeature, support);
            model.ClearSelection2(true);
            if (!planeFeature.Select2(false, 0))
            {
                throw new InvalidOperationException(
                    "Offset plane '" + support.Name +
                    "' could not be selected."
                );
            }
        }

        private static bool SelectDatumPlane(
            ModelDoc2 model,
            string preferredName,
            string semanticPlane)
        {
            model.ClearSelection2(true);
            if (!String.IsNullOrWhiteSpace(preferredName) &&
                model.Extension.SelectByID2(
                    preferredName,
                    "PLANE",
                    0.0,
                    0.0,
                    0.0,
                    false,
                    0,
                    null,
                    0
                ))
            {
                return true;
            }

            int requestedOrdinal = DatumPlaneOrdinal(semanticPlane);
            if (requestedOrdinal == 0)
            {
                return false;
            }
            int planeOrdinal = 0;
            Feature feature = model.FirstFeature() as Feature;
            while (feature != null)
            {
                if (String.Equals(
                    feature.GetTypeName2(),
                    "RefPlane",
                    StringComparison.Ordinal))
                {
                    planeOrdinal += 1;
                    if (planeOrdinal == requestedOrdinal)
                    {
                        model.ClearSelection2(true);
                        bool selected = feature.Select2(false, 0);
                        if (selected)
                        {
                            Trace(
                                "Selected localized datum plane '" +
                                feature.Name + "' by semantic plane " +
                                semanticPlane
                            );
                        }
                        return selected;
                    }
                }
                feature = feature.GetNextFeature() as Feature;
            }
            return false;
        }

        private static int DatumPlaneOrdinal(string semanticPlane)
        {
            switch (semanticPlane)
            {
                case "XY":
                    return 1;
                case "XZ":
                    return 2;
                case "YZ":
                    return 3;
                default:
                    return 0;
            }
        }

        private static void ValidateOffsetPlaneTransform(
            SldWorks application,
            Feature planeFeature,
            SketchSupport support)
        {
            RefPlane referencePlane = planeFeature == null
                ? null
                : planeFeature.GetSpecificFeature2()
                as RefPlane;
            MathTransform transform = referencePlane == null
                ? null
                : referencePlane.Transform;
            double[] values = transform == null
                ? null
                : transform.ArrayData as double[];
            if (values == null || values.Length < 13)
            {
                throw new InvalidOperationException(
                    "Offset plane '" + support.Name +
                    "' did not expose a readable transform."
                );
            }

            MathUtility mathUtility = application == null
                ? null
                : application.IGetMathUtility();
            MathTransform modelToPlane = transform.IInverse();
            double[] targetOrigin = support.Frame.OriginMillimeters;
            MathPoint targetWorldPoint = mathUtility == null
                ? null
                : mathUtility.CreatePoint(new[]
                    {
                        ToMeters(targetOrigin[0]),
                        ToMeters(targetOrigin[1]),
                        ToMeters(targetOrigin[2]),
                    })
                    as MathPoint;
            MathPoint targetPlanePoint = targetWorldPoint == null ||
                modelToPlane == null
                ? null
                : targetWorldPoint.IMultiplyTransform(modelToPlane);
            double[] planeCoordinates = targetPlanePoint == null
                ? null
                : targetPlanePoint.ArrayData as double[];
            if (planeCoordinates == null || planeCoordinates.Length < 3)
            {
                throw new InvalidOperationException(
                    "Offset plane '" + support.Name +
                    "' transform could not map its requested support point."
                );
            }
            Trace(
                "Offset plane " + support.Name + " target origin [" +
                String.Join(",", targetOrigin) +
                "] maps to plane [" +
                String.Join(",", planeCoordinates) +
                "] transform [" + String.Join(",", values) + "]"
            );

            double normalSeparation = Math.Abs(
                planeCoordinates[2] * MillimetersPerMeter
            );
            if (normalSeparation > 1e-4)
            {
                throw new InvalidOperationException(
                    "Offset plane '" + support.Name + "' was created " +
                    normalSeparation + " mm from its requested support " +
                    "location. Check the datum offset direction."
                );
            }
        }

        private static Face2 FindPlanarFaceNearFrame(
            Feature feature,
            FrameSpec frame)
        {
            Face2 bestFace = null;
            double bestDistance = Double.PositiveInfinity;
            double[] target = new[]
            {
                ToMeters(frame.OriginMillimeters[0]),
                ToMeters(frame.OriginMillimeters[1]),
                ToMeters(frame.OriginMillimeters[2]),
            };
            double[] normal = Normalize(frame.Normal);
            foreach (object faceObject in ObjectItems(feature.GetFaces()))
            {
                Face2 face = faceObject as Face2;
                Surface surface = face == null ? null : face.IGetSurface();
                double[] faceNormal = face == null ? null : face.Normal as double[];
                double[] box = face == null ? null : face.GetBox() as double[];
                if (surface == null || !surface.IsPlane() ||
                    faceNormal == null || box == null || box.Length < 6 ||
                    Dot(faceNormal, normal) < 0.94)
                {
                    continue;
                }
                double[] center = new[]
                {
                    (box[0] + box[3]) / 2.0,
                    (box[1] + box[4]) / 2.0,
                    (box[2] + box[5]) / 2.0,
                };
                double distance = Math.Sqrt(
                    Math.Pow(center[0] - target[0], 2) +
                    Math.Pow(center[1] - target[1], 2) +
                    Math.Pow(center[2] - target[2], 2)
                );
                if (distance < bestDistance)
                {
                    bestFace = face;
                    bestDistance = distance;
                }
            }
            return bestFace;
        }

        private static SketchPoint[] CreateProfileInstances(
            ModelDoc2 model,
            SketchManager sketchManager,
            ReplayStep step,
            MathUtility mathUtility,
            MathTransform modelToSketch)
        {
            double[][] positions = step.Sketch.PositionsMillimeters;
            if (positions == null || positions.Length == 0)
            {
                positions = new[] { new[] { 0.0, 0.0 } };
            }

            if (step.Sketch.Profile == "points")
            {
                var createdPoints = new List<SketchPoint>();
                SketchPoint pointPlacementAnchor = null;
                PlacementControl[] pointPlacementControls =
                    step.Sketch.PlacementControls ?? new PlacementControl[0];
                for (int pointIndex = 0; pointIndex < positions.Length; pointIndex++)
                {
                    double[] sourcePoint = positions[pointIndex];
                    PlacementControl pointControl =
                        pointIndex < pointPlacementControls.Length
                        ? pointPlacementControls[pointIndex]
                        : null;
                    double[] seededPoint = pointControl == null
                        ? sourcePoint
                        : NativeProfileSeedCenter(sourcePoint);
                    double[] nativePointCoordinates = ToSketchPoint(
                        step.Support.Frame,
                        seededPoint,
                        mathUtility,
                        modelToSketch
                    );
                    SketchPoint createdPoint = sketchManager.CreatePoint(
                        nativePointCoordinates[0],
                        nativePointCoordinates[1],
                        nativePointCoordinates[2]
                    );
                    if (createdPoint == null)
                    {
                        throw new InvalidOperationException(
                            "SOLIDWORKS did not create a Hole Wizard position point."
                        );
                    }
                    ApplyPlacementControl(
                        model,
                        sketchManager,
                        step.Support.Frame,
                        createdPoint,
                        pointControl,
                        ref pointPlacementAnchor,
                        mathUtility,
                        modelToSketch
                    );
                    createdPoints.Add(createdPoint);
                }
                return createdPoints.ToArray();
            }

            SketchPoint placementAnchor = null;
            PlacementControl[] placementControls =
                step.Sketch.PlacementControls ?? new PlacementControl[0];
            for (int index = 0; index < positions.Length; index++)
            {
                double[] center = positions[index];
                if (center == null || center.Length < 2)
                {
                    throw new InvalidOperationException(
                        "A native sketch position is missing X or Y."
                    );
                }
                CreateProfileInstance(
                    model,
                    sketchManager,
                    step,
                    center,
                    addDrivingDimensions: index == 0,
                    placementControl: index < placementControls.Length
                        ? placementControls[index]
                        : null,
                    placementAnchor: ref placementAnchor,
                    mathUtility: mathUtility,
                    modelToSketch: modelToSketch
                );
            }
            return new SketchPoint[0];
        }

        private static SketchSegment FindCoincidentAxisSegment(
            Sketch sketch,
            double[] axisStart,
            double[] axisEnd)
        {
            double axisX = axisEnd[0] - axisStart[0];
            double axisY = axisEnd[1] - axisStart[1];
            double axisLength = Math.Sqrt(axisX * axisX + axisY * axisY);
            if (axisLength <= 1e-12)
            {
                return null;
            }
            axisX /= axisLength;
            axisY /= axisLength;

            foreach (object segmentObject in ObjectItems(sketch.GetSketchSegments()))
            {
                SketchSegment segment = segmentObject as SketchSegment;
                if (segment == null || segment.ConstructionGeometry)
                {
                    continue;
                }
                Curve curve = segment.GetCurve() as Curve;
                double[] line = curve == null ? null : curve.LineParams as double[];
                if (line == null || line.Length < 6)
                {
                    continue;
                }
                double directionLength = Math.Sqrt(
                    line[3] * line[3] + line[4] * line[4]
                );
                if (directionLength <= 1e-12)
                {
                    continue;
                }
                double lineX = line[3] / directionLength;
                double lineY = line[4] / directionLength;
                double parallelError = Math.Abs(lineX * axisY - lineY * axisX);
                double offsetError = Math.Abs(
                    (line[0] - axisStart[0]) * axisY -
                    (line[1] - axisStart[1]) * axisX
                );
                if (parallelError <= 1e-6 && offsetError <= 1e-6)
                {
                    return segment;
                }
            }
            return null;
        }

        private static void CreateProfileInstance(
            ModelDoc2 model,
            SketchManager sketchManager,
            ReplayStep step,
            double[] center,
            bool addDrivingDimensions,
            PlacementControl placementControl,
            ref SketchPoint placementAnchor,
            MathUtility mathUtility,
            MathTransform modelToSketch)
        {
            SketchSpec sketch = step.Sketch;
            FrameSpec frame = step.Support.Frame;
            if (frame == null)
            {
                throw new InvalidOperationException(
                    "The replay plan is missing its sketch reference frame."
                );
            }

            if (sketch.Profile == "rectangle")
            {
                double halfWidth = sketch.WidthMillimeters / 2.0;
                double halfHeight = sketch.HeightMillimeters / 2.0;
                double[] seedCenter = addDrivingDimensions
                    ? NativeProfileSeedCenter(center)
                    : center;
                double[] centerWorld = ToSketchPoint(
                    frame,
                    seedCenter,
                    mathUtility,
                    modelToSketch
                );
                double[] cornerWorld = ToSketchPoint(
                    frame,
                    new[]
                    {
                        seedCenter[0] + halfWidth,
                        seedCenter[1] + halfHeight,
                    },
                    mathUtility,
                    modelToSketch
                );
                object segmentsObject = sketchManager.CreateCenterRectangle(
                    centerWorld[0], centerWorld[1], centerWorld[2],
                    cornerWorld[0], cornerWorld[1], cornerWorld[2]
                );
                SketchSegment[] segments = ObjectItems(segmentsObject)
                    .Cast<SketchSegment>()
                    .ToArray();
                if (segments.Length == 0)
                {
                    throw new InvalidOperationException(
                        "SOLIDWORKS did not create the rectangle."
                    );
                }
                SketchPoint centerPoint = CreateRectangleCenterPoint(
                    model,
                    sketchManager,
                    segments,
                    centerWorld
                );
                Trace(
                    "Rectangle constraint status before size dimensions for " +
                    step.SketchName + ": " + ConstraintStatusName(
                        segments[0].GetSketch().GetConstrainedStatus()
                    )
                );
                TraceSketchPoints(
                    segments[0].GetSketch(),
                    "Rectangle before dimensions for " + step.SketchName
                );
                TraceSketchRelations(
                    segments[0].GetSketch(),
                    "Rectangle relations before dimensions for " +
                    step.SketchName
                );
                if (addDrivingDimensions)
                {
                    AddRectangleDimensions(
                        model,
                        segments,
                        sketch,
                        frame,
                        center,
                        mathUtility,
                        modelToSketch
                    );
                }
                ApplyPlacementControl(
                    model,
                    sketchManager,
                    frame,
                    centerPoint,
                    placementControl,
                    ref placementAnchor,
                    mathUtility,
                    modelToSketch
                );
                TraceSketchPoints(
                    segments[0].GetSketch(),
                    "Rectangle after dimensions for " + step.SketchName
                );
                return;
            }

            if (sketch.Profile == "circle")
            {
                double radius = ToMeters(sketch.DiameterMillimeters / 2.0);
                double[] seedCenter = addDrivingDimensions
                    ? NativeProfileSeedCenter(center)
                    : center;
                double[] centerWorld = ToSketchPoint(
                    frame,
                    seedCenter,
                    mathUtility,
                    modelToSketch
                );
                SketchSegment circle = sketchManager.CreateCircleByRadius(
                    centerWorld[0], centerWorld[1], centerWorld[2], radius
                );
                if (circle == null)
                {
                    throw new InvalidOperationException(
                        "SOLIDWORKS did not create the circle."
                    );
                }
                SketchPoint centerPoint = FindSketchPointAt(
                    circle.GetSketch(),
                    centerWorld
                );
                if (addDrivingDimensions)
                {
                    AddCircleDimension(
                        model,
                        circle,
                        sketch,
                        frame,
                        center,
                        mathUtility,
                        modelToSketch
                    );
                }
                ApplyPlacementControl(
                    model,
                    sketchManager,
                    frame,
                    centerPoint,
                    placementControl,
                    ref placementAnchor,
                    mathUtility,
                    modelToSketch
                );
                return;
            }

            if (sketch.Profile == "polygon")
            {
                if (sketch.Sides < 3)
                {
                    throw new InvalidOperationException(
                        "A polygon requires at least three sides."
                    );
                }
                double radius = sketch.DiameterMillimeters / 2.0;
                double[] seedCenter = addDrivingDimensions
                    ? NativeProfileSeedCenter(center)
                    : center;
                double[] centerWorld = ToSketchPoint(
                    frame, seedCenter, mathUtility, modelToSketch
                );
                double[] vertexWorld = ToSketchPoint(
                    frame,
                    new[] { seedCenter[0] + radius, seedCenter[1] },
                    mathUtility,
                    modelToSketch
                );
                object polygonObject = sketchManager.CreatePolygon(
                    centerWorld[0], centerWorld[1], centerWorld[2],
                    vertexWorld[0], vertexWorld[1], vertexWorld[2],
                    sketch.Sides,
                    // A circumscribed construction circle passes through the
                    // vertices, matching CadQuery's polygon diameter.
                    false
                );
                SketchSegment[] polygonSegments = ObjectItems(polygonObject)
                    .Cast<SketchSegment>()
                    .ToArray();
                if (polygonSegments.Length != sketch.Sides)
                {
                    throw new InvalidOperationException(
                        "SOLIDWORKS did not create every polygon side."
                    );
                }
                Sketch polygonSketch = polygonSegments[0].GetSketch();
                SketchPoint centerPoint = FindSketchPointAt(
                    polygonSketch, centerWorld
                );
                if (addDrivingDimensions)
                {
                    SketchSegment constructionCircle =
                        FindPolygonConstructionCircle(polygonSketch);
                    AddCircleDimension(
                        model,
                        constructionCircle,
                        sketch,
                        frame,
                        center,
                        mathUtility,
                        modelToSketch
                    );
                }
                ApplyPlacementControl(
                    model, sketchManager, frame, centerPoint,
                    placementControl, ref placementAnchor,
                    mathUtility, modelToSketch
                );
                return;
            }

            if (sketch.Profile == "polyline")
            {
                SketchPoint centerPoint = CreateFreeformProfileCenter(
                    sketchManager, frame, center, mathUtility, modelToSketch
                );
                ApplyPlacementControl(
                    model, sketchManager, frame, centerPoint,
                    placementControl, ref placementAnchor,
                    mathUtility, modelToSketch
                );
                var points = (sketch.PointsMillimeters ?? new double[0][])
                    .Select(point => new[]
                    {
                        center[0] + point[0],
                        center[1] + point[1],
                    })
                    .ToList();
                CreateClosedPolyline(
                    sketchManager,
                    frame,
                    points,
                    mathUtility,
                    modelToSketch
                );
                if (addDrivingDimensions)
                {
                    ApplyCoordinateControls(
                        model, sketchManager, frame, sketch, center,
                        centerPoint, new Dictionary<int, SketchSegment>(),
                        mathUtility, modelToSketch
                    );
                }
                return;
            }

            if (sketch.Profile == "sketch")
            {
                SketchPoint centerPoint = CreateFreeformProfileCenter(
                    sketchManager, frame, center, mathUtility, modelToSketch
                );
                ApplyPlacementControl(
                    model, sketchManager, frame, centerPoint,
                    placementControl, ref placementAnchor,
                    mathUtility, modelToSketch
                );
                Dictionary<int, SketchSegment> pathSegments = CreateSegmentPath(
                    sketchManager,
                    frame,
                    sketch,
                    center,
                    mathUtility,
                    modelToSketch
                );
                if (addDrivingDimensions)
                {
                    ApplyCoordinateControls(
                        model, sketchManager, frame, sketch, center,
                        centerPoint, pathSegments, mathUtility, modelToSketch
                    );
                }
                return;
            }

            throw new InvalidOperationException(
                "Unsupported native sketch profile '" + sketch.Profile + "'."
            );
        }

        private static double[] NativeProfileSeedCenter(double[] center)
        {
            // A profile created exactly on an existing body boundary can
            // acquire an implicit placement degree of freedom in SOLIDWORKS
            // even with AddToDB enabled.  Start slightly away from coincident
            // geometry; named placement controls move it to the exact source
            // coordinates before the feature is built.
            const double seedOffsetMillimeters = 0.137;
            return new[]
            {
                SeedCoordinate(center[0], seedOffsetMillimeters),
                SeedCoordinate(center[1], seedOffsetMillimeters),
            };
        }

        private static double SeedCoordinate(double value, double offset)
        {
            if (Math.Abs(value) <= 1e-12)
            {
                return offset;
            }
            return value + Math.Sign(value) * offset;
        }

        private static SketchPoint CreateFreeformProfileCenter(
            SketchManager sketchManager,
            FrameSpec frame,
            double[] center,
            MathUtility mathUtility,
            MathTransform modelToSketch)
        {
            double[] centerWorld = ToSketchPoint(
                frame, center, mathUtility, modelToSketch
            );
            SketchPoint centerPoint = sketchManager.CreatePoint(
                centerWorld[0], centerWorld[1], centerWorld[2]
            );
            if (centerPoint == null)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS did not create the freeform profile datum."
                );
            }
            return centerPoint;
        }

        private static void ApplyCoordinateControls(
            ModelDoc2 model,
            SketchManager sketchManager,
            FrameSpec frame,
            SketchSpec sketchSpec,
            double[] center,
            SketchPoint centerPoint,
            IDictionary<int, SketchSegment> pathSegments,
            MathUtility mathUtility,
            MathTransform modelToSketch)
        {
            CoordinateControl[] controls =
                sketchSpec.CoordinateControls ?? new CoordinateControl[0];
            if (controls.Length == 0)
            {
                return;
            }
            Sketch activeSketch = model.IGetActiveSketch2();
            if (activeSketch == null)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS did not expose the freeform sketch."
                );
            }

            bool previousAddToDatabase = sketchManager.AddToDB;
            try
            {
                foreach (CoordinateControl control in controls)
                {
                    if (control.PositionMillimeters == null ||
                        control.PositionMillimeters.Length < 2)
                    {
                        throw new InvalidOperationException(
                            "A native coordinate control is missing X or Y."
                        );
                    }
                    double[] localPoint = Add2D(
                        center, control.PositionMillimeters
                    );
                    double[] worldPoint = ToSketchPoint(
                        frame, localPoint, mathUtility, modelToSketch
                    );
                    SketchPoint targetPoint;
                    if (String.Equals(
                        control.Kind,
                        "arc_through",
                        StringComparison.Ordinal))
                    {
                        sketchManager.AddToDB = true;
                        targetPoint = sketchManager.CreatePoint(
                            worldPoint[0], worldPoint[1], worldPoint[2]
                        );
                        if (targetPoint == null)
                        {
                            throw new InvalidOperationException(
                                "SOLIDWORKS did not create an arc control point."
                            );
                        }
                        SketchSegment arc;
                        if (!control.SegmentIndex.HasValue ||
                            !pathSegments.TryGetValue(
                                control.SegmentIndex.Value, out arc
                            ))
                        {
                            throw new InvalidOperationException(
                                "An arc coordinate control has no matching arc."
                            );
                        }
                        sketchManager.AddToDB = false;
                        AddPointSegmentRelation(
                            model, targetPoint, arc, "sgCOINCIDENT"
                        );
                    }
                    else
                    {
                        targetPoint = FindSketchPointAt(
                            activeSketch, worldPoint
                        );
                    }

                    sketchManager.AddToDB = false;
                    AddPlacementAxisControl(
                        model, frame, centerPoint, targetPoint,
                        new[] { 1.0, 0.0 },
                        control.PositionMillimeters[0], control.XDimension,
                        mathUtility, modelToSketch
                    );
                    AddPlacementAxisControl(
                        model, frame, centerPoint, targetPoint,
                        new[] { 0.0, 1.0 },
                        control.PositionMillimeters[1], control.YDimension,
                        mathUtility, modelToSketch
                    );
                }
            }
            finally
            {
                sketchManager.AddToDB = previousAddToDatabase;
                model.ClearSelection2(true);
            }
        }

        private static void AddPointSegmentRelation(
            ModelDoc2 model,
            SketchPoint point,
            SketchSegment segment,
            string relation)
        {
            model.ClearSelection2(true);
            if (!point.Select4(false, null) || !segment.Select4(true, null))
            {
                throw new InvalidOperationException(
                    "Could not select an arc coordinate control."
                );
            }
            model.SketchAddConstraints(relation);
            model.ClearSelection2(true);
        }

        private static void CreateClosedPolyline(
            SketchManager sketchManager,
            FrameSpec frame,
            IList<double[]> points,
            MathUtility mathUtility,
            MathTransform modelToSketch)
        {
            if (points == null || points.Count < 3)
            {
                throw new InvalidOperationException(
                    "A closed native polyline requires at least three points."
                );
            }
            for (int index = 0; index < points.Count; index++)
            {
                CreateLine(
                    sketchManager,
                    frame,
                    points[index],
                    points[(index + 1) % points.Count],
                    mathUtility,
                    modelToSketch
                );
            }
        }

        private static Dictionary<int, SketchSegment> CreateSegmentPath(
            SketchManager sketchManager,
            FrameSpec frame,
            SketchSpec sketch,
            double[] center,
            MathUtility mathUtility,
            MathTransform modelToSketch)
        {
            var createdSegments = new Dictionary<int, SketchSegment>();
            if (sketch.StartMillimeters == null || sketch.StartMillimeters.Length < 2)
            {
                throw new InvalidOperationException("A sketch path requires a start point.");
            }
            double[] start = Add2D(center, sketch.StartMillimeters);
            double[] current = start;
            SketchPathSegment[] sourceSegments =
                sketch.Segments ?? new SketchPathSegment[0];
            for (int segmentIndex = 0; segmentIndex < sourceSegments.Length;
                segmentIndex++)
            {
                SketchPathSegment segment = sourceSegments[segmentIndex];
                if (segment.ToMillimeters == null || segment.ToMillimeters.Length < 2)
                {
                    throw new InvalidOperationException(
                        "A sketch segment is missing its end point."
                    );
                }
                double[] end = Add2D(center, segment.ToMillimeters);
                if (segment.Type == "line")
                {
                    CreateLine(
                        sketchManager,
                        frame,
                        current,
                        end,
                        mathUtility,
                        modelToSketch
                    );
                }
                else if (segment.Type == "arc")
                {
                    if (segment.ThroughMillimeters == null ||
                        segment.ThroughMillimeters.Length < 2)
                    {
                        throw new InvalidOperationException(
                            "An arc segment is missing its through point."
                        );
                    }
                    double[] through = Add2D(center, segment.ThroughMillimeters);
                    double[] startWorld = ToSketchPoint(
                        frame, current, mathUtility, modelToSketch
                    );
                    double[] throughWorld = ToSketchPoint(
                        frame, through, mathUtility, modelToSketch
                    );
                    double[] endWorld = ToSketchPoint(
                        frame, end, mathUtility, modelToSketch
                    );
                    SketchSegment arc = sketchManager.Create3PointArc(
                        startWorld[0], startWorld[1], startWorld[2],
                        endWorld[0], endWorld[1], endWorld[2],
                        throughWorld[0], throughWorld[1], throughWorld[2]
                    );
                    if (arc == null)
                    {
                        throw new InvalidOperationException(
                            "SOLIDWORKS did not create a sketch arc."
                        );
                    }
                    createdSegments[segmentIndex + 1] = arc;
                }
                else
                {
                    throw new InvalidOperationException(
                        "Unsupported sketch segment type '" + segment.Type + "'."
                    );
                }
                current = end;
            }
            if (sketch.Close && Distance2D(current, start) > 1e-9)
            {
                CreateLine(
                    sketchManager,
                    frame,
                    current,
                    start,
                    mathUtility,
                    modelToSketch
                );
            }
            return createdSegments;
        }

        private static void CreateLine(
            SketchManager sketchManager,
            FrameSpec frame,
            double[] start,
            double[] end,
            MathUtility mathUtility,
            MathTransform modelToSketch)
        {
            double[] startWorld = ToSketchPoint(
                frame, start, mathUtility, modelToSketch
            );
            double[] endWorld = ToSketchPoint(
                frame, end, mathUtility, modelToSketch
            );
            SketchSegment line = sketchManager.CreateLine(
                startWorld[0], startWorld[1], startWorld[2],
                endWorld[0], endWorld[1], endWorld[2]
            );
            if (line == null)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS did not create a sketch line."
                );
            }
        }

        private static SketchPoint FindSketchPointAt(
            Sketch sketch,
            double[] target)
        {
            SketchPoint bestPoint = null;
            double bestDistance = Double.PositiveInfinity;
            foreach (object pointObject in ObjectItems(sketch.GetSketchPoints2()))
            {
                SketchPoint point = pointObject as SketchPoint;
                if (point == null)
                {
                    continue;
                }
                double distance = Math.Sqrt(
                    Math.Pow(point.X - target[0], 2) +
                    Math.Pow(point.Y - target[1], 2) +
                    Math.Pow(point.Z - target[2], 2)
                );
                // Prefer the newest point when an explicit anchor and a profile
                // center intentionally share the same coordinates.
                if (distance <= bestDistance)
                {
                    bestPoint = point;
                    bestDistance = distance;
                }
            }
            if (bestPoint == null || bestDistance > 1e-7)
            {
                throw new InvalidOperationException(
                    "Could not identify the native profile center point."
                );
            }
            return bestPoint;
        }

        private static SketchSegment FindPolygonConstructionCircle(
            Sketch sketch)
        {
            SketchSegment match = null;
            foreach (object segmentObject in ObjectItems(
                sketch.GetSketchSegments()
            ))
            {
                SketchSegment segment = segmentObject as SketchSegment;
                Curve curve = segment == null ? null : segment.GetCurve() as Curve;
                if (segment == null || !segment.ConstructionGeometry ||
                    curve == null || !curve.IsCircle())
                {
                    continue;
                }
                if (match != null)
                {
                    throw new InvalidOperationException(
                        "The polygon sketch contains multiple construction circles."
                    );
                }
                match = segment;
            }
            if (match == null)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS did not expose the polygon construction circle."
                );
            }
            return match;
        }

        private static SketchPoint CreateRectangleCenterPoint(
            ModelDoc2 model,
            SketchManager sketchManager,
            SketchSegment[] rectangleSegments,
            double[] center)
        {
            SketchPoint centerPoint = sketchManager.CreatePoint(
                center[0], center[1], center[2]
            );
            if (centerPoint == null)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS did not create the rectangle center point."
                );
            }

            SketchSegment centerGuide = rectangleSegments.FirstOrDefault(
                segment => segment != null && segment.ConstructionGeometry
            );
            if (centerGuide == null)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS did not expose the center-rectangle guide geometry."
                );
            }

            bool previousAddToDatabase = sketchManager.AddToDB;
            try
            {
                sketchManager.AddToDB = false;
                model.ClearSelection2(true);
                if (!centerPoint.Select4(false, null) ||
                    !centerGuide.Select4(true, null))
                {
                    throw new InvalidOperationException(
                        "Could not select the rectangle center references."
                    );
                }
                model.SketchAddConstraints("sgATMIDDLE");
                model.ClearSelection2(true);
            }
            finally
            {
                sketchManager.AddToDB = previousAddToDatabase;
                model.ClearSelection2(true);
            }
            return centerPoint;
        }

        private static void ApplyPlacementControl(
            ModelDoc2 model,
            SketchManager sketchManager,
            FrameSpec frame,
            SketchPoint centerPoint,
            PlacementControl control,
            ref SketchPoint anchorPoint,
            MathUtility mathUtility,
            MathTransform modelToSketch)
        {
            if (control == null)
            {
                return;
            }
            if (control.PositionMillimeters == null ||
                control.PositionMillimeters.Length < 2)
            {
                throw new InvalidOperationException(
                    "A native placement control is missing its X or Y value."
                );
            }

            bool anchorWasCreated = anchorPoint == null;
            if (anchorWasCreated)
            {
                double[] anchorCoordinates = ToSketchPoint(
                    frame,
                    new[] { 0.0, 0.0 },
                    mathUtility,
                    modelToSketch
                );
                anchorPoint = sketchManager.CreatePoint(
                    anchorCoordinates[0],
                    anchorCoordinates[1],
                    anchorCoordinates[2]
                );
                if (anchorPoint == null)
                {
                    throw new InvalidOperationException(
                        "SOLIDWORKS did not create the placement datum point."
                    );
                }
            }

            bool previousAddToDatabase = sketchManager.AddToDB;
            try
            {
                sketchManager.AddToDB = false;
                if (anchorWasCreated)
                {
                    FixSketchPoint(model, anchorPoint);
                }

                double xValue = control.PositionMillimeters[0];
                double yValue = control.PositionMillimeters[1];
                if (Math.Abs(xValue) <= 1e-12 && Math.Abs(yValue) <= 1e-12)
                {
                    AddPointRelation(
                        model,
                        anchorPoint,
                        centerPoint,
                        "sgCOINCIDENT"
                    );
                    return;
                }

                AddPlacementAxisControl(
                    model,
                    frame,
                    anchorPoint,
                    centerPoint,
                    new[] { 1.0, 0.0 },
                    xValue,
                    control.XDimension,
                    mathUtility,
                    modelToSketch
                );
                AddPlacementAxisControl(
                    model,
                    frame,
                    anchorPoint,
                    centerPoint,
                    new[] { 0.0, 1.0 },
                    yValue,
                    control.YDimension,
                    mathUtility,
                    modelToSketch
                );
            }
            finally
            {
                sketchManager.AddToDB = previousAddToDatabase;
                model.ClearSelection2(true);
            }
        }

        private static void FixSketchPoint(ModelDoc2 model, SketchPoint point)
        {
            model.ClearSelection2(true);
            if (!point.Select4(false, null))
            {
                throw new InvalidOperationException(
                    "Could not select the placement datum point."
                );
            }
            model.SketchAddConstraints("sgFIXED");
            model.ClearSelection2(true);
        }

        private static void AddPlacementAxisControl(
            ModelDoc2 model,
            FrameSpec frame,
            SketchPoint anchorPoint,
            SketchPoint centerPoint,
            double[] localDirection,
            double signedValue,
            DimensionSpec specification,
            MathUtility mathUtility,
            MathTransform modelToSketch)
        {
            double[] sketchDirection = ToSketchDirection(
                frame,
                localDirection,
                mathUtility,
                modelToSketch
            );
            bool horizontal = Math.Abs(sketchDirection[0]) >=
                Math.Abs(sketchDirection[1]);

            if (Math.Abs(signedValue) <= 1e-12)
            {
                AddPointRelation(
                    model,
                    anchorPoint,
                    centerPoint,
                    horizontal
                        ? "sgVERTICALPOINTS2D"
                        : "sgHORIZONTALPOINTS2D"
                );
                return;
            }
            if (specification == null)
            {
                throw new InvalidOperationException(
                    "A nonzero native placement is missing its dimension."
                );
            }

            SelectSketchPoints(model, anchorPoint, centerPoint);
            double[] label = horizontal
                ? new[]
                {
                    (anchorPoint.X + centerPoint.X) / 2.0,
                    Math.Min(anchorPoint.Y, centerPoint.Y) - 0.01,
                    0.0,
                }
                : new[]
                {
                    Math.Min(anchorPoint.X, centerPoint.X) - 0.01,
                    (anchorPoint.Y + centerPoint.Y) / 2.0,
                    0.0,
                };
            object display = horizontal
                ? model.AddHorizontalDimension2(label[0], label[1], label[2])
                : model.AddVerticalDimension2(label[0], label[1], label[2]);
            SetNativeDimension(display, specification);
            model.ClearSelection2(true);
        }

        private static void AddPointRelation(
            ModelDoc2 model,
            SketchPoint first,
            SketchPoint second,
            string relation)
        {
            SelectSketchPoints(model, first, second);
            model.SketchAddConstraints(relation);
            model.ClearSelection2(true);
        }

        private static void SelectSketchPoints(
            ModelDoc2 model,
            SketchPoint first,
            SketchPoint second)
        {
            model.ClearSelection2(true);
            if (!first.Select4(false, null) || !second.Select4(true, null))
            {
                throw new InvalidOperationException(
                    "Could not select the native placement points."
                );
            }
        }

        private static void AddRectangleDimensions(
            ModelDoc2 model,
            SketchSegment[] segments,
            SketchSpec sketch,
            FrameSpec frame,
            double[] center,
            MathUtility mathUtility,
            MathTransform modelToSketch)
        {
            DimensionSpec widthSpec = FindDimension(sketch, ".sketch.width");
            DimensionSpec heightSpec = FindDimension(sketch, ".sketch.height");
            double[] widthDirection = ToSketchDirection(
                frame,
                new[] { 1.0, 0.0 },
                mathUtility,
                modelToSketch
            );
            double[] heightDirection = ToSketchDirection(
                frame,
                new[] { 0.0, 1.0 },
                mathUtility,
                modelToSketch
            );
            SketchSegment widthSegment = FindRectangleSegment(
                segments,
                widthDirection
            );
            SketchSegment heightSegment = FindRectangleSegment(
                segments,
                heightDirection
            );

            double width = ToMeters(sketch.WidthMillimeters);
            double height = ToMeters(sketch.HeightMillimeters);

            model.ClearSelection2(true);
            if (!widthSegment.Select4(false, null))
            {
                throw new InvalidOperationException("Could not select the rectangle width.");
            }
            Trace("Creating rectangle width dimension");
            double[] widthLabel = ToSketchPoint(
                frame,
                new[] { center[0], center[1] - 0.7 * sketch.HeightMillimeters },
                mathUtility,
                modelToSketch
            );
            object widthDisplay = model.AddDimension2(
                widthLabel[0], widthLabel[1], widthLabel[2]
            );
            Trace("Naming rectangle width dimension");
            SetNativeDimension(widthDisplay, widthSpec);

            Trace("Selecting rectangle height segment");
            model.ClearSelection2(true);
            if (!heightSegment.Select4(false, null))
            {
                throw new InvalidOperationException("Could not select the rectangle height.");
            }
            Trace("Creating rectangle height dimension");
            double[] heightLabel = ToSketchPoint(
                frame,
                new[] { center[0] - 0.7 * sketch.WidthMillimeters, center[1] },
                mathUtility,
                modelToSketch
            );
            object heightDisplay = model.AddDimension2(
                heightLabel[0], heightLabel[1], heightLabel[2]
            );
            Trace("Naming rectangle height dimension");
            SetNativeDimension(heightDisplay, heightSpec);
            model.ClearSelection2(true);
        }

        private static void AddCircleDimension(
            ModelDoc2 model,
            SketchSegment circle,
            SketchSpec sketch,
            FrameSpec frame,
            double[] center,
            MathUtility mathUtility,
            MathTransform modelToSketch)
        {
            DimensionSpec diameterSpec = FindDimension(sketch, ".sketch.diameter");
            double radius = ToMeters(sketch.DiameterMillimeters / 2.0);
            model.ClearSelection2(true);
            if (!circle.Select4(false, null))
            {
                throw new InvalidOperationException("Could not select the sketch circle.");
            }
            Trace("Creating circle diameter dimension");
            double[] label = ToSketchPoint(
                frame,
                new[]
                {
                    center[0] + 0.75 * sketch.DiameterMillimeters,
                    center[1] + 0.75 * sketch.DiameterMillimeters,
                },
                mathUtility,
                modelToSketch
            );
            object diameterDisplay = model.AddDiameterDimension2(
                label[0], label[1], label[2]
            );
            Trace("Naming circle diameter dimension");
            SetNativeDimension(diameterDisplay, diameterSpec);
            model.ClearSelection2(true);
        }

        private static SketchSegment FindRectangleSegment(
            IEnumerable<SketchSegment> segments,
            double[] expectedDirection)
        {
            foreach (SketchSegment segment in segments)
            {
                if (segment == null || segment.ConstructionGeometry)
                {
                    continue;
                }
                Curve curve = (Curve)segment.GetCurve();
                double[] line = curve == null ? null : (double[])curve.LineParams;
                if (line == null || line.Length < 6)
                {
                    continue;
                }
                double alignment = Math.Abs(
                    line[3] * expectedDirection[0] +
                    line[4] * expectedDirection[1] +
                    line[5] * expectedDirection[2]
                );
                if (alignment >= 0.99)
                {
                    return segment;
                }
            }
            throw new InvalidOperationException(
                "Could not identify a rectangle segment in the expected direction."
            );
        }

        private static DimensionSpec FindDimension(SketchSpec sketch, string suffix)
        {
            DimensionSpec dimension = (sketch.DrivingDimensions ?? new DimensionSpec[0])
                .FirstOrDefault(item => item.ParameterId.EndsWith(
                    suffix,
                    StringComparison.Ordinal
                ));
            if (dimension == null)
            {
                throw new InvalidOperationException(
                    "The sketch is missing its named '" + suffix + "' dimension."
                );
            }
            return dimension;
        }

        private static void SetNativeDimension(
            object displayDimensionObject,
            DimensionSpec specification)
        {
            if (displayDimensionObject == null)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS did not create dimension '" +
                    specification.NativeName + "'."
                );
            }
            DisplayDimension displayDimension = (DisplayDimension)displayDimensionObject;
            Dimension dimension = displayDimension.GetDimension2(0);
            if (dimension == null)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS did not expose dimension '" +
                    specification.NativeName + "'."
                );
            }

            Trace(
                "Initial driven state for " + specification.NativeName +
                ": " + dimension.DrivenState
            );
            if (dimension.DrivenState ==
                (int)swDimensionDrivenState_e.swDimensionDriven)
            {
                Trace(
                    "Converting driven sketch dimension " +
                    specification.NativeName + " to driving"
                );
                dimension.DrivenState =
                    (int)swDimensionDrivenState_e.swDimensionDriving;
                Trace(
                    "Driven state after conversion for " +
                    specification.NativeName + ": " +
                    dimension.DrivenState
                );
            }
            if (dimension.DrivenState ==
                (int)swDimensionDrivenState_e.swDimensionDriven)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS kept dimension '" +
                    specification.NativeName +
                    "' driven instead of editable."
                );
            }
            dimension.Name = specification.NativeName;
            int status = dimension.SetSystemValue3(
                ToSystemValue(specification),
                (int)swSetValueInConfiguration_e.swSetValue_InAllConfigurations,
                null
            );
            if (status != (int)swSetValueReturnStatus_e.swSetValue_Successful)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS rejected dimension '" + specification.NativeName +
                    "' with status " + status + "."
                );
            }
        }

        private static Feature CreateNativeFeature(
            ModelDoc2 model,
            ReplayStep step,
            NativeSketchResult nativeSketch)
        {
            model.ClearSelection2(true);
            if (!nativeSketch.SketchFeature.Select2(false, 0))
            {
                throw new InvalidOperationException(
                    "Could not select sketch '" + step.SketchName + "' for feature creation."
                );
            }

            FeatureManager manager = model.FeatureManager;
            int endCondition = (int)swEndConditions_e.swEndCondBlind;
            double depth = 0.01;
            if (step.Feature.EndCondition == "through_all")
            {
                endCondition = (int)swEndConditions_e.swEndCondThroughAll;
            }
            else if (step.Feature.DepthMillimeters.HasValue)
            {
                depth = ToMeters(step.Feature.DepthMillimeters.Value);
            }
            bool reverseDirection = step.Support != null &&
                step.Support.ReverseDirection;
            bool singleEnded = !step.Feature.ReverseDepthMillimeters.HasValue;
            double reverseDepth = step.Feature.ReverseDepthMillimeters.HasValue
                ? ToMeters(step.Feature.ReverseDepthMillimeters.Value)
                : 0.01;
            if (step.Feature.ReverseDepthMillimeters.HasValue &&
                step.Feature.ReverseDepthMillimeters.Value <= 0.0)
            {
                throw new InvalidOperationException(
                    "Reverse extrusion depth must be positive."
                );
            }
            int secondEndCondition = (int)swEndConditions_e.swEndCondBlind;

            Feature feature;
            if (step.Feature.Kind == "boss_extrude")
            {
                feature = manager.FeatureExtrusion3(
                    singleEnded, false, reverseDirection,
                    endCondition, secondEndCondition,
                    depth, reverseDepth,
                    false, false, false, false,
                    0.0, 0.0,
                    false, false, false, false,
                    step.Feature.MergeResult,
                    true, true,
                    0, 0.0, false
                );
            }
            else if (step.Feature.Kind == "cut_extrude")
            {
                feature = manager.FeatureCut4(
                    true, false, reverseDirection,
                    endCondition, 0,
                    depth, 0.01,
                    false, false, false, false,
                    0.0, 0.0,
                    false, false, false, false,
                    false,
                    true, true,
                    false, false, false,
                    0, 0.0, false,
                    true
                );
            }
            else if (step.Feature.Kind == "boss_revolve" ||
                step.Feature.Kind == "cut_revolve")
            {
                SelectionMgr selectionManager =
                    (SelectionMgr)model.SelectionManager;
                SelectData axisSelection = selectionManager.CreateSelectData();
                axisSelection.Mark = 4;
                if (nativeSketch.RevolveAxis == null ||
                    !nativeSketch.RevolveAxis.Select4(true, axisSelection))
                {
                    throw new InvalidOperationException(
                        "Could not select the native revolve axis."
                    );
                }
                feature = manager.FeatureRevolve2(
                    true,
                    true,
                    false,
                    step.Feature.Kind == "cut_revolve",
                    false,
                    false,
                    0,
                    0,
                    DegreesToRadians(step.Feature.AngleDegrees),
                    0.0,
                    false,
                    false,
                    0.0,
                    0.0,
                    0,
                    0.0,
                    0.0,
                    step.Feature.MergeResult,
                    true,
                    true
                );
                if (feature == null && step.Feature.Kind == "cut_revolve")
                {
                    Trace(
                        "Retrying " + step.FeatureName +
                        " with the compatibility cut-revolve API"
                    );
                    model.ClearSelection2(true);
                    if (!nativeSketch.SketchFeature.Select2(false, 0))
                    {
                        throw new InvalidOperationException(
                            "Could not reselect sketch '" + step.SketchName +
                            "' for cut-revolve compatibility replay."
                        );
                    }
                    SelectData retryAxisSelection =
                        selectionManager.CreateSelectData();
                    retryAxisSelection.Mark = 4;
                    if (nativeSketch.RevolveAxis == null ||
                        !nativeSketch.RevolveAxis.Select4(
                            true,
                            retryAxisSelection
                        ))
                    {
                        throw new InvalidOperationException(
                            "Could not reselect the native cut-revolve axis."
                        );
                    }
                    feature = manager.FeatureRevolveCut2(
                        DegreesToRadians(step.Feature.AngleDegrees),
                        false,
                        0.0,
                        0,
                        0,
                        true,
                        true,
                        false,
                        false,
                        false
                    );
                }
            }
            else
            {
                throw new InvalidOperationException(
                    "Unsupported native feature kind '" + step.Feature.Kind + "'."
                );
            }

            if (feature == null &&
                (step.Feature.Kind == "boss_extrude" ||
                 step.Feature.Kind == "cut_extrude"))
            {
                Trace("Retrying " + step.FeatureName + " in the opposite direction");
                model.ClearSelection2(true);
                if (!nativeSketch.SketchFeature.Select2(false, 0))
                {
                    throw new InvalidOperationException(
                        "Could not reselect sketch '" + step.SketchName +
                        "' for opposite-direction feature creation."
                    );
                }
                if (step.Feature.Kind == "boss_extrude")
                {
                    feature = manager.FeatureExtrusion3(
                        singleEnded, false, !reverseDirection,
                        endCondition, secondEndCondition,
                        depth, reverseDepth,
                        false, false, false, false,
                        0.0, 0.0,
                        false, false, false, false,
                        step.Feature.MergeResult,
                        true, true,
                        0, 0.0, false
                    );
                }
                else
                {
                    feature = manager.FeatureCut4(
                        true, false, !reverseDirection,
                        endCondition, 0,
                        depth, 0.01,
                        false, false, false, false,
                        0.0, 0.0,
                        false, false, false, false,
                        false,
                        true, true,
                        false, false, false,
                        0, 0.0, false,
                        true
                    );
                }
            }

            if (feature == null)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS did not create feature '" + step.FeatureName + "'."
                );
            }
            feature.Name = step.Pattern == null
                ? step.FeatureName
                : step.Pattern.SeedFeatureName;

            ConfigureFeatureDrivingDimension(
                feature,
                step.Feature.DrivingDimension,
                step.FeatureName
            );
            ConfigureFeatureDrivingDimension(
                feature,
                step.Feature.ReverseDrivingDimension,
                step.FeatureName,
                "D2"
            );

            if (!model.EditRebuild3())
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS rebuild failed after '" + step.FeatureName + "'."
                );
            }
            return feature;
        }

        private static Feature CreateNativeCountersink(
            ModelDoc2 model,
            ReplayStep step,
            NativeSketchResult nativeSketch)
        {
            model.ClearSelection2(true);
            SketchPoint[] featurePoints =
                nativeSketch.FeaturePoints ?? new SketchPoint[0];
            if (featurePoints.Length == 0)
            {
                throw new InvalidOperationException(
                    "The countersink position sketch contains no points."
                );
            }
            foreach (SketchPoint point in featurePoints)
            {
                if (point == null || !point.Select4(true, null))
                {
                    throw new InvalidOperationException(
                        "Could not select a countersink position point."
                    );
                }
            }

            short endCondition = (short)(
                step.Feature.EndCondition == "through_all"
                    ? swEndConditions_e.swEndCondThroughAll
                    : swEndConditions_e.swEndCondBlind
            );
            double depth = step.Feature.DepthMillimeters.HasValue
                ? ToMeters(step.Feature.DepthMillimeters.Value)
                : 0.01;
            FeatureManager manager = model.FeatureManager;
            Feature feature = manager.HoleWizard5(
                (int)swWzdGeneralHoleTypes_e.swWzdCounterSink,
                (int)swWzdHoleStandards_e.swStandardAnsiMetric,
                (int)swWzdHoleStandardFastenerTypes_e.swStandardAnsiMetricFlatHead82,
                "M2",
                endCondition,
                ToMeters(step.Feature.HoleDiameterMillimeters),
                depth,
                -1.0,
                ToMeters(step.Feature.CountersinkDiameterMillimeters),
                DegreesToRadians(step.Feature.CountersinkAngleDegrees),
                -1.0, -1.0, -1.0, -1.0,
                -1.0, -1.0, -1.0, -1.0, -1.0, -1.0,
                "",
                false,
                false,
                true,
                false,
                false,
                false
            );
            if (feature == null)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS did not create the Hole Wizard countersink."
                );
            }
            feature.Name = step.Pattern == null
                ? step.FeatureName
                : step.Pattern.SeedFeatureName;
            if (!model.EditRebuild3())
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS rebuild failed after '" + step.FeatureName + "'."
                );
            }
            return feature;
        }

        private static void ConfigureFeatureDrivingDimension(
            Feature feature,
            DimensionSpec specification,
            string featureName,
            string dimensionParameter = "D1")
        {
            if (specification == null)
            {
                return;
            }
            object dimensionObject = feature.Parameter(dimensionParameter);
            if (dimensionObject == null)
            {
                throw new InvalidOperationException(
                    "Native feature '" + featureName +
                    "' has no " + dimensionParameter +
                    " driving dimension."
                );
            }
            Dimension dimension = (Dimension)dimensionObject;
            dimension.Name = specification.NativeName;
            int status = dimension.SetSystemValue3(
                ToSystemValue(specification),
                (int)swSetValueInConfiguration_e.swSetValue_InAllConfigurations,
                null
            );
            if (status != (int)swSetValueReturnStatus_e.swSetValue_Successful)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS rejected feature dimension '" +
                    specification.NativeName + "'."
                );
            }
        }

        private static Feature CreateNativePattern(
            SldWorks application,
            ModelDoc2 model,
            PartDoc part,
            ReplayStep step,
            Feature seedFeature)
        {
            PatternSpec pattern = step.Pattern;
            Feature patternFeature;
            if (pattern.Kind == "circular_pattern")
            {
                PatternReferenceSketch references = CreatePatternReferenceSketch(
                    model,
                    step,
                    circular: true
                );
                model.ClearSelection2(true);
                if (!seedFeature.Select2(false, 4))
                {
                    throw new InvalidOperationException(
                        "Could not select the circular-pattern seed feature."
                    );
                }
                SelectCircularPatternAxis(references.CircularAxis);
                object definitionObject = model.FeatureManager.CreateDefinition(
                    (int)swFeatureNameID_e.swFmCirPattern
                );
                CircularPatternFeatureData definition =
                    definitionObject as CircularPatternFeatureData;
                if (definition == null)
                {
                    throw new InvalidOperationException(
                        "SOLIDWORKS did not create circular-pattern feature data."
                    );
                }
                object axisEntity = references.CircularAxis.GetSpecificFeature2();
                if (axisEntity == null)
                {
                    throw new InvalidOperationException(
                        "Could not retrieve the circular-pattern reference axis."
                    );
                }
                definition.Axis = axisEntity;
                definition.PatternElement =
                    (int)swPatternElementSelection_e.swFeatureFaces;
                definition.BodyPattern = false;
                definition.TotalInstances = pattern.Count;
                definition.Spacing = DegreesToRadians(
                    pattern.TotalAngleDegrees
                );
                definition.EqualSpacing = true;
                definition.ReverseDirection = false;
                definition.Direction2 = false;
                definition.GeometryPattern = true;
                definition.VarySketch = false;
                definition.PropagateVisualProperty = true;
                patternFeature = model.FeatureManager.CreateFeature(definition);
            }
            else if (pattern.Kind == "linear_pattern")
            {
                PatternReferenceSketch references = CreatePatternReferenceSketch(
                    model,
                    step,
                    circular: false
                );
                model.ClearSelection2(true);
                if (!seedFeature.Select2(false, 4))
                {
                    throw new InvalidOperationException(
                        "Could not select the linear-pattern seed feature."
                    );
                }
                SelectPatternDirection(model, references.Direction1, 1);
                if (pattern.Count2 > 1)
                {
                    SelectPatternDirection(model, references.Direction2, 2);
                }
                patternFeature = model.FeatureManager.FeatureLinearPattern5(
                    pattern.Count1,
                    ToMeters(pattern.Spacing1Millimeters),
                    pattern.Count2,
                    ToMeters(pattern.Spacing2Millimeters),
                    false,
                    false,
                    "NULL",
                    "NULL",
                    true,
                    false,
                    false,
                    false,
                    true,
                    true,
                    true,
                    true,
                    false,
                    false,
                    0.0,
                    0.0,
                    false,
                    false
                );
            }
            else if (pattern.Kind == "mirror_pattern")
            {
                patternFeature = CreateSketchDrivenPattern(
                    application,
                    model,
                    part,
                    step,
                    seedFeature
                );
            }
            else
            {
                throw new InvalidOperationException(
                    "Unsupported native pattern kind '" + pattern.Kind + "'."
                );
            }

            if (patternFeature == null)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS did not create pattern '" + step.FeatureName + "'."
                );
            }
            if (pattern.Kind == "circular_pattern")
            {
                TraceCircularPatternDefinition(patternFeature, model);
            }
            patternFeature.Name = step.FeatureName;
            if (!model.EditRebuild3())
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS rebuild failed after pattern '" +
                    step.FeatureName + "'."
                );
            }
            return patternFeature;
        }

        private sealed class PatternReferenceSketch
        {
            public Feature SketchFeature { get; set; }
            public SketchSegment Direction1 { get; set; }
            public SketchSegment Direction2 { get; set; }
            public Feature CircularAxis { get; set; }
        }

        private static PatternReferenceSketch CreatePatternReferenceSketch(
            ModelDoc2 model,
            ReplayStep step,
            bool circular)
        {
            model.ClearSelection2(true);
            model.Insert3DSketch2(true);
            Feature sketchFeature = model.GetActiveSketch2() as Feature;
            if (sketchFeature == null)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS did not enter the pattern reference sketch."
                );
            }
            sketchFeature.Name = step.Pattern.ReferenceSketchName;
            SketchManager sketchManager = model.SketchManager;
            FrameSpec frame = step.Support.Frame;
            double[] seed = step.Pattern.SeedPositionMillimeters;
            double[] start = WorldPoint(frame, seed);
            double[] direction1;
            double[] direction2 = null;
            if (circular)
            {
                double[] center = WorldPoint(frame, step.Pattern.CenterMillimeters);
                start = center;
                direction1 = Normalize(frame.Normal);
            }
            else
            {
                direction1 = LocalDirection(frame, step.Pattern.Direction1);
                direction2 = LocalDirection(frame, step.Pattern.Direction2);
            }

            SketchSegment first = sketchManager.CreateLine(
                start[0], start[1], start[2],
                start[0] + 0.02 * direction1[0],
                start[1] + 0.02 * direction1[1],
                start[2] + 0.02 * direction1[2]
            );
            if (first == null)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS did not create pattern direction 1."
                );
            }
            first.ConstructionGeometry = true;

            SketchSegment second = null;
            if (!circular && step.Pattern.Count2 > 1)
            {
                second = sketchManager.CreateLine(
                    start[0], start[1], start[2],
                    start[0] + 0.02 * direction2[0],
                    start[1] + 0.02 * direction2[1],
                    start[2] + 0.02 * direction2[2]
                );
                if (second == null)
                {
                    throw new InvalidOperationException(
                        "SOLIDWORKS did not create pattern direction 2."
                    );
                }
                second.ConstructionGeometry = true;
            }
            model.Insert3DSketch2(true);
            Feature circularAxis = null;
            if (circular)
            {
                model.ClearSelection2(true);
                SelectionMgr selectionManager =
                    (SelectionMgr)model.SelectionManager;
                SelectData axisSource = selectionManager.CreateSelectData();
                axisSource.Mark = 0;
                if (!first.Select4(false, axisSource))
                {
                    throw new InvalidOperationException(
                        "Could not select circular-pattern axis geometry."
                    );
                }
                int featureCountBeforeAxis = model.GetFeatureCount();
                if (!model.InsertAxis2(true))
                {
                    throw new InvalidOperationException(
                        "SOLIDWORKS did not create the circular-pattern axis."
                    );
                }
                if (model.GetFeatureCount() != featureCountBeforeAxis + 1)
                {
                    throw new InvalidOperationException(
                        "Circular-pattern axis creation changed the feature " +
                        "tree unexpectedly."
                    );
                }
                circularAxis = model.IFeatureByPositionReverse(0);
                if (circularAxis == null)
                {
                    throw new InvalidOperationException(
                        "Could not retrieve the circular-pattern axis feature."
                    );
                }
                circularAxis.Name = step.Pattern.AxisName;
                RequireReferenceAxisDirection(
                    circularAxis,
                    direction1,
                    step.FeatureName
                );
            }
            return new PatternReferenceSketch
            {
                SketchFeature = sketchFeature,
                Direction1 = first,
                Direction2 = second,
                CircularAxis = circularAxis,
            };
        }

        private static void SelectCircularPatternAxis(Feature axis)
        {
            if (axis == null || !axis.Select2(true, 1))
            {
                throw new InvalidOperationException(
                    "Could not select the native circular-pattern axis."
                );
            }
        }

        private static void RequireReferenceAxisDirection(
            Feature axisFeature,
            double[] expectedDirection,
            string featureName)
        {
            RefAxis axis = axisFeature.GetSpecificFeature2() as RefAxis;
            if (axis == null)
            {
                throw new InvalidOperationException(
                    "Circular pattern '" + featureName +
                    "' does not have a readable reference axis."
                );
            }
            double[] parameters = axis.GetRefAxisParams() as double[];
            if (parameters == null || parameters.Length < 6)
            {
                throw new InvalidOperationException(
                    "Circular pattern '" + featureName +
                    "' returned incomplete reference-axis data."
                );
            }
            double[] actualDirection = Normalize(new[]
            {
                parameters[3] - parameters[0],
                parameters[4] - parameters[1],
                parameters[5] - parameters[2],
            });
            double alignment = Math.Abs(
                actualDirection[0] * expectedDirection[0] +
                actualDirection[1] * expectedDirection[1] +
                actualDirection[2] * expectedDirection[2]
            );
            if (alignment < 0.999)
            {
                throw new InvalidOperationException(
                    "Circular pattern '" + featureName +
                    "' reference axis does not align with its support normal."
                );
            }
        }

        private static void TraceCircularPatternDefinition(
            Feature patternFeature,
            ModelDoc2 model)
        {
            CircularPatternFeatureData definition =
                patternFeature.GetDefinition() as CircularPatternFeatureData;
            if (definition == null || !definition.AccessSelections(model, null))
            {
                Trace("Could not inspect stored circular-pattern definition");
                return;
            }
            try
            {
                object axisEntity = definition.Axis;
                RefAxis referenceAxis = axisEntity as RefAxis;
                Feature axisFeature = axisEntity as Feature;
                if (referenceAxis == null && axisFeature != null)
                {
                    referenceAxis = axisFeature.GetSpecificFeature2() as RefAxis;
                }
                double[] parameters = referenceAxis == null
                    ? null
                    : referenceAxis.GetRefAxisParams() as double[];
                Trace(
                    "Stored circular pattern axis_type=" + definition.GetAxisType() +
                    " instances=" + definition.TotalInstances +
                    " spacing=" + definition.Spacing +
                    " axis=" + (parameters == null
                        ? "unavailable"
                        : "[" + String.Join(",", parameters) + "]")
                );
            }
            finally
            {
                definition.ReleaseSelectionAccess();
            }
        }

        private static void SelectPatternDirection(
            ModelDoc2 model,
            SketchSegment direction,
            int mark)
        {
            SelectionMgr selectionManager = (SelectionMgr)model.SelectionManager;
            SelectData selection = selectionManager.CreateSelectData();
            selection.Mark = mark;
            if (direction == null || !direction.Select4(true, selection))
            {
                throw new InvalidOperationException(
                    "Could not select native pattern direction " + mark + "."
                );
            }
        }

        private static Feature CreateSketchDrivenPattern(
            SldWorks application,
            ModelDoc2 model,
            PartDoc part,
            ReplayStep step,
            Feature seedFeature)
        {
            SelectSketchSupport(application, model, part, step.Support);
            SketchManager sketchManager = model.SketchManager;
            sketchManager.InsertSketch(true);
            Feature sketchFeature = model.GetActiveSketch2() as Feature;
            Sketch sketch = model.IGetActiveSketch2();
            if (sketchFeature == null || sketch == null)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS did not create the mirror placement sketch."
                );
            }
            sketchFeature.Name = step.Pattern.PlacementSketchName;
            MathUtility mathUtility = application.IGetMathUtility();
            MathTransform modelToSketch = sketch.ModelToSketchTransform;
            var patternPoints = new List<SketchPoint>();
            foreach (double[] position in step.Pattern.PositionsMillimeters.Skip(1))
            {
                double[] point = ToSketchPoint(
                    step.Support.Frame,
                    position,
                    mathUtility,
                    modelToSketch
                );
                SketchPoint patternPoint = sketchManager.CreatePoint(
                    point[0], point[1], point[2]
                );
                if (patternPoint == null)
                {
                    throw new InvalidOperationException(
                        "SOLIDWORKS did not create a mirror-pattern point."
                    );
                }
                patternPoints.Add(patternPoint);
            }
            sketchManager.InsertSketch(true);

            model.ClearSelection2(true);
            if (!seedFeature.Select2(false, 4))
            {
                throw new InvalidOperationException(
                    "Could not select the sketch-pattern seed feature."
                );
            }
            SelectionMgr selectionManager =
                (SelectionMgr)model.SelectionManager;
            SelectData pointSelection = selectionManager.CreateSelectData();
            pointSelection.Mark = 32;
            foreach (SketchPoint patternPoint in patternPoints)
            {
                if (!patternPoint.Select4(true, pointSelection))
                {
                    throw new InvalidOperationException(
                        "Could not select a mirror-pattern point."
                    );
                }
            }
            if (!sketchFeature.Select2(true, 64))
            {
                throw new InvalidOperationException(
                    "Could not select the mirror-pattern sketch."
                );
            }

            SketchPatternFeatureData definition =
                (SketchPatternFeatureData)model.FeatureManager.CreateDefinition(
                    (int)swFeatureNameID_e.swFmSketchPattern
                );
            if (definition == null)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS did not create sketch-pattern feature data."
                );
            }
            definition.UseCentroid = true;
            definition.GeometryPattern = true;
            return model.FeatureManager.CreateFeature(definition);
        }

        private static Feature CreateNativeEdgeTreatment(
            ModelDoc2 model,
            ReplayStep step)
        {
            Feature targetFeature = FindFeatureByName(
                model,
                step.Support.TargetFeatureName
            );
            if (targetFeature == null)
            {
                throw new InvalidOperationException(
                    "Native edge target feature '" + step.Support.TargetFeatureName +
                    "' was not found."
                );
            }
            IList<Edge> edges;
            if (step.Support.Members != null &&
                step.Support.Members.Length > 0)
            {
                try
                {
                    edges = SelectFeatureEdgesByMembers(
                        targetFeature,
                        step.Support.Members
                    );
                }
                catch (InvalidOperationException canonicalError)
                {
                    // Curves can have equivalent geometry but different
                    // parameterization in the OCC and SOLIDWORKS kernels.
                    // Fall back only when the semantic group is unambiguous:
                    // it must resolve exactly as many native edges as the
                    // canonical contract expected.
                    IList<Edge> semanticEdges = SelectFeatureEdges(
                        targetFeature,
                        step.Support.Frame,
                        step.Support.Selector
                    );
                    if (semanticEdges.Count != step.Support.Members.Length)
                    {
                        throw new InvalidOperationException(
                            canonicalError.Message + " Semantic selector '" +
                            step.Support.Selector + "' found " +
                            semanticEdges.Count + " edge(s), but the canonical " +
                            "group requires " + step.Support.Members.Length + ".",
                            canonicalError
                        );
                    }
                    Trace(
                        "Canonical curve descriptors differed across kernels; " +
                        "used unambiguous semantic selector '" +
                        step.Support.Selector + "'."
                    );
                    edges = semanticEdges;
                }
            }
            else
            {
                edges = SelectFeatureEdges(
                    targetFeature,
                    step.Support.Frame,
                    step.Support.Selector
                );
            }
            Trace(
                "Resolved " + edges.Count + " canonical edge(s) for " +
                step.FeatureName
            );
            model.ClearSelection2(true);
            foreach (Edge edge in edges)
            {
                Entity entity = edge as Entity;
                if (entity == null || !entity.Select4(true, null))
                {
                    throw new InvalidOperationException(
                        "Could not select a resolved native model edge."
                    );
                }
            }

            Feature feature;
            if (step.Feature.Kind == "edge_chamfer")
            {
                feature = model.FeatureManager.InsertFeatureChamfer(
                    (int)swFeatureChamferOption_e.swFeatureChamferTangentPropagation,
                    (int)swChamferType_e.swChamferAngleDistance,
                    ToMeters(step.Feature.DistanceMillimeters),
                    Math.PI / 4.0,
                    0.0,
                    0.0,
                    0.0,
                    0.0
                );
            }
            else
            {
                object featureObject = model.FeatureManager.FeatureFillet3(
                    (int)swFeatureFilletOptions_e.swFeatureFilletUniformRadius |
                    (int)swFeatureFilletOptions_e.swFeatureFilletPropagate,
                    ToMeters(step.Feature.RadiusMillimeters),
                    0.0,
                    0.0,
                    (int)swFeatureFilletType_e.swFeatureFilletType_Simple,
                    (int)swFilletOverFlowType_e.swFilletOverFlowType_Default,
                    (int)swFeatureFilletProfileType_e.swFeatureFilletCircular,
                    null, null, null, null, null, null, null
                );
                feature = featureObject as Feature;
            }
            if (feature == null)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS did not create edge treatment '" +
                    step.FeatureName + "'."
                );
            }
            feature.Name = step.FeatureName;
            ConfigureFeatureDrivingDimension(
                feature,
                step.Feature.DrivingDimension,
                step.FeatureName
            );
            if (!model.EditRebuild3())
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS rebuild failed after '" + step.FeatureName + "'."
                );
            }
            return feature;
        }

        private static IList<Edge> SelectFeatureEdges(
            Feature feature,
            FrameSpec frame,
            string selector)
        {
            Dictionary<string, Edge> edges = FeatureEdges(feature);
            if (selector == "all_edges")
            {
                return edges.Values.ToList();
            }

            double[] normal = Normalize(frame.Normal);
            double[] xAxis = Normalize(frame.XAxis);
            double[] yAxis = Normalize(Cross(normal, xAxis));
            var measurements = edges.Values.Select(edge => new
            {
                Edge = edge,
                Normal = EdgeProjectionRange(edge, frame, normal),
                Front = EdgeProjectionRange(edge, frame, yAxis),
            }).ToList();
            const double tolerance = 1e-6;
            IList<Edge> selected;
            if (selector == "vertical_edges")
            {
                selected = measurements
                    .Where(item => item.Normal[1] - item.Normal[0] > tolerance)
                    .Select(item => item.Edge)
                    .ToList();
            }
            else if (selector == "top_outer_edges" ||
                selector == "bottom_outer_edges")
            {
                bool top = selector == "top_outer_edges";
                double extreme = top
                    ? measurements.Max(item => item.Normal[1])
                    : measurements.Min(item => item.Normal[0]);
                selected = measurements
                    .Where(item =>
                        item.Normal[1] - item.Normal[0] <= tolerance &&
                        Math.Abs((top ? item.Normal[1] : item.Normal[0]) - extreme)
                            <= tolerance
                    )
                    .Select(item => item.Edge)
                    .ToList();
            }
            else if (selector == "front_outer_edges" ||
                selector == "back_outer_edges" || selector == "end_edges")
            {
                double front = measurements.Max(item => item.Front[1]);
                double back = measurements.Min(item => item.Front[0]);
                selected = measurements
                    .Where(item =>
                        item.Front[1] - item.Front[0] <= tolerance &&
                        (selector != "back_outer_edges" &&
                            Math.Abs(item.Front[1] - front) <= tolerance ||
                         selector != "front_outer_edges" &&
                            Math.Abs(item.Front[0] - back) <= tolerance)
                    )
                    .Select(item => item.Edge)
                    .ToList();
            }
            else
            {
                throw new InvalidOperationException(
                    "Unsupported native edge selector '" + selector + "'."
                );
            }
            if (selected.Count == 0)
            {
                throw new InvalidOperationException(
                    "Native edge selector '" + selector + "' matched no edges."
                );
            }
            return selected;
        }

        private static Dictionary<string, Edge> FeatureEdges(Feature feature)
        {
            var edges = new Dictionary<string, Edge>();
            foreach (object faceObject in ObjectItems(feature.GetFaces()))
            {
                Face2 face = faceObject as Face2;
                if (face == null)
                {
                    continue;
                }
                foreach (object edgeObject in ObjectItems(face.GetEdges()))
                {
                    Edge edge = edgeObject as Edge;
                    if (edge != null)
                    {
                        edges[EdgeIdentityKey(edge)] = edge;
                    }
                }
            }
            if (edges.Count == 0)
            {
                throw new InvalidOperationException(
                    "The target feature exposes no selectable model edges."
                );
            }
            return edges;
        }

        private static IList<Edge> SelectFeatureEdgesByMembers(
            Feature feature,
            ReferenceMemberSpec[] members)
        {
            var remaining = FeatureEdges(feature).Values
                .Select(edge => new EdgeMatch
                {
                    Edge = edge,
                    BoundingBoxMillimeters = SampleEdgeBoundingBoxMillimeters(edge),
                })
                .ToList();
            foreach (EdgeMatch match in remaining)
            {
                match.CenterMillimeters = BoundingBoxCenter(
                    match.BoundingBoxMillimeters
                );
            }

            var selected = new List<Edge>();
            foreach (ReferenceMemberSpec member in members)
            {
                EdgeMatch best = remaining
                    .OrderBy(candidate => EdgeDescriptorError(candidate, member))
                    .FirstOrDefault();
                if (best == null)
                {
                    throw new InvalidOperationException(
                        "No native edge remained for canonical reference '" +
                        member.ReferenceId + "'."
                    );
                }
                double error = EdgeDescriptorError(best, member);
                if (error > 0.5)
                {
                    throw new InvalidOperationException(
                        "Canonical edge reference '" + member.ReferenceId +
                        "' did not match native topology within 0.5 mm " +
                        "(error " + error.ToString(
                            "R",
                            CultureInfo.InvariantCulture
                        ) + " mm)."
                    );
                }
                selected.Add(best.Edge);
                remaining.Remove(best);
            }
            return selected;
        }

        private sealed class EdgeMatch
        {
            public Edge Edge { get; set; }
            public double[] CenterMillimeters { get; set; }
            public double[] BoundingBoxMillimeters { get; set; }
        }

        private static double EdgeDescriptorError(
            EdgeMatch candidate,
            ReferenceMemberSpec expected)
        {
            if (expected.CenterMillimeters == null ||
                expected.CenterMillimeters.Length != 3 ||
                expected.BoundingBoxMillimeters == null ||
                expected.BoundingBoxMillimeters.Length != 6)
            {
                throw new InvalidOperationException(
                    "Canonical edge reference '" + expected.ReferenceId +
                    "' has an invalid geometric descriptor."
                );
            }
            double maximum = 0.0;
            for (int index = 0; index < 3; index += 1)
            {
                maximum = Math.Max(
                    maximum,
                    Math.Abs(
                        candidate.CenterMillimeters[index] -
                        expected.CenterMillimeters[index]
                    )
                );
            }
            for (int index = 0; index < 6; index += 1)
            {
                maximum = Math.Max(
                    maximum,
                    Math.Abs(
                        candidate.BoundingBoxMillimeters[index] -
                        expected.BoundingBoxMillimeters[index]
                    )
                );
            }
            return maximum;
        }

        private static double[] SampleEdgeBoundingBoxMillimeters(Edge edge)
        {
            CurveParamData parameters = edge.GetCurveParams3();
            if (parameters == null)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS did not expose edge parameter data."
                );
            }
            var bounds = new[]
            {
                Double.PositiveInfinity,
                Double.PositiveInfinity,
                Double.PositiveInfinity,
                Double.NegativeInfinity,
                Double.NegativeInfinity,
                Double.NegativeInfinity,
            };
            const int sampleCount = 64;
            for (int index = 0; index <= sampleCount; index += 1)
            {
                double fraction = (double)index / sampleCount;
                double parameter = parameters.UMinValue +
                    (parameters.UMaxValue - parameters.UMinValue) * fraction;
                double[] point = edge.Evaluate(parameter) as double[];
                if (point == null || point.Length < 3)
                {
                    throw new InvalidOperationException(
                        "SOLIDWORKS could not sample a canonical target edge."
                    );
                }
                for (int axis = 0; axis < 3; axis += 1)
                {
                    double millimeters = point[axis] * MillimetersPerMeter;
                    bounds[axis] = Math.Min(bounds[axis], millimeters);
                    bounds[axis + 3] = Math.Max(
                        bounds[axis + 3],
                        millimeters
                    );
                }
            }
            return bounds;
        }

        private static double[] BoundingBoxCenter(double[] bounds)
        {
            return new[]
            {
                (bounds[0] + bounds[3]) / 2.0,
                (bounds[1] + bounds[4]) / 2.0,
                (bounds[2] + bounds[5]) / 2.0,
            };
        }

        private static string EdgeIdentityKey(Edge edge)
        {
            CurveParamData parameters = edge.GetCurveParams3();
            if (parameters == null)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS did not expose edge parameter data."
                );
            }
            double middle =
                (parameters.UMinValue + parameters.UMaxValue) / 2.0;
            string start = EdgePointKey(edge, parameters.UMinValue);
            string end = EdgePointKey(edge, parameters.UMaxValue);
            string midpoint = EdgePointKey(edge, middle);
            if (String.CompareOrdinal(start, end) > 0)
            {
                string swap = start;
                start = end;
                end = swap;
            }
            return start + "|" + midpoint + "|" + end;
        }

        private static string EdgePointKey(Edge edge, double parameter)
        {
            double[] evaluation = edge.Evaluate(parameter) as double[];
            if (evaluation == null || evaluation.Length < 3)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS could not evaluate a target edge."
                );
            }
            return String.Join(
                ",",
                evaluation.Take(3).Select(value =>
                    Math.Round(value, 9).ToString("R", CultureInfo.InvariantCulture)
                )
            );
        }

        private static double[] EdgeProjectionRange(
            Edge edge,
            FrameSpec frame,
            double[] direction)
        {
            CurveParamData parameters = edge.GetCurveParams3();
            if (parameters == null)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS did not expose edge parameter data."
                );
            }
            double minimum = Double.PositiveInfinity;
            double maximum = Double.NegativeInfinity;
            for (int index = 0; index <= 4; index++)
            {
                double parameter = parameters.UMinValue +
                    (parameters.UMaxValue - parameters.UMinValue) * index / 4.0;
                double[] evaluation = edge.Evaluate(parameter) as double[];
                if (evaluation == null || evaluation.Length < 3)
                {
                    continue;
                }
                double[] relative = new[]
                {
                    evaluation[0] - ToMeters(frame.OriginMillimeters[0]),
                    evaluation[1] - ToMeters(frame.OriginMillimeters[1]),
                    evaluation[2] - ToMeters(frame.OriginMillimeters[2]),
                };
                double projection = Dot(relative, direction);
                minimum = Math.Min(minimum, projection);
                maximum = Math.Max(maximum, projection);
            }
            if (Double.IsInfinity(minimum))
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS could not evaluate a target edge."
                );
            }
            return new[] { minimum, maximum };
        }

        private static void PublishNativeReferences(
            PartDoc part,
            Feature feature,
            ReplayStep step)
        {
            foreach (NativeReferenceSpec reference in
                step.PublishReferences ?? new NativeReferenceSpec[0])
            {
                if (!String.Equals(
                    reference.EntityType,
                    "face",
                    StringComparison.Ordinal))
                {
                    throw new InvalidOperationException(
                        "Unsupported native reference entity type '" +
                        reference.EntityType + "' for '" +
                        reference.ReferenceId + "'."
                    );
                }
                NativeReferenceSelector selector = reference.Selector;
                if (selector == null)
                {
                    throw new InvalidOperationException(
                        "Native reference '" + reference.ReferenceId +
                        "' is missing its geometric selector."
                    );
                }
                Face2 face;
                if (String.Equals(
                    selector.Kind,
                    "planar_face_direction",
                    StringComparison.Ordinal))
                {
                    face = FindPlanarFace(feature, selector.Direction);
                }
                else if (String.Equals(
                    selector.Kind,
                    "planar_face_geometry",
                    StringComparison.Ordinal))
                {
                    face = FindPlanarFaceByGeometry(
                        feature,
                        selector.Direction,
                        selector.CenterMillimeters,
                        selector.AreaSquareMillimeters
                    );
                }
                else if (String.Equals(
                    selector.Kind,
                    "largest_non_planar_face",
                    StringComparison.Ordinal))
                {
                    face = FindLargestNonPlanarFace(feature);
                }
                else
                {
                    throw new InvalidOperationException(
                        "Unsupported native reference selector '" +
                        selector.Kind + "' for '" + reference.ReferenceId + "'."
                    );
                }
                if (face == null)
                {
                    throw new InvalidOperationException(
                        "Could not resolve native face '" + reference.ReferenceId +
                        "' on '" + feature.Name + "'."
                    );
                }
                if (!part.SetEntityName(face, reference.EntityName))
                {
                    throw new InvalidOperationException(
                        "Could not publish native face name '" +
                        reference.EntityName + "'."
                    );
                }
            }
        }

        private static Face2 FindPlanarFace(Feature feature, double[] direction)
        {
            Face2 bestFace = null;
            double bestAlignment = 0.94;
            double bestProjection = Double.NegativeInfinity;
            foreach (object faceObject in ObjectItems(feature.GetFaces()))
            {
                Face2 face = (Face2)faceObject;
                Surface surface = face.IGetSurface();
                double[] normal = face.Normal as double[];
                double[] box = face.GetBox() as double[];
                if (surface == null || !surface.IsPlane() ||
                    normal == null || normal.Length < 3 ||
                    box == null || box.Length < 6)
                {
                    continue;
                }
                double alignment = Dot(normal, direction);
                if (alignment < bestAlignment)
                {
                    continue;
                }
                double[] center = new[]
                {
                    (box[0] + box[3]) / 2.0,
                    (box[1] + box[4]) / 2.0,
                    (box[2] + box[5]) / 2.0,
                };
                double projection = Dot(center, direction);
                if (alignment > bestAlignment + 1e-6 ||
                    projection > bestProjection)
                {
                    bestFace = face;
                    bestAlignment = alignment;
                    bestProjection = projection;
                }
            }
            return bestFace;
        }

        private static Face2 FindPlanarFaceByGeometry(
            Feature feature,
            double[] direction,
            double[] centerMillimeters,
            double? areaSquareMillimeters)
        {
            if (direction == null || direction.Length < 3 ||
                centerMillimeters == null || centerMillimeters.Length < 3)
            {
                throw new InvalidOperationException(
                    "A planar-face geometry selector requires a normal and center."
                );
            }

            double[] expectedCenter = new[]
            {
                ToMeters(centerMillimeters[0]),
                ToMeters(centerMillimeters[1]),
                ToMeters(centerMillimeters[2]),
            };
            double expectedArea = areaSquareMillimeters.HasValue
                ? areaSquareMillimeters.Value * 1e-6
                : 0.0;
            Face2 bestFace = null;
            double bestScore = Double.PositiveInfinity;
            foreach (object faceObject in ObjectItems(feature.GetFaces()))
            {
                Face2 face = (Face2)faceObject;
                Surface surface = face.IGetSurface();
                double[] normal = face.Normal as double[];
                double[] box = face.GetBox() as double[];
                if (surface == null || !surface.IsPlane() ||
                    normal == null || normal.Length < 3 ||
                    box == null || box.Length < 6)
                {
                    continue;
                }

                double alignment = Dot(normal, direction);
                if (alignment < 0.98)
                {
                    continue;
                }
                double[] center = new[]
                {
                    (box[0] + box[3]) / 2.0,
                    (box[1] + box[4]) / 2.0,
                    (box[2] + box[5]) / 2.0,
                };
                double[] delta = new[]
                {
                    center[0] - expectedCenter[0],
                    center[1] - expectedCenter[1],
                    center[2] - expectedCenter[2],
                };
                double planeDistanceMillimeters =
                    Math.Abs(Dot(delta, direction)) * 1000.0;
                if (planeDistanceMillimeters > 0.5)
                {
                    continue;
                }
                double centerDistanceMillimeters = Math.Sqrt(
                    Dot(delta, delta)
                ) * 1000.0;
                double areaError = 0.0;
                if (expectedArea > 0.0)
                {
                    areaError = Math.Abs(face.GetArea() - expectedArea) /
                        expectedArea;
                }
                double score = planeDistanceMillimeters * 100.0 +
                    centerDistanceMillimeters + areaError * 10.0 +
                    (1.0 - alignment) * 100.0;
                if (score < bestScore)
                {
                    bestFace = face;
                    bestScore = score;
                }
            }
            return bestFace;
        }

        private static Face2 FindLargestNonPlanarFace(Feature feature)
        {
            Face2 bestFace = null;
            double bestArea = Double.NegativeInfinity;
            foreach (object faceObject in ObjectItems(feature.GetFaces()))
            {
                Face2 face = (Face2)faceObject;
                Surface surface = face.IGetSurface();
                if (surface == null || surface.IsPlane())
                {
                    continue;
                }
                double area = face.GetArea();
                if (area > bestArea)
                {
                    bestFace = face;
                    bestArea = area;
                }
            }
            return bestFace;
        }

        private static Feature FindFeatureByName(ModelDoc2 model, string name)
        {
            Feature current = model.FirstFeature() as Feature;
            while (current != null)
            {
                Feature match = FindFeatureAndChildren(current, name);
                if (match != null)
                {
                    return match;
                }
                current = current.GetNextFeature() as Feature;
            }
            return null;
        }

        private static Feature FindFeatureAndChildren(
            Feature feature,
            string name)
        {
            if (String.Equals(feature.Name, name, StringComparison.Ordinal))
            {
                return feature;
            }
            Feature child = feature.GetFirstSubFeature() as Feature;
            while (child != null)
            {
                Feature match = FindFeatureAndChildren(child, name);
                if (match != null)
                {
                    return match;
                }
                child = child.GetNextSubFeature() as Feature;
            }
            return null;
        }

        private sealed class ParameterVerificationResult
        {
            public int DeclaredParameterCount { get; set; }
            public int VerifiedParameterCount { get; set; }
            public int VerifiedDimensionCount { get; set; }
            public int DeclaredHelperCount { get; set; }
            public int VerifiedHelperCount { get; set; }
            public string[] VerifiedParameterIds { get; set; }
            public string[] VerifiedHelperNames { get; set; }
        }

        private static NativeHealthResult InspectNativeHealth(
            ModelDoc2 model,
            ReplayPlan plan)
        {
            var featureResults = new List<FeatureHealthResult>();
            var sketchResults = new List<SketchHealthResult>();
            var inspectedFeatures = new HashSet<string>(StringComparer.Ordinal);
            var inspectedSketches = new HashSet<string>(StringComparer.Ordinal);

            foreach (ReplayStep step in plan.Features)
            {
                if (!String.IsNullOrWhiteSpace(step.FeatureName) &&
                    inspectedFeatures.Add(step.FeatureName))
                {
                    Feature nativeFeature = FindFeatureByName(
                        model,
                        step.FeatureName
                    );
                    if (nativeFeature == null)
                    {
                        throw new InvalidOperationException(
                            "Health inspection could not find feature '" +
                            step.FeatureName + "'."
                        );
                    }
                    bool isWarning;
                    int errorCode = nativeFeature.GetErrorCode2(out isWarning);
                    featureResults.Add(
                        new FeatureHealthResult
                        {
                            FeatureName = step.FeatureName,
                            ErrorCode = errorCode,
                            IsWarning = errorCode != 0 && isWarning,
                            Status = errorCode == 0
                                ? "healthy"
                                : isWarning ? "warning" : "error",
                        }
                    );
                }

                if (!String.IsNullOrWhiteSpace(step.SketchName) &&
                    inspectedSketches.Add(step.SketchName))
                {
                    Feature sketchFeature = FindFeatureByName(
                        model,
                        step.SketchName
                    );
                    Sketch sketch = sketchFeature == null
                        ? null
                        : sketchFeature.GetSpecificFeature2() as Sketch;
                    if (sketch == null)
                    {
                        throw new InvalidOperationException(
                            "Health inspection could not read sketch '" +
                            step.SketchName + "'."
                        );
                    }
                    int constraintCode = sketch.GetConstrainedStatus();
                    SketchConstraintPlan constraintPlan = step.Sketch == null
                        ? null
                        : step.Sketch.ConstraintPlan;
                    bool fullyDefinedRequired = constraintPlan != null &&
                        constraintPlan.RequireFullyDefined;
                    bool validConstraintState = constraintCode !=
                            (int)swConstrainedStatus_e.swOverConstrained &&
                        constraintCode !=
                            (int)swConstrainedStatus_e.swNoSolution &&
                        constraintCode !=
                            (int)swConstrainedStatus_e.swInvalidSolution;
                    sketchResults.Add(
                        new SketchHealthResult
                        {
                            SketchName = step.SketchName,
                            ConstraintCode = constraintCode,
                            ConstraintStatus = ConstraintStatusName(
                                constraintCode
                            ),
                            IsValid = validConstraintState &&
                                (!fullyDefinedRequired || constraintCode ==
                                    (int)swConstrainedStatus_e
                                        .swFullyConstrained),
                            ConstraintStrategy = constraintPlan == null
                                ? "none"
                                : constraintPlan.Strategy,
                            FullyDefinedRequired = fullyDefinedRequired,
                        }
                    );
                }
            }

            return new NativeHealthResult
            {
                Features = featureResults.ToArray(),
                Sketches = sketchResults.ToArray(),
                FeatureErrorCount = featureResults.Count(item =>
                    item.ErrorCode != 0 && !item.IsWarning),
                FeatureWarningCount = featureResults.Count(item =>
                    item.ErrorCode != 0 && item.IsWarning),
                FullyDefinedSketchCount = sketchResults.Count(item =>
                    item.ConstraintCode ==
                    (int)swConstrainedStatus_e.swFullyConstrained),
                UnderDefinedSketchCount = sketchResults.Count(item =>
                    item.ConstraintCode ==
                    (int)swConstrainedStatus_e.swUnderConstrained),
            };
        }

        private static string ConstraintStatusName(int constraintCode)
        {
            switch ((swConstrainedStatus_e)constraintCode)
            {
                case swConstrainedStatus_e.swUnknownConstraint:
                    return "unknown";
                case swConstrainedStatus_e.swUnderConstrained:
                    return "under_defined";
                case swConstrainedStatus_e.swFullyConstrained:
                    return "fully_defined";
                case swConstrainedStatus_e.swOverConstrained:
                    return "over_defined";
                case swConstrainedStatus_e.swNoSolution:
                    return "no_solution";
                case swConstrainedStatus_e.swInvalidSolution:
                    return "invalid_solution";
                case swConstrainedStatus_e.swAutosolveOff:
                    return "autosolve_off";
                default:
                    return "unrecognized_" + constraintCode;
            }
        }

        private static void RequireHealthyModel(
            NativeHealthResult health,
            string stage)
        {
            FeatureHealthResult[] errors = health.Features
                .Where(item => item.ErrorCode != 0 && !item.IsWarning)
                .ToArray();
            SketchHealthResult[] invalidSketches = health.Sketches
                .Where(item => !item.IsValid)
                .ToArray();
            if (errors.Length == 0 && invalidSketches.Length == 0)
            {
                return;
            }
            var problems = new List<string>();
            problems.AddRange(errors.Select(item =>
                item.FeatureName + " feature error " + item.ErrorCode));
            problems.AddRange(invalidSketches.Select(item =>
                item.SketchName + " sketch status " + item.ConstraintStatus));
            throw new InvalidOperationException(
                "SOLIDWORKS model is unhealthy " + stage + ": " +
                String.Join(", ", problems) + "."
            );
        }

        private static void ApplyParameterMutations(
            ModelDoc2 model,
            ReplayPlan plan,
            ParameterMutation[] mutations)
        {
            var bindings = new Dictionary<string, NativeParameterBinding>(
                StringComparer.Ordinal
            );
            foreach (ReplayStep step in plan.Features)
            {
                foreach (NativeParameterBinding binding in
                    step.ParameterBindings ?? new NativeParameterBinding[0])
                {
                    if (bindings.ContainsKey(binding.ParameterId))
                    {
                        throw new InvalidOperationException(
                            "Replay plan contains duplicate parameter binding '" +
                            binding.ParameterId + "'."
                        );
                    }
                    bindings.Add(binding.ParameterId, binding);
                }
            }

            var mutated = new HashSet<string>(StringComparer.Ordinal);
            var nativeValues = bindings.ToDictionary(
                item => item.Key,
                item => item.Value.Value,
                StringComparer.Ordinal
            );
            foreach (ParameterMutation mutation in mutations)
            {
                if (!mutated.Add(mutation.ParameterId))
                {
                    throw new InvalidOperationException(
                        "Mutation document repeats parameter '" +
                        mutation.ParameterId + "'."
                    );
                }
                NativeParameterBinding binding;
                if (!bindings.TryGetValue(mutation.ParameterId, out binding))
                {
                    throw new InvalidOperationException(
                        "Mutation references unknown parameter '" +
                        mutation.ParameterId + "'."
                    );
                }
                if (!String.Equals(
                    mutation.Unit,
                    binding.Unit,
                    StringComparison.OrdinalIgnoreCase))
                {
                    throw new InvalidOperationException(
                        "Mutation unit for '" + mutation.ParameterId +
                        "' does not match its replay binding."
                    );
                }

                nativeValues[mutation.ParameterId] = ResolveNativeMutationValue(
                    binding,
                    mutation.Value
                );
            }
            ValidateNativeMutationSet(plan, nativeValues);

            foreach (ParameterMutation mutation in mutations)
            {
                NativeParameterBinding binding = bindings[mutation.ParameterId];
                double nativeValue = nativeValues[mutation.ParameterId];
                if (String.Equals(
                    binding.BindingKind,
                    "named_dimension",
                    StringComparison.Ordinal))
                {
                    SetNamedDimension(model, binding, nativeValue);
                }
                else if (String.Equals(
                    binding.BindingKind,
                    "feature_property",
                    StringComparison.Ordinal))
                {
                    SetFeatureProperty(model, binding, nativeValue);
                }
                else
                {
                    throw new InvalidOperationException(
                        "Parameter '" + mutation.ParameterId +
                        "' uses unsupported mutation strategy '" +
                        binding.BindingKind + "'."
                    );
                }
                binding.Value = nativeValue;
                if (String.Equals(
                    binding.MutationMode,
                    "absolute_same_side",
                    StringComparison.Ordinal))
                {
                    binding.SourceValue = mutation.Value;
                }
            }
        }

        private static void ValidateNativeMutationSet(
            ReplayPlan plan,
            IDictionary<string, double> values)
        {
            foreach (ReplayStep step in plan.Features)
            {
                if (step.Feature != null && String.Equals(
                    step.Feature.Kind,
                    "countersink",
                    StringComparison.Ordinal))
                {
                    double holeDiameter = values[
                        step.Id + ".feature.diameter"
                    ];
                    double countersinkDiameter = values[
                        step.Id + ".feature.countersink_diameter"
                    ];
                    if (countersinkDiameter <= holeDiameter)
                    {
                        throw new InvalidOperationException(
                            "Countersink '" + step.Id + "' requires its " +
                            "countersink diameter to remain larger than its " +
                            "hole diameter."
                        );
                    }
                }

                if (step.Pattern == null || !String.Equals(
                    step.Pattern.Kind,
                    "linear_pattern",
                    StringComparison.Ordinal))
                {
                    continue;
                }
                double count1 = values[step.Id + ".pattern.count_1"];
                double count2 = values[step.Id + ".pattern.count_2"];
                double spacing1 = values[step.Id + ".pattern.spacing_1"];
                double spacing2 = values[step.Id + ".pattern.spacing_2"];
                if (count1 * count2 < 2.0)
                {
                    throw new InvalidOperationException(
                        "Linear pattern '" + step.Id + "' must retain at " +
                        "least two instances; regenerate the package to " +
                        "remove the pattern."
                    );
                }
                if (count1 > 1.0 && spacing1 <= 0.0)
                {
                    throw new InvalidOperationException(
                        "Linear pattern '" + step.Id + "' requires positive " +
                        "direction-1 spacing when count 1 exceeds one."
                    );
                }
                if (count2 > 1.0 && spacing2 <= 0.0)
                {
                    throw new InvalidOperationException(
                        "Linear pattern '" + step.Id + "' requires positive " +
                        "direction-2 spacing when count 2 exceeds one."
                    );
                }
            }
        }

        private static double ResolveNativeMutationValue(
            NativeParameterBinding binding,
            double requestedValue)
        {
            if (Double.IsNaN(requestedValue) || Double.IsInfinity(requestedValue))
            {
                throw new InvalidOperationException(
                    "Parameter '" + binding.ParameterId +
                    "' requires a finite mutation value."
                );
            }
            double nativeValue = requestedValue;
            if (!String.Equals(
                binding.MutationMode,
                "absolute_same_side",
                StringComparison.Ordinal))
            {
                return ValidateNativeMutationRange(binding, nativeValue);
            }
            if (!binding.SourceValue.HasValue ||
                Math.Abs(binding.SourceValue.Value) <= 1e-12)
            {
                throw new InvalidOperationException(
                    "Parameter '" + binding.ParameterId +
                    "' is missing its signed source value."
                );
            }
            if (Math.Abs(requestedValue) <= 1e-12 ||
                binding.SourceValue.Value * requestedValue <= 0.0)
            {
                throw new InvalidOperationException(
                    "Parameter '" + binding.ParameterId +
                    "' cannot cross or land on the sketch origin during an " +
                    "in-place edit. Regenerate the part to change sides."
                );
            }
            nativeValue = Math.Abs(requestedValue);
            return ValidateNativeMutationRange(binding, nativeValue);
        }

        private static double ValidateNativeMutationRange(
            NativeParameterBinding binding,
            double nativeValue)
        {
            if (binding.IntegerOnly &&
                Math.Abs(nativeValue - Math.Round(nativeValue)) > 1e-9)
            {
                throw new InvalidOperationException(
                    "Parameter '" + binding.ParameterId +
                    "' requires a whole-number value."
                );
            }
            if (binding.MinimumValue.HasValue &&
                (nativeValue < binding.MinimumValue.Value ||
                 (nativeValue == binding.MinimumValue.Value &&
                  !binding.MinimumInclusive)))
            {
                throw new InvalidOperationException(
                    "Parameter '" + binding.ParameterId + "' must be " +
                    (binding.MinimumInclusive ? "at least " : "greater than ") +
                    binding.MinimumValue.Value.ToString(CultureInfo.InvariantCulture) +
                    "."
                );
            }
            if (binding.MaximumValue.HasValue &&
                (nativeValue > binding.MaximumValue.Value ||
                 (nativeValue == binding.MaximumValue.Value &&
                  !binding.MaximumInclusive)))
            {
                throw new InvalidOperationException(
                    "Parameter '" + binding.ParameterId + "' must be " +
                    (binding.MaximumInclusive ? "at most " : "less than ") +
                    binding.MaximumValue.Value.ToString(CultureInfo.InvariantCulture) +
                    "."
                );
            }
            return nativeValue;
        }

        private static void SetNamedDimension(
            ModelDoc2 model,
            NativeParameterBinding binding,
            double value)
        {
            string qualifiedName = binding.NativeName + "@" + binding.OwnerName;
            Dimension dimension = model.Parameter(qualifiedName) as Dimension;
            if (dimension == null)
            {
                throw new InvalidOperationException(
                    "Cannot mutate missing dimension '" + qualifiedName + "'."
                );
            }
            int status = dimension.SetSystemValue3(
                ToSystemValue(value, binding.Unit),
                (int)swSetValueInConfiguration_e.swSetValue_InAllConfigurations,
                null
            );
            if (status != (int)swSetValueReturnStatus_e.swSetValue_Successful)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS rejected mutation for dimension '" +
                    qualifiedName + "'."
                );
            }
        }

        private static void SetFeatureProperty(
            ModelDoc2 model,
            NativeParameterBinding binding,
            double value)
        {
            Feature owner = FindFeatureByName(model, binding.OwnerName);
            if (owner == null)
            {
                throw new InvalidOperationException(
                    "Cannot mutate missing feature '" + binding.OwnerName + "'."
                );
            }
            object definition = owner.GetDefinition();
            if (definition == null)
            {
                throw new InvalidOperationException(
                    "Feature '" + binding.OwnerName +
                    "' exposes no editable feature data."
                );
            }
            string propertyName = ResolveFeaturePropertyName(
                definition,
                binding
            );
            bool selectionAccessed;
            try
            {
                selectionAccessed = TryAccessSelections(definition, model);
            }
            catch (Exception error)
            {
                throw new InvalidOperationException(
                    "Could not access selections for feature-data property '" +
                    propertyName + "@" + binding.OwnerName + "'.",
                    error
                );
            }
            try
            {
                object nativeValue = String.Equals(
                    binding.Unit,
                    "count",
                    StringComparison.OrdinalIgnoreCase
                )
                    ? (object)Convert.ToInt32(
                        Math.Round(value),
                        CultureInfo.InvariantCulture
                    )
                    : ToSystemValue(value, binding.Unit);
                try
                {
                    definition.GetType().InvokeMember(
                        propertyName,
                        BindingFlags.SetProperty,
                        null,
                        definition,
                        new[] { nativeValue },
                        CultureInfo.InvariantCulture
                    );
                }
                catch (Exception error)
                {
                    throw new InvalidOperationException(
                        "Could not set feature-data property '" +
                        propertyName + "@" + binding.OwnerName + "'.",
                        error
                    );
                }
                if (!owner.ModifyDefinition(definition, model, null))
                {
                    throw new InvalidOperationException(
                        "SOLIDWORKS rejected mutation of '" + propertyName +
                        "@" + binding.OwnerName + "'."
                    );
                }
            }
            finally
            {
                if (selectionAccessed)
                {
                    TryReleaseSelectionAccess(definition);
                }
            }
        }

        private static bool TryAccessSelections(
            object definition,
            ModelDoc2 model)
        {
            WizardHoleFeatureData2 holeData =
                definition as WizardHoleFeatureData2;
            if (holeData != null)
            {
                if (!holeData.AccessSelections(model, null))
                {
                    throw new InvalidOperationException(
                        "SOLIDWORKS denied Hole Wizard selection access."
                    );
                }
                return true;
            }
            CircularPatternFeatureData circularData =
                definition as CircularPatternFeatureData;
            if (circularData != null)
            {
                if (!circularData.AccessSelections(model, null))
                {
                    throw new InvalidOperationException(
                        "SOLIDWORKS denied circular-pattern selection access."
                    );
                }
                return true;
            }
            LinearPatternFeatureData linearData =
                definition as LinearPatternFeatureData;
            if (linearData != null)
            {
                if (!linearData.AccessSelections(model, null))
                {
                    throw new InvalidOperationException(
                        "SOLIDWORKS denied linear-pattern selection access."
                    );
                }
                return true;
            }
            try
            {
                object result = definition.GetType().InvokeMember(
                    "AccessSelections",
                    BindingFlags.InvokeMethod,
                    null,
                    definition,
                    new object[] { model, null },
                    CultureInfo.InvariantCulture
                );
                if (result is bool && !(bool)result)
                {
                    throw new InvalidOperationException(
                        "SOLIDWORKS denied feature-data selection access."
                    );
                }
                return true;
            }
            catch (MissingMethodException)
            {
                return false;
            }
        }

        private static void TryReleaseSelectionAccess(object definition)
        {
            WizardHoleFeatureData2 holeData =
                definition as WizardHoleFeatureData2;
            if (holeData != null)
            {
                holeData.ReleaseSelectionAccess();
                return;
            }
            CircularPatternFeatureData circularData =
                definition as CircularPatternFeatureData;
            if (circularData != null)
            {
                circularData.ReleaseSelectionAccess();
                return;
            }
            LinearPatternFeatureData linearData =
                definition as LinearPatternFeatureData;
            if (linearData != null)
            {
                linearData.ReleaseSelectionAccess();
                return;
            }
            try
            {
                definition.GetType().InvokeMember(
                    "ReleaseSelectionAccess",
                    BindingFlags.InvokeMethod,
                    null,
                    definition,
                    null,
                    CultureInfo.InvariantCulture
                );
            }
            catch (MissingMethodException)
            {
            }
        }

        private static ParameterVerificationResult VerifyReplay(
            ModelDoc2 model,
            PartDoc part,
            ReplayPlan plan)
        {
            var featureNames = new HashSet<string>(StringComparer.Ordinal);
            object firstFeatureObject = model.FirstFeature();
            Feature current = firstFeatureObject as Feature;
            while (current != null)
            {
                CollectFeatureAndChildren(current, featureNames);
                current = current.GetNextFeature() as Feature;
            }

            int declaredParameterCount = 0;
            int verifiedParameterCount = 0;
            int verifiedDimensionCount = 0;
            int declaredHelperCount = 0;
            int verifiedHelperCount = 0;
            var verifiedParameterIds = new List<string>();
            var verifiedHelperNames = new List<string>();
            foreach (ReplayStep step in plan.Features)
            {
                if (!String.IsNullOrWhiteSpace(step.SketchName) &&
                    !featureNames.Contains(step.SketchName))
                {
                    throw new InvalidOperationException(
                        "Saved history is missing sketch '" + step.SketchName + "'."
                    );
                }
                if (!featureNames.Contains(step.FeatureName))
                {
                    throw new InvalidOperationException(
                        "Saved history is missing feature '" + step.FeatureName + "'."
                    );
                }
                foreach (string helperName in ExpectedNativeHelperNames(step))
                {
                    declaredHelperCount += 1;
                    if (!featureNames.Contains(helperName))
                    {
                        throw new InvalidOperationException(
                            "Saved history is missing helper '" + helperName +
                            "' for feature '" + step.FeatureName + "'."
                        );
                    }
                    verifiedHelperCount += 1;
                    verifiedHelperNames.Add(helperName);
                }

                NativeParameterBinding[] bindings =
                    step.ParameterBindings ?? new NativeParameterBinding[0];
                foreach (NativeParameterBinding binding in bindings)
                {
                    declaredParameterCount += 1;
                    if (String.Equals(
                        binding.BindingKind,
                        "named_dimension",
                        StringComparison.Ordinal))
                    {
                        VerifyDimension(
                            model,
                            new DimensionSpec
                            {
                                ParameterId = binding.ParameterId,
                                NativeName = binding.NativeName,
                                ValueMillimeters = binding.Value,
                                Unit = binding.Unit,
                            },
                            binding.OwnerName
                        );
                        verifiedDimensionCount += 1;
                    }
                    else if (String.Equals(
                        binding.BindingKind,
                        "feature_property",
                        StringComparison.Ordinal))
                    {
                        VerifyFeaturePropertyBinding(model, binding);
                    }
                    else
                    {
                        throw new InvalidOperationException(
                            "Unsupported native parameter binding kind '" +
                            binding.BindingKind + "' for '" +
                            binding.ParameterId + "'."
                        );
                    }
                    verifiedParameterCount += 1;
                    verifiedParameterIds.Add(binding.ParameterId);
                }

                foreach (NativeReferenceSpec reference in
                    step.PublishReferences ?? new NativeReferenceSpec[0])
                {
                    if (!String.Equals(
                        reference.EntityType,
                        "face",
                        StringComparison.Ordinal))
                    {
                        throw new InvalidOperationException(
                            "Saved-history verification does not support native " +
                            "reference type '" + reference.EntityType + "'."
                        );
                    }
                    if (part.GetEntityByName(
                        reference.EntityName,
                        (int)swSelectType_e.swSelFACES
                    ) == null)
                    {
                        throw new InvalidOperationException(
                            "Saved history is missing named face '" +
                            reference.EntityName + "'."
                        );
                    }
                }
            }
            return new ParameterVerificationResult
            {
                DeclaredParameterCount = declaredParameterCount,
                VerifiedParameterCount = verifiedParameterCount,
                VerifiedDimensionCount = verifiedDimensionCount,
                DeclaredHelperCount = declaredHelperCount,
                VerifiedHelperCount = verifiedHelperCount,
                VerifiedParameterIds = verifiedParameterIds.ToArray(),
                VerifiedHelperNames = verifiedHelperNames.ToArray(),
            };
        }

        private static IEnumerable<string> ExpectedNativeHelperNames(
            ReplayStep step)
        {
            if (step.Support != null &&
                String.Equals(
                    step.Support.Kind,
                    "offset_plane",
                    StringComparison.Ordinal))
            {
                yield return step.Support.Name;
            }
            if (step.Pattern == null)
            {
                yield break;
            }

            yield return step.Pattern.SeedFeatureName;
            if (String.Equals(
                step.Pattern.Kind,
                "circular_pattern",
                StringComparison.Ordinal))
            {
                yield return step.Pattern.ReferenceSketchName;
                yield return step.Pattern.AxisName;
            }
            else if (String.Equals(
                step.Pattern.Kind,
                "linear_pattern",
                StringComparison.Ordinal))
            {
                yield return step.Pattern.ReferenceSketchName;
            }
            else if (String.Equals(
                step.Pattern.Kind,
                "mirror_pattern",
                StringComparison.Ordinal))
            {
                yield return step.Pattern.PlacementSketchName;
            }
        }

        private static IDictionary<string, byte[]> CapturePersistentReferenceIds(
            ModelDoc2 model,
            PartDoc part,
            ReplayPlan plan)
        {
            var captured = new Dictionary<string, byte[]>(StringComparer.Ordinal);
            foreach (ReplayStep step in plan.Features)
            {
                foreach (NativeReferenceSpec reference in
                    step.PublishReferences ?? new NativeReferenceSpec[0])
                {
                    if (captured.ContainsKey(reference.ReferenceId))
                    {
                        throw new InvalidOperationException(
                            "Duplicate native reference ID '" +
                            reference.ReferenceId + "'."
                        );
                    }
                    object entity = part.GetEntityByName(
                        reference.EntityName,
                        ReferenceSelectType(reference.EntityType)
                    );
                    if (entity == null)
                    {
                        throw new InvalidOperationException(
                            "Cannot capture persistent ID for missing entity '" +
                            reference.EntityName + "'."
                        );
                    }
                    object rawIdentifier = model.Extension.GetPersistReference3(
                        entity
                    );
                    byte[] identifier = PersistentReferenceBytes(rawIdentifier);
                    if (identifier.Length == 0)
                    {
                        throw new InvalidOperationException(
                            "SOLIDWORKS returned an empty persistent ID for '" +
                            reference.ReferenceId + "'."
                        );
                    }
                    captured.Add(reference.ReferenceId, identifier);
                }
            }
            return captured;
        }

        private static PersistentReferenceResult[] VerifyPersistentReferenceIds(
            ModelDoc2 model,
            PartDoc part,
            ReplayPlan plan,
            IDictionary<string, byte[]> identifiers)
        {
            var results = new List<PersistentReferenceResult>();
            foreach (ReplayStep step in plan.Features)
            {
                foreach (NativeReferenceSpec reference in
                    step.PublishReferences ?? new NativeReferenceSpec[0])
                {
                    byte[] identifier;
                    if (!identifiers.TryGetValue(reference.ReferenceId, out identifier))
                    {
                        throw new InvalidOperationException(
                            "No captured persistent ID exists for '" +
                            reference.ReferenceId + "'."
                        );
                    }
                    int errorCode = 0;
                    object resolved = model.Extension.GetObjectByPersistReference3(
                        identifier,
                        out errorCode
                    );
                    if (resolved == null)
                    {
                        throw new InvalidOperationException(
                            "Persistent reference '" + reference.ReferenceId +
                            "' did not resolve (error " + errorCode + ")."
                        );
                    }
                    object named = part.GetEntityByName(
                        reference.EntityName,
                        ReferenceSelectType(reference.EntityType)
                    );
                    if (named == null)
                    {
                        throw new InvalidOperationException(
                            "Persistent reference '" + reference.ReferenceId +
                            "' resolved, but its semantic entity name '" +
                            reference.EntityName + "' was missing."
                        );
                    }
                    results.Add(
                        new PersistentReferenceResult
                        {
                            ReferenceId = reference.ReferenceId,
                            EntityName = reference.EntityName,
                            EntityType = reference.EntityType,
                            PersistentIdBase64 = Convert.ToBase64String(identifier),
                            Resolved = true,
                            ResolutionErrorCode = errorCode,
                        }
                    );
                }
            }
            return results.ToArray();
        }

        private static int ReferenceSelectType(string entityType)
        {
            if (String.Equals(entityType, "face", StringComparison.Ordinal))
            {
                return (int)swSelectType_e.swSelFACES;
            }
            throw new InvalidOperationException(
                "Unsupported persistent-reference entity type '" + entityType + "'."
            );
        }

        private static byte[] PersistentReferenceBytes(object value)
        {
            byte[] bytes = value as byte[];
            if (bytes != null)
            {
                return bytes;
            }
            Array values = value as Array;
            if (values == null)
            {
                return new byte[0];
            }
            var converted = new byte[values.Length];
            for (int index = 0; index < values.Length; index += 1)
            {
                converted[index] = Convert.ToByte(
                    values.GetValue(index),
                    CultureInfo.InvariantCulture
                );
            }
            return converted;
        }

        private static void VerifyFeaturePropertyBinding(
            ModelDoc2 model,
            NativeParameterBinding binding)
        {
            Feature owner = FindFeatureByName(model, binding.OwnerName);
            if (owner == null)
            {
                throw new InvalidOperationException(
                    "Parameter '" + binding.ParameterId +
                    "' references missing native feature '" +
                    binding.OwnerName + "'."
                );
            }
            object definition = owner.GetDefinition();
            if (definition == null)
            {
                throw new InvalidOperationException(
                    "Native feature '" + binding.OwnerName +
                    "' exposes no editable feature data for parameter '" +
                    binding.ParameterId + "'."
                );
            }

            ResolveFeaturePropertyName(definition, binding);
        }

        private static string ResolveFeaturePropertyName(
            object definition,
            NativeParameterBinding binding)
        {
            string matchedProperty = null;
            Exception lastError = null;
            var observedValues = new List<string>();
            double expected = ToSystemValue(binding.Value, binding.Unit);
            double tolerance = String.Equals(
                binding.Unit,
                "count",
                StringComparison.OrdinalIgnoreCase
            )
                ? 0.0
                : Math.Max(1e-9, Math.Abs(expected) * 1e-6);
            foreach (string propertyName in
                binding.NativeProperties ?? new string[0])
            {
                try
                {
                    object actualObject = definition.GetType().InvokeMember(
                        propertyName,
                        BindingFlags.GetProperty,
                        null,
                        definition,
                        null,
                        CultureInfo.InvariantCulture
                    );
                    double actual = Convert.ToDouble(
                        actualObject,
                        CultureInfo.InvariantCulture
                    );
                    observedValues.Add(
                        propertyName + "=" +
                        actual.ToString("R", CultureInfo.InvariantCulture)
                    );
                    if (Math.Abs(actual - expected) <= tolerance)
                    {
                        matchedProperty = propertyName;
                        break;
                    }
                }
                catch (Exception error)
                {
                    lastError = error;
                }
            }
            if (observedValues.Count == 0)
            {
                string candidates = String.Join(
                    ", ",
                    binding.NativeProperties ?? new string[0]
                );
                throw new InvalidOperationException(
                    "Native feature '" + binding.OwnerName +
                    "' does not expose any expected property for '" +
                    binding.ParameterId + "' (tried " + candidates + ").",
                    lastError
                );
            }
            if (matchedProperty == null)
            {
                throw new InvalidOperationException(
                    "Native properties on '" + binding.OwnerName +
                    "' have values [" + String.Join(", ", observedValues) +
                    "], expected " +
                    expected.ToString("R", CultureInfo.InvariantCulture) +
                    " for parameter '" + binding.ParameterId + "'."
                );
            }
            return matchedProperty;
        }

        private static void CollectFeatureAndChildren(
            Feature feature,
            ISet<string> names)
        {
            if (!String.IsNullOrWhiteSpace(feature.Name))
            {
                names.Add(feature.Name);
            }

            Feature child = feature.GetFirstSubFeature() as Feature;
            while (child != null)
            {
                CollectFeatureAndChildren(child, names);
                child = child.GetNextSubFeature() as Feature;
            }
        }

        private static void VerifyDimension(
            ModelDoc2 model,
            DimensionSpec dimension,
            string ownerName)
        {
            string qualifiedName = dimension.NativeName + "@" + ownerName;
            object dimensionObject = model.Parameter(qualifiedName);
            if (dimensionObject == null)
            {
                throw new InvalidOperationException(
                    "Saved history is missing dimension '" + qualifiedName + "'."
                );
            }
            Dimension nativeDimension = (Dimension)dimensionObject;
            if (!String.Equals(
                nativeDimension.Name,
                dimension.NativeName,
                StringComparison.Ordinal))
            {
                throw new InvalidOperationException(
                    "Dimension '" + qualifiedName + "' was not named deterministically."
                );
            }
            object systemValues = nativeDimension.GetSystemValue3(
                (int)swInConfigurationOpts_e.swThisConfiguration,
                null
            );
            double actual = ObjectItems(systemValues)
                .Select(value => Convert.ToDouble(
                    value,
                    CultureInfo.InvariantCulture
                ))
                .First();
            double expected = ToSystemValue(dimension);
            double tolerance = Math.Max(1e-9, Math.Abs(expected) * 1e-6);
            if (Math.Abs(actual - expected) > tolerance)
            {
                throw new InvalidOperationException(
                    "Dimension '" + qualifiedName + "' has value " +
                    actual.ToString("R", CultureInfo.InvariantCulture) +
                    ", expected " +
                    expected.ToString("R", CultureInfo.InvariantCulture) + "."
                );
            }
        }

        private static IEnumerable<object> ObjectItems(object value)
        {
            if (value == null)
            {
                yield break;
            }
            Array array = value as Array;
            if (array == null)
            {
                yield return value;
                yield break;
            }
            foreach (object item in array)
            {
                yield return item;
            }
        }

        private static double ToMeters(double millimeters)
        {
            return millimeters / MillimetersPerMeter;
        }

        private static double ToSystemValue(DimensionSpec specification)
        {
            return ToSystemValue(specification.ValueMillimeters, specification.Unit);
        }

        private static double ToSystemValue(double value, string unit)
        {
            if (String.Equals(unit, "deg", StringComparison.OrdinalIgnoreCase))
            {
                return DegreesToRadians(value);
            }
            if (String.Equals(unit, "count", StringComparison.OrdinalIgnoreCase))
            {
                return value;
            }
            return ToMeters(value);
        }

        private static double DegreesToRadians(double degrees)
        {
            return degrees * Math.PI / 180.0;
        }

        private static double[] ToSketchPoint(
            FrameSpec frame,
            double[] localPoint,
            MathUtility mathUtility,
            MathTransform modelToSketch)
        {
            double[] worldPoint = WorldPoint(frame, localPoint);
            MathPoint point = (MathPoint)mathUtility.CreatePoint(worldPoint);
            MathPoint sketchPoint = point.IMultiplyTransform(modelToSketch);
            double[] result = (double[])sketchPoint.ArrayData;
            if (String.Equals(
                System.Environment.GetEnvironmentVariable(
                    "P2P_TRACE_COORDINATES"
                ),
                "1",
                StringComparison.Ordinal))
            {
                Trace(
                    "Mapped local [" + String.Join(",", localPoint) +
                    "] through world [" + String.Join(",", worldPoint) +
                    "] to sketch [" + String.Join(",", result) + "]"
                );
            }
            return result;
        }

        private static double[] ToSketchDirection(
            FrameSpec frame,
            double[] localDirection,
            MathUtility mathUtility,
            MathTransform modelToSketch)
        {
            double[] sketchOrigin = ToSketchPoint(
                frame,
                new[] { 0.0, 0.0 },
                mathUtility,
                modelToSketch
            );
            double[] sketchEnd = ToSketchPoint(
                frame,
                localDirection,
                mathUtility,
                modelToSketch
            );
            return Normalize(new[]
            {
                sketchEnd[0] - sketchOrigin[0],
                sketchEnd[1] - sketchOrigin[1],
                sketchEnd[2] - sketchOrigin[2],
            });
        }

        private static double[] WorldPoint(FrameSpec frame, double[] localPoint)
        {
            if (frame == null || frame.OriginMillimeters == null ||
                frame.XAxis == null || frame.Normal == null ||
                localPoint == null || localPoint.Length < 2)
            {
                throw new InvalidOperationException(
                    "A complete frame and local point are required."
                );
            }
            double[] yAxis = Normalize(Cross(frame.Normal, frame.XAxis));
            return new[]
            {
                ToMeters(frame.OriginMillimeters[0] +
                    frame.XAxis[0] * localPoint[0] + yAxis[0] * localPoint[1]),
                ToMeters(frame.OriginMillimeters[1] +
                    frame.XAxis[1] * localPoint[0] + yAxis[1] * localPoint[1]),
                ToMeters(frame.OriginMillimeters[2] +
                    frame.XAxis[2] * localPoint[0] + yAxis[2] * localPoint[1]),
            };
        }

        private static double[] LocalDirection(
            FrameSpec frame,
            double[] localDirection)
        {
            if (localDirection == null || localDirection.Length < 2)
            {
                throw new InvalidOperationException(
                    "A two-dimensional pattern direction is required."
                );
            }
            double[] yAxis = Normalize(Cross(frame.Normal, frame.XAxis));
            return Normalize(Add(
                Scale(frame.XAxis, localDirection[0]),
                Scale(yAxis, localDirection[1])
            ));
        }

        private static double[] Add2D(double[] left, double[] right)
        {
            return new[] { left[0] + right[0], left[1] + right[1] };
        }

        private static double Distance2D(double[] left, double[] right)
        {
            double dx = left[0] - right[0];
            double dy = left[1] - right[1];
            return Math.Sqrt(dx * dx + dy * dy);
        }

        private static double[] Cross(double[] left, double[] right)
        {
            return new[]
            {
                left[1] * right[2] - left[2] * right[1],
                left[2] * right[0] - left[0] * right[2],
                left[0] * right[1] - left[1] * right[0],
            };
        }

        private static double Dot(double[] left, double[] right)
        {
            return left[0] * right[0] + left[1] * right[1] + left[2] * right[2];
        }

        private static double[] Add(double[] left, double[] right)
        {
            return new[]
            {
                left[0] + right[0],
                left[1] + right[1],
                left[2] + right[2],
            };
        }

        private static double[] Scale(double[] value, double factor)
        {
            return new[]
            {
                value[0] * factor,
                value[1] * factor,
                value[2] * factor,
            };
        }

        private static double[] Normalize(double[] value)
        {
            double length = Math.Sqrt(Dot(value, value));
            if (length <= 1e-12)
            {
                throw new InvalidOperationException(
                    "A native reference direction cannot have zero length."
                );
            }
            return Scale(value, 1.0 / length);
        }

        private static double[] Negate(double[] value)
        {
            return new[] { -value[0], -value[1], -value[2] };
        }

        private static void ReleaseComObject(object value)
        {
            if (value != null && Marshal.IsComObject(value))
            {
                try
                {
                    Marshal.FinalReleaseComObject(value);
                }
                catch
                {
                }
            }
        }

        private static void Trace(string message)
        {
            if (String.IsNullOrWhiteSpace(tracePath))
            {
                return;
            }
            File.AppendAllText(
                tracePath,
                DateTime.UtcNow.ToString("O") + " " + message + System.Environment.NewLine
            );
        }

        private static void TraceSketchPoints(Sketch sketch, string label)
        {
            if (!String.Equals(
                System.Environment.GetEnvironmentVariable(
                    "P2P_TRACE_COORDINATES"
                ),
                "1",
                StringComparison.Ordinal) || sketch == null)
            {
                return;
            }

            var coordinates = new List<string>();
            foreach (object pointObject in ObjectItems(sketch.GetSketchPoints2()))
            {
                SketchPoint point = pointObject as SketchPoint;
                if (point != null)
                {
                    coordinates.Add(
                        "[" + point.X + "," + point.Y + "," + point.Z +
                        ";status=" + point.Status + "]"
                    );
                }
            }
            foreach (object segmentObject in ObjectItems(
                sketch.GetSketchSegments()
            ))
            {
                SketchSegment segment = segmentObject as SketchSegment;
                if (segment != null)
                {
                    coordinates.Add(
                        "segment(status=" + segment.Status +
                        ",construction=" + segment.ConstructionGeometry + ")"
                    );
                }
            }
            Trace(label + ": " + String.Join(";", coordinates));
        }

        private static void TraceSketchRelations(Sketch sketch, string label)
        {
            if (!String.Equals(
                System.Environment.GetEnvironmentVariable(
                    "P2P_TRACE_COORDINATES"
                ),
                "1",
                StringComparison.Ordinal) || sketch == null)
            {
                return;
            }

            SketchRelationManager manager = sketch.RelationManager;
            var relations = new List<string>();
            foreach (object relationObject in ObjectItems(
                manager.GetRelations(
                    (int)swSketchRelationFilterType_e.swAll
                )
            ))
            {
                SketchRelation relation = relationObject as SketchRelation;
                if (relation != null)
                {
                    relations.Add(
                        ((swConstraintType_e)relation.GetRelationType()) +
                        "(" + relation.GetEntitiesCount() + ")"
                    );
                }
            }
            Trace(label + ": " + String.Join(";", relations));
        }

        private static void TryDeleteTrace()
        {
            try
            {
                if (!String.IsNullOrWhiteSpace(tracePath) && File.Exists(tracePath))
                {
                    File.Delete(tracePath);
                }
            }
            catch
            {
            }
        }
    }
}
