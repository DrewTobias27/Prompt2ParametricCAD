using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
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

        [DataMember(Name = "publish_references")]
        public PublishedReferences PublishReferences { get; set; }
    }

    [DataContract]
    public sealed class SketchSupport
    {
        [DataMember(Name = "kind")]
        public string Kind { get; set; }

        [DataMember(Name = "name")]
        public string Name { get; set; }

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

        [DataMember(Name = "merge_result")]
        public bool MergeResult { get; set; }

        [DataMember(Name = "driving_dimension")]
        public DimensionSpec DrivingDimension { get; set; }

        [DataMember(Name = "angle_deg")]
        public double AngleDegrees { get; set; }

        [DataMember(Name = "axis_start_mm")]
        public double[] AxisStartMillimeters { get; set; }

        [DataMember(Name = "axis_end_mm")]
        public double[] AxisEndMillimeters { get; set; }

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
    public sealed class PatternSpec
    {
        [DataMember(Name = "kind")]
        public string Kind { get; set; }

        [DataMember(Name = "seed_feature_name")]
        public string SeedFeatureName { get; set; }

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
    public sealed class PublishedReferences
    {
        [DataMember(Name = "top")]
        public string Top { get; set; }

        [DataMember(Name = "bottom")]
        public string Bottom { get; set; }

        [DataMember(Name = "front")]
        public string Front { get; set; }

        [DataMember(Name = "back")]
        public string Back { get; set; }

        [DataMember(Name = "left")]
        public string Left { get; set; }

        [DataMember(Name = "right")]
        public string Right { get; set; }

        [DataMember(Name = "outer_surface")]
        public string OuterSurface { get; set; }
    }

    internal sealed class NativeSketchResult
    {
        public Feature SketchFeature { get; set; }
        public Sketch Sketch { get; set; }
        public SketchSegment RevolveAxis { get; set; }
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

        [DataMember(Name = "verified_dimension_count")]
        public int VerifiedDimensionCount { get; set; }

        [DataMember(Name = "geometry")]
        public NativeGeometryResult Geometry { get; set; }
    }

    [DataContract]
    public sealed class NativeGeometryResult
    {
        [DataMember(Name = "solid_body_count")]
        public int SolidBodyCount { get; set; }

        [DataMember(Name = "volume_mm3")]
        public double VolumeCubicMillimeters { get; set; }

        [DataMember(Name = "bounding_box_mm")]
        public double[] BoundingBoxMillimeters { get; set; }
    }

    public static class NativeReplayRunner
    {
        private const double MillimetersPerMeter = 1000.0;
        private const string ReplayFormat = "prompt2cad.solidworks-replay-plan";
        private const int ReplayVersion = 4;
        private static string tracePath;

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
            if (plan.Format != ReplayFormat || plan.Version != ReplayVersion)
            {
                throw new InvalidOperationException(
                    "Unsupported SOLIDWORKS replay plan format or version."
                );
            }
            if (plan.Features == null || plan.Features.Length == 0)
            {
                throw new InvalidOperationException("The replay plan has no features.");
            }

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
                        if (step.PublishReferences != null)
                        {
                            Trace("Publishing named faces for " + step.FeatureName);
                            PublishNamedFaces(
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
                int verifiedDimensionCount = VerifyReplay(model, part, plan);
                string resolvedOutput = Path.GetFullPath(outputPath);
                string outputDirectory = Path.GetDirectoryName(resolvedOutput);
                if (!String.IsNullOrWhiteSpace(outputDirectory))
                {
                    Directory.CreateDirectory(outputDirectory);
                }

                Trace("Saving native part");
                int saveStatus = model.SaveAs3(
                    resolvedOutput,
                    (int)swSaveAsVersion_e.swSaveAsCurrentVersion,
                    (int)swSaveAsOptions_e.swSaveAsOptions_Silent
                );
                if (saveStatus != 0 || !File.Exists(resolvedOutput))
                {
                    throw new InvalidOperationException(
                        "SOLIDWORKS failed to save '" + resolvedOutput +
                        "' (status " + saveStatus + ")."
                    );
                }

                Trace("Replay complete");
                NativeGeometryResult geometry = MeasureNativeGeometry(part);
                string resultJson = WriteJson(
                    new ReplayResult
                    {
                        Status = "success",
                        OutputPath = resolvedOutput,
                        NativeFeatures = createdNames.ToArray(),
                        FeatureCount = createdNames.Count,
                        VerificationPassed = true,
                        VerifiedDimensionCount = verifiedDimensionCount,
                        Geometry = geometry,
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
            }
        }

        private static ReplayPlan ReadPlan(string path)
        {
            var serializer = new DataContractJsonSerializer(typeof(ReplayPlan));
            using (FileStream stream = File.OpenRead(path))
            {
                return (ReplayPlan)serializer.ReadObject(stream);
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
                if (massProperties.Length < 4)
                {
                    throw new InvalidOperationException(
                        "SOLIDWORKS did not return solid-body mass properties."
                    );
                }
                volumeCubicMeters += massProperties[3];
            }

            double[] boundingBox = ObjectItems(part.GetPartBox(true))
                .Select(value => Convert.ToDouble(
                    value,
                    CultureInfo.InvariantCulture
                ) * MillimetersPerMeter)
                .ToArray();
            if (boundingBox.Length != 6)
            {
                throw new InvalidOperationException(
                    "SOLIDWORKS did not return a six-value part bounding box."
                );
            }
            return new NativeGeometryResult
            {
                SolidBodyCount = bodyObjects.Length,
                VolumeCubicMillimeters =
                    volumeCubicMeters * Math.Pow(MillimetersPerMeter, 3),
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
            SelectSketchSupport(model, part, step.Support);
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

            bool previousAddToDatabase = sketchManager.AddToDB;
            try
            {
                // Native replay must preserve the coordinates in the replay plan.
                // Direct database insertion disables interactive inference and
                // snapping that can otherwise move an offset profile to the
                // sketch origin on a side face.
                sketchManager.AddToDB = true;
                CreateProfileInstances(
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
            };
        }

        private static void SelectSketchSupport(
            ModelDoc2 model,
            PartDoc part,
            SketchSupport support)
        {
            model.ClearSelection2(true);
            if (support.Kind == "datum_plane")
            {
                bool selected = model.Extension.SelectByID2(
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
                if (!selected)
                {
                    throw new InvalidOperationException(
                        "Could not select datum plane '" + support.Name + "'."
                    );
                }
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

        private static void CreateProfileInstances(
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
                foreach (double[] point in positions)
                {
                    double[] sketchPoint = ToSketchPoint(
                        step.Support.Frame,
                        point,
                        mathUtility,
                        modelToSketch
                    );
                    if (sketchManager.CreatePoint(
                        sketchPoint[0], sketchPoint[1], sketchPoint[2]
                    ) == null)
                    {
                        throw new InvalidOperationException(
                            "SOLIDWORKS did not create a Hole Wizard position point."
                        );
                    }
                }
                return;
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
                double[] centerWorld = ToSketchPoint(
                    frame,
                    center,
                    mathUtility,
                    modelToSketch
                );
                double[] cornerWorld = ToSketchPoint(
                    frame,
                    new[] { center[0] + halfWidth, center[1] + halfHeight },
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
                SketchPoint centerPoint = FindSketchPointAt(
                    segments[0].GetSketch(),
                    centerWorld
                );
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
                    "Rectangle before dimensions for " + step.SketchName
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
                TraceSketchPoints(
                    segments[0].GetSketch(),
                    "Rectangle after dimensions for " + step.SketchName
                );
                return;
            }

            if (sketch.Profile == "circle")
            {
                double radius = ToMeters(sketch.DiameterMillimeters / 2.0);
                double[] centerWorld = ToSketchPoint(
                    frame,
                    center,
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
                var points = new List<double[]>();
                for (int index = 0; index < sketch.Sides; index++)
                {
                    double angle = (2.0 * Math.PI * index / sketch.Sides) +
                        (Math.PI / 2.0);
                    points.Add(new[]
                    {
                        center[0] + radius * Math.Cos(angle),
                        center[1] + radius * Math.Sin(angle),
                    });
                }
                CreateClosedPolyline(
                    sketchManager,
                    frame,
                    points,
                    mathUtility,
                    modelToSketch
                );
                return;
            }

            if (sketch.Profile == "polyline")
            {
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
                return;
            }

            if (sketch.Profile == "sketch")
            {
                CreateSegmentPath(
                    sketchManager,
                    frame,
                    sketch,
                    center,
                    mathUtility,
                    modelToSketch
                );
                return;
            }

            throw new InvalidOperationException(
                "Unsupported native sketch profile '" + sketch.Profile + "'."
            );
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

        private static void CreateSegmentPath(
            SketchManager sketchManager,
            FrameSpec frame,
            SketchSpec sketch,
            double[] center,
            MathUtility mathUtility,
            MathTransform modelToSketch)
        {
            if (sketch.StartMillimeters == null || sketch.StartMillimeters.Length < 2)
            {
                throw new InvalidOperationException("A sketch path requires a start point.");
            }
            double[] start = Add2D(center, sketch.StartMillimeters);
            double[] current = start;
            foreach (SketchPathSegment segment in
                sketch.Segments ?? new SketchPathSegment[0])
            {
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

            Feature feature;
            if (step.Feature.Kind == "boss_extrude")
            {
                feature = manager.FeatureExtrusion3(
                    true, false, false,
                    endCondition, 0,
                    depth, 0.01,
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
                    true, false, false,
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
                        true, false, true,
                        endCondition, 0,
                        depth, 0.01,
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
                        true, false, true,
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
            object[] pointObjects = ObjectItems(
                nativeSketch.Sketch.GetSketchPoints2()
            ).ToArray();
            if (pointObjects.Length == 0)
            {
                throw new InvalidOperationException(
                    "The countersink position sketch contains no points."
                );
            }
            foreach (object pointObject in pointObjects)
            {
                SketchPoint point = pointObject as SketchPoint;
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
            string featureName)
        {
            if (specification == null)
            {
                return;
            }
            object dimensionObject = feature.Parameter("D1");
            if (dimensionObject == null)
            {
                throw new InvalidOperationException(
                    "Native feature '" + featureName +
                    "' has no D1 driving dimension."
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
                SelectPatternDirection(model, references.Direction1, 1);
                patternFeature = model.FeatureManager.FeatureCircularPattern5(
                    pattern.Count,
                    DegreesToRadians(pattern.TotalAngleDegrees),
                    false,
                    "NULL",
                    true,
                    true,
                    false,
                    false,
                    false,
                    false,
                    0,
                    0.0,
                    "NULL",
                    false
                );
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
            sketchFeature.Name = step.FeatureName + "_References";
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
            return new PatternReferenceSketch
            {
                SketchFeature = sketchFeature,
                Direction1 = first,
                Direction2 = second,
            };
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
            SelectSketchSupport(model, part, step.Support);
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
            sketchFeature.Name = step.FeatureName + "_MirrorPositions";
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
            IList<Edge> edges = SelectFeatureEdges(
                targetFeature,
                step.Support.Frame,
                step.Support.Selector
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
                    (int)swChamferType_e.swChamferEqualDistance,
                    0.0,
                    0.0,
                    ToMeters(step.Feature.DistanceMillimeters),
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

        private static void PublishNamedFaces(
            PartDoc part,
            Feature feature,
            ReplayStep step)
        {
            FrameSpec frame = step.Support.Frame;
            if (frame == null)
            {
                throw new InvalidOperationException(
                    "Cannot publish native references without a feature frame."
                );
            }
            double[] yAxis = Cross(frame.Normal, frame.XAxis);
            double[] frontDirection = yAxis;
            if ((step.Feature.Kind == "boss_revolve" ||
                 step.Feature.Kind == "cut_revolve") &&
                step.Feature.AxisStartMillimeters != null &&
                step.Feature.AxisEndMillimeters != null)
            {
                double axisX =
                    step.Feature.AxisEndMillimeters[0] -
                    step.Feature.AxisStartMillimeters[0];
                double axisY =
                    step.Feature.AxisEndMillimeters[1] -
                    step.Feature.AxisStartMillimeters[1];
                frontDirection = Normalize(Add(
                    Scale(frame.XAxis, axisX),
                    Scale(yAxis, axisY)
                ));
            }
            var requests = new[]
            {
                new { Name = step.PublishReferences.Top, Direction = frame.Normal, Curved = false },
                new { Name = step.PublishReferences.Bottom, Direction = Negate(frame.Normal), Curved = false },
                new { Name = step.PublishReferences.Right, Direction = frame.XAxis, Curved = false },
                new { Name = step.PublishReferences.Left, Direction = Negate(frame.XAxis), Curved = false },
                new { Name = step.PublishReferences.Front, Direction = frontDirection, Curved = false },
                new { Name = step.PublishReferences.Back, Direction = Negate(frontDirection), Curved = false },
                new { Name = step.PublishReferences.OuterSurface, Direction = frame.Normal, Curved = true },
            };

            foreach (var request in requests)
            {
                if (String.IsNullOrWhiteSpace(request.Name))
                {
                    continue;
                }
                Face2 face = request.Curved
                    ? FindLargestNonPlanarFace(feature)
                    : FindPlanarFace(feature, request.Direction);
                if (face == null)
                {
                    throw new InvalidOperationException(
                        "Could not resolve native face '" + request.Name +
                        "' on '" + feature.Name + "'."
                    );
                }
                if (!part.SetEntityName(face, request.Name))
                {
                    throw new InvalidOperationException(
                        "Could not publish native face name '" + request.Name + "'."
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

        private static int VerifyReplay(
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

            int dimensionCount = 0;
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

                foreach (DimensionSpec dimension in
                    step.Sketch == null
                        ? new DimensionSpec[0]
                        : step.Sketch.DrivingDimensions ?? new DimensionSpec[0])
                {
                    VerifyDimension(model, dimension, step.SketchName);
                    dimensionCount += 1;
                }
                foreach (PlacementControl control in
                    step.Sketch == null
                        ? new PlacementControl[0]
                        : step.Sketch.PlacementControls ?? new PlacementControl[0])
                {
                    foreach (DimensionSpec dimension in new[]
                    {
                        control.XDimension,
                        control.YDimension,
                    })
                    {
                        if (dimension == null)
                        {
                            continue;
                        }
                        VerifyDimension(model, dimension, step.SketchName);
                        dimensionCount += 1;
                    }
                }
                if (step.Feature.DrivingDimension != null)
                {
                    VerifyDimension(
                        model,
                        step.Feature.DrivingDimension,
                        step.Pattern == null
                            ? step.FeatureName
                            : step.Pattern.SeedFeatureName
                    );
                    dimensionCount += 1;
                }

                foreach (string entityName in PublishedEntityNames(
                    step.PublishReferences
                ))
                {
                    if (part.GetEntityByName(
                        entityName,
                        (int)swSelectType_e.swSelFACES
                    ) == null)
                    {
                        throw new InvalidOperationException(
                            "Saved history is missing named face '" +
                            entityName + "'."
                        );
                    }
                }
            }
            return dimensionCount;
        }

        private static IEnumerable<string> PublishedEntityNames(
            PublishedReferences references)
        {
            if (references == null)
            {
                yield break;
            }
            foreach (string name in new[]
            {
                references.Top,
                references.Bottom,
                references.Front,
                references.Back,
                references.Left,
                references.Right,
                references.OuterSurface,
            })
            {
                if (!String.IsNullOrWhiteSpace(name))
                {
                    yield return name;
                }
            }
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
            if (String.Equals(specification.Unit, "deg", StringComparison.OrdinalIgnoreCase))
            {
                return DegreesToRadians(specification.ValueMillimeters);
            }
            return ToMeters(specification.ValueMillimeters);
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
                        "[" + point.X + "," + point.Y + "," + point.Z + "]"
                    );
                }
            }
            Trace(label + ": " + String.Join(";", coordinates));
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
