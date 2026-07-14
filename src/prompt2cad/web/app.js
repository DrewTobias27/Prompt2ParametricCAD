async function generateCAD() {
    const button = document.getElementById("generateButton");
    const downloadLink = document.getElementById("downloadLink");
    const output = document.getElementById("output");
    const prompt = document.getElementById("prompt").value;
    const resultActions = document.getElementById("resultActions");
    const resultSummary = document.getElementById("resultSummary");
    const status = document.getElementById("status");

    status.textContent = "Generating CAD model...";
    status.className = "status-message";
    output.textContent = "";
    resultActions.classList.add("hidden");
    resultSummary.classList.add("hidden");
    downloadLink.classList.add("hidden");

    button.disabled = true;
    button.textContent = "Generating...";

    try {
        const response = await fetch("/generate-intent", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ prompt: prompt }),
        });

        const data = await response.json();
        showResult(data);
    } catch (error) {
        showResult({
            status: "error",
            message: String(error),
            model_data: null,
        });
    } finally {
        button.disabled = false;
        button.textContent = "Generate CAD";
    }
}

const generateButton = document.getElementById("generateButton");
generateButton.addEventListener("click", generateCAD);


let lastResultJson = "";
let demoExamples = [];


async function loadDemoExamples() {
    const select = document.getElementById("demoExampleSelect");

    try {
        const response = await fetch("/demo-examples");
        const data = await response.json();
        demoExamples = data.examples || [];
        select.innerHTML = "";

        for (const example of demoExamples) {
            const option = document.createElement("option");
            option.value = example.id;
            option.textContent = example.title;
            select.appendChild(option);
        }

        if (demoExamples.length === 0) {
            const option = document.createElement("option");
            option.value = "";
            option.textContent = "No demo examples found";
            select.appendChild(option);
        }
    } catch (error) {
        select.innerHTML = "";
        const option = document.createElement("option");
        option.value = "";
        option.textContent = "Could not load demo examples";
        select.appendChild(option);
    }
}


function selectedDemoExample() {
    const selectedId = document.getElementById("demoExampleSelect").value;
    return demoExamples.find((example) => example.id === selectedId);
}


function useSelectedDemoPrompt() {
    const example = selectedDemoExample();
    if (!example) {
        return;
    }

    document.getElementById("prompt").value = example.prompt;
}


function setBuilderMode(mode) {
    const promptBuilder = document.getElementById("promptBuilder");
    const manualBuilder = document.getElementById("manualBuilder");
    const promptModeButton = document.getElementById("promptModeButton");
    const manualModeButton = document.getElementById("manualModeButton");

    const isPromptMode = mode === "prompt";

    promptBuilder.classList.toggle("hidden", !isPromptMode);
    manualBuilder.classList.toggle("hidden", isPromptMode);
    promptModeButton.classList.toggle("active", isPromptMode);
    manualModeButton.classList.toggle("active", !isPromptMode);
    updateDesignReviewWarnings();
    updateManualPreview();
}


function updateManualBuilderFields() {
    const baseProfile = document.getElementById("baseProfile").value;
    const useReasonableDefaults = document.getElementById("useReasonableDefaults").checked;
    const rectangleFields = document.getElementById("rectangleFields");
    const circleFields = document.getElementById("circleFields");
    const thicknessFields = document.getElementById("thicknessFields");
    const polygonFields = document.getElementById("polygonFields");
    const polylineFields = document.getElementById("polylineFields");

    rectangleFields.classList.toggle("hidden", useReasonableDefaults || baseProfile !== "rectangle");
    circleFields.classList.toggle("hidden", useReasonableDefaults || baseProfile !== "circle");
    polygonFields.classList.toggle("hidden", useReasonableDefaults || baseProfile !== "polygon");
    thicknessFields.classList.toggle("hidden", useReasonableDefaults);
    polylineFields.classList.toggle("hidden", baseProfile !== "polyline");
    updateDesignReviewWarnings();
    updateManualPreview();
}


function showResult(data) {
    const downloadLink = document.getElementById("downloadLink");
    const output = document.getElementById("output");
    const resultActions = document.getElementById("resultActions");
    const resultSummary = document.getElementById("resultSummary");
    const status = document.getElementById("status");

    lastResultJson = JSON.stringify(data, null, 2);
    renderResultSummary(data);

    if (data.status === "success") {
        status.textContent = "Success";
        status.className = "status-message success";
        downloadLink.href = data.download_url;
        downloadLink.classList.remove("hidden");
        resultActions.classList.remove("hidden");
    } else {
        status.textContent = "Error: " + data.message;
        status.className = "status-message error";
        resultActions.classList.remove("hidden");
        downloadLink.removeAttribute("href");
        downloadLink.classList.add("hidden");
    }

    output.textContent = lastResultJson;
}


function formatSeconds(value) {
    if (value === undefined || value === null) {
        return null;
    }

    return `${Number(value).toFixed(2)}s`;
}


function readableGenerationMode(mode) {
    if (mode === "design_intent") {
        return "AI design-intent pipeline";
    }
    if (mode === "saved_demo") {
        return "Saved demo fallback";
    }
    return "Direct CAD JSON pipeline";
}


function renderResultSummary(data) {
    const resultSummary = document.getElementById("resultSummary");
    const performance = data.performance || {};
    const qualityReport = data.quality_report || {};
    const issues = qualityReport.issues || [];
    const summaryItems = [];

    summaryItems.push([
        "Mode",
        readableGenerationMode(data.generation_mode),
    ]);

    const totalSeconds = formatSeconds(performance.total_seconds);
    if (totalSeconds) {
        summaryItems.push(["Total time", totalSeconds]);
    }

    const apiSeconds = formatSeconds(performance.api_seconds);
    if (apiSeconds) {
        summaryItems.push(["AI time", apiSeconds]);
    }

    const buildSeconds = formatSeconds(performance.build_seconds);
    if (buildSeconds) {
        summaryItems.push(["CAD build", buildSeconds]);
    }

    if (performance.cache_hit) {
        summaryItems.push(["Cache", "served from previous successful result"]);
    }

    if (qualityReport.status) {
        summaryItems.push(["Quality", qualityReport.status]);
    }

    resultSummary.innerHTML = "";
    resultSummary.className = `result-summary ${data.status === "success" ? "success" : "error"}`;

    const summaryGrid = document.createElement("div");
    summaryGrid.className = "result-summary-grid";
    for (const [label, value] of summaryItems) {
        const item = document.createElement("div");
        item.className = "result-summary-item";
        item.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
        summaryGrid.appendChild(item);
    }
    resultSummary.appendChild(summaryGrid);

    if (issues.length > 0) {
        const issueList = document.createElement("ul");
        issueList.className = "result-issue-list";
        for (const issue of issues.slice(0, 4)) {
            const item = document.createElement("li");
            item.textContent = issue.message || issue.code || JSON.stringify(issue);
            issueList.appendChild(item);
        }
        resultSummary.appendChild(issueList);
    } else if (data.status === "success") {
        const cleanMessage = document.createElement("p");
        cleanMessage.className = "result-clean-message";
        cleanMessage.textContent = "Generated one valid connected model and exported a STEP file.";
        resultSummary.appendChild(cleanMessage);
    }

    if (data.status !== "success") {
        const recovery = document.createElement("p");
        recovery.className = "result-recovery-message";
        recovery.textContent = "Try one of the known-good demo prompts or simplify the request, then generate again.";
        resultSummary.appendChild(recovery);
    }

    resultSummary.classList.remove("hidden");
}


async function copyResultJson() {
    const copyJsonButton = document.getElementById("copyJsonButton");

    if (!lastResultJson) {
        return;
    }

    await navigator.clipboard.writeText(lastResultJson);
    copyJsonButton.textContent = "Copied";
    setTimeout(() => {
        copyJsonButton.textContent = "Copy JSON";
    }, 1200);
}


function buildManualModelData() {
    const baseProfile = document.getElementById("baseProfile").value;
    const width = Number(document.getElementById("baseWidth").value);
    const height = Number(document.getElementById("baseHeight").value);
    const diameter = Number(document.getElementById("baseDiameter").value);
    const distance = Number(document.getElementById("baseDistance").value);
    const polygonDiameter = Number(document.getElementById("polygonDiameter").value);
    const polygonSides = Number(document.getElementById("polygonSides").value);

    const baseOperation = {
        type: "extrude",
        id: "base",
        plane: "XY",
        profile: baseProfile,
        distance: distance,
    };

    if (baseProfile === "rectangle") {
        baseOperation.width = width;
        baseOperation.height = height;
    } else if (baseProfile === "circle") {
        baseOperation.diameter = diameter;
    } else if (baseProfile === "polygon") {
        baseOperation.sides = polygonSides;
        baseOperation.diameter = polygonDiameter;
    } else if (baseProfile === "polyline") {
        throw new Error("Polyline manual builder needs the API-assisted point generator next.");
    }

    return {
        operations: [baseOperation],
    };
}


let featureCount = 0;


function updateFeatureCardFields(featureCard) {
    const featureProfile = featureCard.querySelector(".feature-profile").value;
    const featureOperation = featureCard.querySelector(".feature-operation").value;
    const useReasonableDimensions = featureCard.querySelector(".feature-reasonable").checked;
    const depthMode = featureCard.querySelector(".feature-depth-mode").value;
    const rectangleFields = featureCard.querySelector(".feature-rectangle-fields");
    const circleFields = featureCard.querySelector(".feature-circle-fields");
    const polygonFields = featureCard.querySelector(".feature-polygon-fields");
    const polylineFields = featureCard.querySelector(".feature-polyline-fields");
    const positionFields = featureCard.querySelector(".feature-position-fields");
    const mirrorFields = featureCard.querySelector(".feature-mirror-fields");
    const circularPatternFields = featureCard.querySelector(".feature-circular-pattern-fields");
    const cutDepthModeFields = featureCard.querySelector(".feature-cut-depth-mode-fields");
    const amountFields = featureCard.querySelector(".feature-amount-fields");
    const amountLabel = featureCard.querySelector(".feature-amount-label");
    const pattern = featureCard.querySelector(".feature-pattern").value;
    const usesApiAssistance = useReasonableDimensions;

    rectangleFields.classList.toggle(
        "hidden",
        usesApiAssistance || featureProfile !== "rectangle",
    );
    circleFields.classList.toggle(
        "hidden",
        usesApiAssistance || featureProfile !== "circle",
    );
    polygonFields.classList.toggle(
        "hidden",
        usesApiAssistance || featureProfile !== "polygon",
    );
    polylineFields.classList.toggle("hidden", featureProfile !== "polyline");
    positionFields.classList.toggle("hidden", usesApiAssistance);
    mirrorFields.classList.toggle("hidden", pattern === "circular");
    circularPatternFields.classList.toggle(
        "hidden",
        pattern !== "circular",
    );
    cutDepthModeFields.classList.toggle(
        "hidden",
        usesApiAssistance || featureOperation !== "cut",
    );
    amountFields.classList.toggle(
        "hidden",
        usesApiAssistance || (featureOperation === "cut" && depthMode === "through"),
    );

    if (featureOperation === "cut") {
        amountLabel.textContent = "Cut depth";
    } else {
        amountLabel.textContent = "Extrusion distance";
    }
}


function baseTargetOptions() {
    return [
        ["base.top", "Base top"],
        ["base.bottom", "Base bottom"],
        ["base.front", "Base front"],
        ["base.back", "Base back"],
        ["base.left", "Base left"],
        ["base.right", "Base right"],
    ];
}


function featureFaceOptions(featureCard, featureNumber) {
    const operation = featureCard.querySelector(".feature-operation").value;
    const profile = featureCard.querySelector(".feature-profile").value;

    if (operation !== "add_extrude") {
        return [];
    }

    const faces = [
        ["top", "top"],
        ["bottom", "bottom"],
    ];
    if (profile === "rectangle") {
        faces.push(
            ["front", "front"],
            ["back", "back"],
            ["left", "left"],
            ["right", "right"],
        );
    }

    return faces.map(([faceValue, faceLabel]) => [
        `feature_${featureNumber}.${faceValue}`,
        `Feature ${featureNumber} ${faceLabel}`,
    ]);
}


function setTargetOptions(selectElement, options) {
    const previousValue = selectElement.value;
    selectElement.innerHTML = "";

    for (const [value, label] of options) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = label;
        selectElement.appendChild(option);
    }

    if (options.some(([value]) => value === previousValue)) {
        selectElement.value = previousValue;
    }
}


function renumberFeatureCards() {
    const featureCards = Array.from(document.querySelectorAll(".feature-card"));

    for (const [index, featureCard] of featureCards.entries()) {
        const featureNumber = index + 1;
        featureCard.dataset.featureNumber = String(featureNumber);
        featureCard.querySelector(".feature-title").textContent = `Feature ${featureNumber}`;

        const targetSelect = featureCard.querySelector(".feature-target");
        const targetOptions = baseTargetOptions();

        for (let priorIndex = 0; priorIndex < index; priorIndex += 1) {
            targetOptions.push(
                ...featureFaceOptions(featureCards[priorIndex], priorIndex + 1),
            );
        }

        setTargetOptions(targetSelect, targetOptions);
    }

    featureCount = featureCards.length;
    updateDesignReviewWarnings();
    updateManualPreview();
}


function addFeatureCard() {
    featureCount += 1;

    const featureList = document.getElementById("featureList");
    const featureCard = document.createElement("div");
    featureCard.className = "feature-card";
    featureCard.innerHTML = `
        <div class="feature-card-header">
            <h4 class="feature-title">Feature ${featureCount}</h4>
            <button class="remove-feature-button" type="button">Remove</button>
        </div>

        <div class="field-group">
            <label>
                Operation
                <select class="feature-operation">
                    <option value="add_extrude">Extrusion</option>
                    <option value="cut">Cut</option>
                </select>
            </label>

            <label>
                Target face
                <select class="feature-target">
                    <option value="base.top">Base top</option>
                </select>
            </label>

            <label>
                Shape
                <select class="feature-profile">
                    <option value="rectangle">Rectangle</option>
                    <option value="circle">Circle</option>
                    <option value="polygon">Polygon</option>
                    <option value="polyline">Polyline</option>
                </select>
            </label>
        </div>

        <div class="field-group feature-pattern-fields">
            <label>
                Pattern
                <select class="feature-pattern">
                    <option value="single">Single</option>
                    <option value="circular">Circular pattern</option>
                </select>
            </label>
        </div>

        <div class="feature-mirror-fields">
            <label class="checkbox-row">
                <input class="feature-mirror-x" type="checkbox">
                Mirror across X axis
            </label>

            <label class="checkbox-row">
                <input class="feature-mirror-y" type="checkbox">
                Mirror across Y axis
            </label>

            <label class="checkbox-row">
                <input class="feature-reasonable" type="checkbox" checked>
                Use reasonable dimensions
            </label>
        </div>

        <div class="field-group feature-rectangle-fields">
            <label>
                Width
                <input class="feature-width" type="number" value="20">
            </label>

            <label>
                Height
                <input class="feature-height" type="number" value="12">
            </label>
        </div>

        <div class="field-group feature-circle-fields">
            <label>
                Diameter
                <input class="feature-diameter" type="number" value="10">
            </label>
        </div>

        <div class="field-group feature-polygon-fields">
            <label>
                Diameter
                <input class="feature-polygon-diameter" type="number" value="16">
            </label>

            <label>
                Number of sides
                <input class="feature-polygon-sides" type="number" value="6" min="3">
            </label>
        </div>

        <div class="field-group feature-polyline-fields">
            <label>
                Polyline description
                <textarea
                    class="feature-polyline-description"
                    rows="3"
                    placeholder="Example: a small L-shaped cut or a stepped rectangular boss"
                ></textarea>
            </label>
        </div>

        <div class="field-group feature-position-fields">
            <label>
                Position X
                <input class="feature-position-x" type="number" value="0">
            </label>

            <label>
                Position Y
                <input class="feature-position-y" type="number" value="0">
            </label>
        </div>

        <div class="field-group feature-circular-pattern-fields">
            <label>
                Number of copies
                <input class="feature-circular-count" type="number" value="4" min="2">
            </label>
        </div>

        <div class="field-group feature-cut-depth-mode-fields">
            <label>
                Cut depth type
                <select class="feature-depth-mode">
                    <option value="blind">Blind depth</option>
                    <option value="through">Through cut</option>
                </select>
            </label>
        </div>

        <div class="field-group feature-amount-fields">
            <label>
                <span class="feature-amount-label">Extrusion distance</span>
                <input class="feature-amount" type="number" value="6">
            </label>
        </div>
    `;

    const removeButton = featureCard.querySelector(".remove-feature-button");
    removeButton.addEventListener("click", () => {
        featureCard.remove();
        renumberFeatureCards();
        updateDesignReviewWarnings();
        updateManualPreview();
    });

    const featureOperationSelect = featureCard.querySelector(".feature-operation");
    featureOperationSelect.addEventListener("change", () => {
        updateFeatureCardFields(featureCard);
        renumberFeatureCards();
    });

    const featureProfileSelect = featureCard.querySelector(".feature-profile");
    featureProfileSelect.addEventListener("change", () => {
        updateFeatureCardFields(featureCard);
        renumberFeatureCards();
    });

    const featurePatternSelect = featureCard.querySelector(".feature-pattern");
    featurePatternSelect.addEventListener("change", () => {
        updateFeatureCardFields(featureCard);
        updateDesignReviewWarnings();
        updateManualPreview();
    });

    const featureReasonableCheckbox = featureCard.querySelector(".feature-reasonable");
    featureReasonableCheckbox.addEventListener("change", () => {
        updateFeatureCardFields(featureCard);
        updateDesignReviewWarnings();
        updateManualPreview();
    });

    const featureDepthModeSelect = featureCard.querySelector(".feature-depth-mode");
    featureDepthModeSelect.addEventListener("change", () => {
        updateFeatureCardFields(featureCard);
        updateDesignReviewWarnings();
        updateManualPreview();
    });

    featureCard.addEventListener("input", updateDesignReviewWarnings);
    featureCard.addEventListener("change", updateDesignReviewWarnings);
    featureCard.addEventListener("input", updateManualPreview);
    featureCard.addEventListener("change", updateManualPreview);

    featureList.appendChild(featureCard);
    renumberFeatureCards();
    updateFeatureCardFields(featureCard);
    updateDesignReviewWarnings();
    updateManualPreview();
}


const REVIEW_EDGE_MARGIN = 3;
const REVIEW_FEATURE_FRACTION_LIMIT = 0.75;
const REVIEW_MIN_FEATURE_SPACING = 2;


function reviewWarning(severity, title, message) {
    return {
        severity: severity,
        title: title,
        message: message,
    };
}


function getManualBaseReviewGeometry() {
    const baseProfile = document.getElementById("baseProfile").value;
    const useReasonableDefaults = document.getElementById("useReasonableDefaults").checked;
    const thickness = Number(document.getElementById("baseDistance").value);

    if (useReasonableDefaults || baseProfile === "polyline") {
        return null;
    }

    if (baseProfile === "rectangle") {
        const width = Number(document.getElementById("baseWidth").value);
        const height = Number(document.getElementById("baseHeight").value);
        return {
            profile: "rectangle",
            width: width,
            height: height,
            thickness: thickness,
            bounds: [-width / 2, -height / 2, width / 2, height / 2],
        };
    }

    if (baseProfile === "circle") {
        const diameter = Number(document.getElementById("baseDiameter").value);
        return {
            profile: "circle",
            diameter: diameter,
            radius: diameter / 2,
            thickness: thickness,
            bounds: [-diameter / 2, -diameter / 2, diameter / 2, diameter / 2],
        };
    }

    if (baseProfile === "polygon") {
        const diameter = Number(document.getElementById("polygonDiameter").value);
        const sides = Number(document.getElementById("polygonSides").value);
        return {
            profile: "polygon",
            diameter: diameter,
            radius: diameter / 2,
            sides: sides,
            thickness: thickness,
            bounds: [-diameter / 2, -diameter / 2, diameter / 2, diameter / 2],
        };
    }

    return null;
}


function featureLocalBounds(featureCard) {
    const profile = featureCard.querySelector(".feature-profile").value;
    const useReasonableDimensions = featureCard.querySelector(".feature-reasonable").checked;

    if (useReasonableDimensions || profile === "polyline") {
        return null;
    }

    if (profile === "rectangle") {
        const width = Number(featureCard.querySelector(".feature-width").value);
        const height = Number(featureCard.querySelector(".feature-height").value);
        return {
            width: width,
            height: height,
            bounds: [-width / 2, -height / 2, width / 2, height / 2],
        };
    }

    if (profile === "circle") {
        const diameter = Number(featureCard.querySelector(".feature-diameter").value);
        return {
            width: diameter,
            height: diameter,
            radius: diameter / 2,
            bounds: [-diameter / 2, -diameter / 2, diameter / 2, diameter / 2],
        };
    }

    if (profile === "polygon") {
        const diameter = Number(featureCard.querySelector(".feature-polygon-diameter").value);
        const sides = Number(featureCard.querySelector(".feature-polygon-sides").value);
        return {
            width: diameter,
            height: diameter,
            radius: diameter / 2,
            sides: sides,
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


function boundsWidth(bounds) {
    return bounds[2] - bounds[0];
}


function boundsHeight(bounds) {
    return bounds[3] - bounds[1];
}


function boundsCenter(bounds) {
    return [
        (bounds[0] + bounds[2]) / 2,
        (bounds[1] + bounds[3]) / 2,
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
        return {
            ...baseGeometry,
            viewName: "top",
        };
    }

    const topWidth = boundsWidth(baseGeometry.bounds);
    const topDepth = boundsHeight(baseGeometry.bounds);

    if (viewName === "front") {
        return {
            profile: "projection",
            viewName: "front",
            width: topWidth,
            height: baseGeometry.thickness,
            bounds: [-topWidth / 2, -baseGeometry.thickness / 2, topWidth / 2, baseGeometry.thickness / 2],
        };
    }

    if (viewName === "right") {
        return {
            profile: "projection",
            viewName: "right",
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
    const parts = target.split(".");
    if (parts.length !== 2) {
        return null;
    }

    return {
        id: parts[0],
        face: parts[1],
    };
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
        faceName: faceName,
        volume: volume,
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
        id: id,
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
    featureCard,
    localGeometry,
    faceInfo,
    baseGeometry,
    position,
    bounds,
}) {
    return {
        featureNumber: featureNumber,
        operation: operation,
        target: target,
        profile: profile,
        card: featureCard,
        position: facePositionFromLocal(faceInfo, position),
        bounds: bounds,
        width: localGeometry.width,
        height: localGeometry.height,
        radius: localGeometry.radius || 0,
        sides: localGeometry.sides || 0,
        baseGeometry: faceReviewGeometry(faceInfo, baseGeometry),
        viewName: faceInfo.viewName,
        isPrimary: true,
    };
}


function projectionRecordFromVolume({
    operation,
    target,
    featureNumber,
    featureCard,
    volume,
    viewName,
    baseGeometry,
}) {
    const bounds = projectionBoundsForVolume(volume, viewName);
    if (bounds === null || !validBounds(bounds)) {
        return null;
    }

    return {
        featureNumber: featureNumber,
        operation: operation,
        target: target,
        profile: "rectangle",
        card: featureCard,
        position: boundsCenter(bounds),
        bounds: bounds,
        width: boundsWidth(bounds),
        height: boundsHeight(bounds),
        radius: 0,
        sides: 0,
        baseGeometry: baseViewGeometry(baseGeometry, viewName),
        viewName: viewName,
        isPrimary: false,
    };
}


function addProjectionRecords(records, recordOptions, volume, primaryViewName) {
    for (const viewName of ["top", "front", "right"]) {
        if (viewName === primaryViewName) {
            continue;
        }

        const record = projectionRecordFromVolume({
            ...recordOptions,
            volume: volume,
            viewName: viewName,
        });

        if (record !== null) {
            records.push(record);
        }
    }
}


function collectExactFeaturePreviewData(baseGeometry) {
    const featureCards = Array.from(document.querySelectorAll(".feature-card"));
    const featureData = [];
    const volumeById = new Map();
    volumeById.set("base", basePreviewVolume(baseGeometry));

    for (const featureCard of featureCards) {
        const operation = featureCard.querySelector(".feature-operation").value;
        const target = featureCard.querySelector(".feature-target").value;
        const profile = featureCard.querySelector(".feature-profile").value;
        const featureNumber = featureCard.dataset.featureNumber;
        const localGeometry = featureLocalBounds(featureCard);
        const faceInfo = faceInfoForTarget(target, volumeById);

        if (localGeometry === null || faceInfo === null) {
            continue;
        }

        const depthMode = featureCard.querySelector(".feature-depth-mode").value;
        const amount = Number(featureCard.querySelector(".feature-amount").value);
        const seedPosition = [
            Number(featureCard.querySelector(".feature-position-x").value),
            Number(featureCard.querySelector(".feature-position-y").value),
        ];
        const positions = transformFeaturePositions(featureCard, [seedPosition]);

        for (const position of positions) {
            const bounds = faceBoundsFromLocal(faceInfo, localGeometry.bounds, position);
            featureData.push({
                ...previewRecordFromFace({
                    operation: operation,
                    target: target,
                    profile: profile,
                    featureNumber: featureNumber,
                    featureCard: featureCard,
                    localGeometry: localGeometry,
                    faceInfo: faceInfo,
                    baseGeometry: baseGeometry,
                    position: position,
                    bounds: bounds,
                }),
            });

            const recordOptions = {
                operation: operation,
                target: target,
                featureNumber: featureNumber,
                featureCard: featureCard,
                baseGeometry: baseGeometry,
            };

            if (operation === "add_extrude") {
                const featureId = `feature_${featureNumber}`;
                const extrudeVolume = extrudeVolumeFromFace(faceInfo, bounds, amount, featureId);
                if (!volumeById.has(featureId)) {
                    volumeById.set(featureId, extrudeVolume);
                }
                addProjectionRecords(featureData, recordOptions, extrudeVolume, faceInfo.viewName);
            } else if (operation === "cut") {
                const cutVolume = depthMode === "through"
                    ? throughCutVolumeFromFace(faceInfo, bounds, volumeById)
                    : cutVolumeFromFace(faceInfo, bounds, amount);
                addProjectionRecords(featureData, recordOptions, cutVolume, faceInfo.viewName);
            }
        }
    }

    return featureData;
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


function depthLimitForTarget(target, baseGeometry) {
    if (target === "base.top" || target === "base.bottom") {
        return baseGeometry.thickness;
    }

    if (target === "base.front" || target === "base.back") {
        return boundsHeight(baseGeometry.bounds);
    }

    if (target === "base.right" || target === "base.left") {
        return boundsWidth(baseGeometry.bounds);
    }

    return baseGeometry.thickness;
}


function checkCutDepthWarnings() {
    const warnings = [];
    const baseGeometry = getManualBaseReviewGeometry();
    if (baseGeometry === null) {
        return warnings;
    }

    for (const featureCard of document.querySelectorAll(".feature-card")) {
        const operation = featureCard.querySelector(".feature-operation").value;
        const target = featureCard.querySelector(".feature-target").value;
        const useReasonableDimensions = featureCard.querySelector(".feature-reasonable").checked;
        const depthMode = featureCard.querySelector(".feature-depth-mode").value;
        const amount = Number(featureCard.querySelector(".feature-amount").value);
        const featureNumber = featureCard.dataset.featureNumber;
        const depthLimit = depthLimitForTarget(target, baseGeometry);

        if (operation !== "cut" || useReasonableDimensions || depthMode === "through") {
            continue;
        }

        if (amount > depthLimit) {
            warnings.push(
                reviewWarning(
                    "warning",
                    `Feature ${featureNumber} cut is deeper than its target`,
                    "This blind cut is deeper than the material available normal to its target face. Use a through cut if that is intentional.",
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
                            `Circular cuts overlap`,
                            `Features ${first.featureNumber} and ${second.featureNumber} overlap in the same drawing view. Move them apart or reduce their diameters.`,
                        ),
                    );
                } else if (clearDistance < REVIEW_MIN_FEATURE_SPACING) {
                    warnings.push(
                        reviewWarning(
                            "warning",
                            `Circular cuts are very close`,
                            `Features ${first.featureNumber} and ${second.featureNumber} leave only ${clearDistance.toFixed(1)} mm between holes in the same drawing view.`,
                        ),
                    );
                }
            }
        }
    }

    return warnings;
}


function checkPatternSymmetryWarnings(featureData) {
    const warnings = [];
    const groupedByCard = new Map();

    for (const feature of featureData) {
        if (!groupedByCard.has(feature.card)) {
            groupedByCard.set(feature.card, []);
        }
        groupedByCard.get(feature.card).push(feature);
    }

    for (const [featureCard, features] of groupedByCard.entries()) {
        const pattern = featureCard.querySelector(".feature-pattern").value;
        const mirrorX = featureCard.querySelector(".feature-mirror-x").checked;
        const mirrorY = featureCard.querySelector(".feature-mirror-y").checked;
        const featureNumber = featureCard.dataset.featureNumber;

        if (pattern === "circular") {
            const requestedCount = Number(featureCard.querySelector(".feature-circular-count").value);
            if (requestedCount < 2) {
                warnings.push(
                    reviewWarning(
                        "warning",
                        `Feature ${featureNumber} circular pattern needs more copies`,
                        "Use at least 2 copies for a circular pattern.",
                    ),
                );
            } else if (features.length < requestedCount) {
                warnings.push(
                    reviewWarning(
                        "warning",
                        `Feature ${featureNumber} circular pattern collapses`,
                        "The seed position is probably at the origin, so rotated copies land on top of each other. Move the feature away from [0, 0].",
                    ),
                );
            }
        }

        if (pattern === "circular" && features.length > 1) {
            const radii = features.map((feature) => distanceBetweenPoints([0, 0], feature.position));
            const averageRadius = radii.reduce((total, value) => total + value, 0) / radii.length;
            const radiusMismatch = radii.some((radius) => Math.abs(radius - averageRadius) > 0.001);
            if (radiusMismatch) {
                warnings.push(
                    reviewWarning(
                        "warning",
                        `Feature ${featureNumber} circular pattern is inconsistent`,
                        "The copied positions are not all on the same radius. Check the pattern origin and seed position.",
                    ),
                );
            }
        }

        if ((mirrorX || mirrorY) && features.length > 1) {
            const positionKeys = new Set(
                features.map((feature) => feature.position.map((value) => value.toFixed(3)).join(",")),
            );
            for (const feature of features) {
                const [x, y] = feature.position;
                if (mirrorX && !positionKeys.has([x, -y].map((value) => value.toFixed(3)).join(","))) {
                    warnings.push(
                        reviewWarning(
                            "warning",
                            `Feature ${featureNumber} mirror pattern looks incomplete`,
                            "A mirrored copy across the X axis is missing or collapsed onto another position.",
                        ),
                    );
                    break;
                }
                if (mirrorY && !positionKeys.has([-x, y].map((value) => value.toFixed(3)).join(","))) {
                    warnings.push(
                        reviewWarning(
                            "warning",
                            `Feature ${featureNumber} mirror pattern looks incomplete`,
                            "A mirrored copy across the Y axis is missing or collapsed onto another position.",
                        ),
                    );
                    break;
                }
            }
        } else if ((mirrorX || mirrorY) && features.length === 1) {
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


function checkSharpInternalCornerWarnings() {
    const warnings = [];

    for (const featureCard of document.querySelectorAll(".feature-card")) {
        const operation = featureCard.querySelector(".feature-operation").value;
        const profile = featureCard.querySelector(".feature-profile").value;
        const useReasonableDimensions = featureCard.querySelector(".feature-reasonable").checked;
        const featureNumber = featureCard.dataset.featureNumber;

        if (operation === "cut" && profile === "rectangle" && !useReasonableDimensions) {
            warnings.push(
                reviewWarning(
                    "info",
                    `Feature ${featureNumber} has sharp internal corners`,
                    "Rectangular CNC pockets and slots usually need internal corner radii or relief cuts.",
                ),
            );
        }
    }

    return warnings;
}


function designReviewWarnings() {
    const warnings = [];
    const baseGeometry = getManualBaseReviewGeometry();
    const featureCards = Array.from(document.querySelectorAll(".feature-card"));

    if (baseGeometry === null) {
        return [
            reviewWarning(
                "info",
                "Exact design review is waiting for dimensions",
                "Turn off reasonable dimensions and use rectangle, circle, or polygon base dimensions to enable live boundary checks.",
            ),
        ];
    }

    if (featureCards.length === 0) {
        return [
            reviewWarning(
                "info",
                "No feature warnings yet",
                "Add a cut or extrusion to see live spacing, boundary, and manufacturability warnings.",
            ),
        ];
    }

    const exactFeatureData = collectExactFeaturePreviewData(baseGeometry).filter(
        (feature) => feature.isPrimary,
    );
    const exactFeatureCount = exactFeatureData.length;

    warnings.push(...checkFeatureBoundaryWarnings(exactFeatureData));
    warnings.push(...checkFeatureSizeWarnings(exactFeatureData));
    warnings.push(...checkCutDepthWarnings());
    warnings.push(...checkHoleSpacingWarnings(exactFeatureData));
    warnings.push(...checkPatternSymmetryWarnings(exactFeatureData));
    warnings.push(...checkSharpInternalCornerWarnings());

    if (exactFeatureCount < featureCards.length) {
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

    return warnings;
}


function updateDesignReviewWarnings() {
    const panel = document.getElementById("designReviewPanel");
    const warningsContainer = document.getElementById("designReviewWarnings");
    if (!panel || !warningsContainer) {
        return;
    }

    const isManualMode = !document.getElementById("manualBuilder").classList.contains("hidden");
    panel.classList.toggle("hidden", !isManualMode);

    if (!isManualMode) {
        return;
    }

    const warnings = designReviewWarnings();
    warningsContainer.innerHTML = "";

    for (const warning of warnings) {
        const warningElement = document.createElement("div");
        warningElement.className = `design-review-item ${warning.severity}`;

        const titleElement = document.createElement("strong");
        titleElement.textContent = warning.title;

        const messageElement = document.createElement("p");
        messageElement.textContent = warning.message;

        warningElement.appendChild(titleElement);
        warningElement.appendChild(messageElement);
        warningsContainer.appendChild(warningElement);
    }
}


const SVG_NS = "http://www.w3.org/2000/svg";
const PREVIEW_WIDTH = 820;
const PREVIEW_HEIGHT = 500;
const PREVIEW_PADDING = 30;
const SMALL_FEATURE_CALLOUT_THRESHOLD = 48;


function createSvgElement(name, attributes = {}) {
    const element = document.createElementNS(SVG_NS, name);
    for (const [key, value] of Object.entries(attributes)) {
        element.setAttribute(key, String(value));
    }
    return element;
}


function validNumber(value) {
    return Number.isFinite(value) && value > 0;
}


function validBounds(bounds) {
    return (
        Array.isArray(bounds)
        && bounds.length === 4
        && bounds.every((value) => Number.isFinite(value))
        && bounds[2] > bounds[0]
        && bounds[3] > bounds[1]
    );
}


function allPreviewBounds(baseGeometry, featureData) {
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


function formatDimension(value) {
    if (!Number.isFinite(value)) {
        return "";
    }

    if (Math.abs(value - Math.round(value)) < 0.001) {
        return String(Math.round(value));
    }

    return value.toFixed(2).replace(/\.?0+$/, "");
}


function dimensionOffset(bounds) {
    return Math.max(boundsWidth(bounds), boundsHeight(bounds), 1) * 0.14;
}


function featureDimensionOffset(bounds) {
    return Math.max(Math.max(boundsWidth(bounds), boundsHeight(bounds), 1) * 0.22, 2);
}


function previewScaleForBounds(worldBounds) {
    const worldWidth = worldBounds[2] - worldBounds[0];
    const worldHeight = worldBounds[3] - worldBounds[1];

    return Math.min(
        (PREVIEW_WIDTH - 2 * PREVIEW_PADDING) / worldWidth,
        (PREVIEW_HEIGHT - 2 * PREVIEW_PADDING) / worldHeight,
    );
}


function drawPreviewDefs(svg) {
    const defs = createSvgElement("defs");
    const arrowMarker = createSvgElement("marker", {
        id: "preview-dimension-arrow",
        viewBox: "0 0 10 10",
        refX: 5,
        refY: 5,
        markerWidth: 5,
        markerHeight: 5,
        orient: "auto-start-reverse",
    });
    arrowMarker.appendChild(
        createSvgElement("path", {
            d: "M 0 0 L 10 5 L 0 10 z",
            class: "preview-dimension-arrow",
        }),
    );
    defs.appendChild(arrowMarker);
    svg.appendChild(defs);
}


function createPreviewMapper(worldBounds, fixedScale = null) {
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


function drawPreviewText(svg, text, x, y, className, attributes = {}) {
    const textElement = createSvgElement("text", {
        x: x,
        y: y,
        class: className,
        ...attributes,
    });
    textElement.textContent = text;
    svg.appendChild(textElement);
    return textElement;
}


function drawPreviewGrid(svg, mapper, worldBounds) {
    const origin = mapper.point(0, 0);
    const left = mapper.point(worldBounds[0], 0);
    const right = mapper.point(worldBounds[2], 0);
    const bottom = mapper.point(0, worldBounds[1]);
    const top = mapper.point(0, worldBounds[3]);

    svg.appendChild(
        createSvgElement("line", {
            x1: left[0],
            y1: left[1],
            x2: right[0],
            y2: right[1],
            class: "preview-axis",
        }),
    );
    svg.appendChild(
        createSvgElement("line", {
            x1: bottom[0],
            y1: bottom[1],
            x2: top[0],
            y2: top[1],
            class: "preview-axis",
        }),
    );
    svg.appendChild(
        createSvgElement("circle", {
            cx: origin[0],
            cy: origin[1],
            r: 2.5,
            class: "preview-origin",
        }),
    );
}


function drawCenterlines(svg, center, size, mapper) {
    const halfLength = size / 2;
    const horizontalStart = mapper.point(center[0] - halfLength, center[1]);
    const horizontalEnd = mapper.point(center[0] + halfLength, center[1]);
    const verticalStart = mapper.point(center[0], center[1] - halfLength);
    const verticalEnd = mapper.point(center[0], center[1] + halfLength);

    svg.appendChild(
        createSvgElement("line", {
            x1: horizontalStart[0],
            y1: horizontalStart[1],
            x2: horizontalEnd[0],
            y2: horizontalEnd[1],
            class: "preview-centerline",
        }),
    );
    svg.appendChild(
        createSvgElement("line", {
            x1: verticalStart[0],
            y1: verticalStart[1],
            x2: verticalEnd[0],
            y2: verticalEnd[1],
            class: "preview-centerline",
        }),
    );
}


function drawHorizontalDimension(svg, bounds, mapper, label, offset) {
    const y = bounds[1] - offset;
    const left = mapper.point(bounds[0], y);
    const right = mapper.point(bounds[2], y);
    const leftExtensionStart = mapper.point(bounds[0], bounds[1]);
    const rightExtensionStart = mapper.point(bounds[2], bounds[1]);
    const textPoint = mapper.point((bounds[0] + bounds[2]) / 2, y);

    svg.appendChild(
        createSvgElement("line", {
            x1: leftExtensionStart[0],
            y1: leftExtensionStart[1],
            x2: left[0],
            y2: left[1],
            class: "preview-extension-line",
        }),
    );
    svg.appendChild(
        createSvgElement("line", {
            x1: rightExtensionStart[0],
            y1: rightExtensionStart[1],
            x2: right[0],
            y2: right[1],
            class: "preview-extension-line",
        }),
    );
    svg.appendChild(
        createSvgElement("line", {
            x1: left[0],
            y1: left[1],
            x2: right[0],
            y2: right[1],
            class: "preview-dimension-line",
            "marker-start": "url(#preview-dimension-arrow)",
            "marker-end": "url(#preview-dimension-arrow)",
        }),
    );
    drawPreviewText(
        svg,
        label,
        textPoint[0],
        textPoint[1] - 5,
        "preview-dimension-text",
        {"text-anchor": "middle"},
    );
}


function drawVerticalDimension(svg, bounds, mapper, label, offset) {
    const x = bounds[0] - offset;
    const bottom = mapper.point(x, bounds[1]);
    const top = mapper.point(x, bounds[3]);
    const bottomExtensionStart = mapper.point(bounds[0], bounds[1]);
    const topExtensionStart = mapper.point(bounds[0], bounds[3]);
    const textPoint = mapper.point(x, (bounds[1] + bounds[3]) / 2);

    svg.appendChild(
        createSvgElement("line", {
            x1: bottomExtensionStart[0],
            y1: bottomExtensionStart[1],
            x2: bottom[0],
            y2: bottom[1],
            class: "preview-extension-line",
        }),
    );
    svg.appendChild(
        createSvgElement("line", {
            x1: topExtensionStart[0],
            y1: topExtensionStart[1],
            x2: top[0],
            y2: top[1],
            class: "preview-extension-line",
        }),
    );
    svg.appendChild(
        createSvgElement("line", {
            x1: bottom[0],
            y1: bottom[1],
            x2: top[0],
            y2: top[1],
            class: "preview-dimension-line",
            "marker-start": "url(#preview-dimension-arrow)",
            "marker-end": "url(#preview-dimension-arrow)",
        }),
    );
    drawPreviewText(
        svg,
        label,
        textPoint[0] - 6,
        textPoint[1],
        "preview-dimension-text",
        {
            "text-anchor": "middle",
            transform: `rotate(-90 ${textPoint[0] - 6} ${textPoint[1]})`,
        },
    );
}


function drawOverallDimensions(svg, baseGeometry, mapper) {
    if (baseGeometry.profile === "circle") {
        const center = mapper.point(0, 0);
        const leaderEnd = mapper.point(baseGeometry.radius * 0.75, baseGeometry.radius * 0.75);
        const textPoint = [
            Math.min(leaderEnd[0] + 20, PREVIEW_WIDTH - 80),
            Math.max(leaderEnd[1] - 16, 20),
        ];

        svg.appendChild(
            createSvgElement("line", {
                x1: center[0],
                y1: center[1],
                x2: textPoint[0],
                y2: textPoint[1],
                class: "preview-leader-line",
            }),
        );
        drawPreviewText(
            svg,
            `Ø${formatDimension(baseGeometry.diameter)}`,
            textPoint[0] + 4,
            textPoint[1] - 4,
            "preview-callout-text",
        );
        return;
    }

    const offset = dimensionOffset(baseGeometry.bounds);
    drawHorizontalDimension(
        svg,
        baseGeometry.bounds,
        mapper,
        formatDimension(boundsWidth(baseGeometry.bounds)),
        offset,
    );
    drawVerticalDimension(
        svg,
        baseGeometry.bounds,
        mapper,
        formatDimension(boundsHeight(baseGeometry.bounds)),
        offset,
    );
}


function featureNeedsLinearDimensions(feature) {
    return feature.profile === "rectangle";
}


function drawFeatureDimensions(svg, feature, mapper) {
    if (!featureNeedsLinearDimensions(feature)) {
        return;
    }

    const offset = featureDimensionOffset(feature.bounds);
    const widthLabel = formatDimension(boundsWidth(feature.bounds));
    const heightLabel = formatDimension(boundsHeight(feature.bounds));

    if (widthLabel !== "") {
        drawHorizontalDimension(
            svg,
            feature.bounds,
            mapper,
            widthLabel,
            offset,
        );
    }

    if (heightLabel !== "") {
        drawVerticalDimension(
            svg,
            feature.bounds,
            mapper,
            heightLabel,
            offset,
        );
    }
}


function regularPolygonPoints(center, radius, sides, mapper) {
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


function drawBoundsRectangle(svg, bounds, mapper, className) {
    const topLeft = mapper.point(bounds[0], bounds[3]);
    const bottomRight = mapper.point(bounds[2], bounds[1]);
    svg.appendChild(
        createSvgElement("rect", {
            x: topLeft[0],
            y: topLeft[1],
            width: bottomRight[0] - topLeft[0],
            height: bottomRight[1] - topLeft[1],
            class: className,
        }),
    );
}


function drawBasePreview(svg, baseGeometry, mapper) {
    if (baseGeometry.profile === "rectangle" || baseGeometry.profile === "projection") {
        drawBoundsRectangle(svg, baseGeometry.bounds, mapper, "preview-base");
        return;
    }

    if (baseGeometry.profile === "circle") {
        const center = mapper.point(0, 0);
        svg.appendChild(
            createSvgElement("circle", {
                cx: center[0],
                cy: center[1],
                r: mapper.length(baseGeometry.radius),
                class: "preview-base",
            }),
        );
        drawCenterlines(svg, [0, 0], baseGeometry.diameter * 1.25, mapper);
        return;
    }

    if (baseGeometry.profile === "polygon") {
        svg.appendChild(
            createSvgElement("polygon", {
                points: regularPolygonPoints(
                    [0, 0],
                    baseGeometry.radius,
                    baseGeometry.sides,
                    mapper,
                ),
                class: "preview-base",
            }),
        );
    }
}


function drawPreviewEmptyMessage(svg, text) {
    svg.innerHTML = "";
    svg.setAttribute("viewBox", `0 0 ${PREVIEW_WIDTH} ${PREVIEW_HEIGHT}`);
    svg.appendChild(
        createSvgElement("text", {
            x: PREVIEW_WIDTH / 2,
            y: PREVIEW_HEIGHT / 2,
            class: "preview-empty-text",
            "text-anchor": "middle",
        }),
    ).textContent = text;
}


function drawFeaturePreview(svg, feature, mapper) {
    let className = feature.operation === "cut" ? "preview-cut" : "preview-extrude";
    if (feature.isPrimary && !baseContainsFeatureBounds(feature.baseGeometry, feature.bounds, 0)) {
        className += " preview-outside";
    }

    if (feature.profile === "rectangle") {
        drawBoundsRectangle(svg, feature.bounds, mapper, className);
        return;
    }

    if (feature.profile === "circle") {
        const center = mapper.point(feature.position[0], feature.position[1]);
        svg.appendChild(
            createSvgElement("circle", {
                cx: center[0],
                cy: center[1],
                r: mapper.length(feature.radius),
                class: className,
            }),
        );
        if (feature.isPrimary) {
            drawCenterlines(svg, feature.position, feature.radius * 2.6, mapper);
        }
        return;
    }

    if (feature.profile === "polygon") {
        svg.appendChild(
            createSvgElement("polygon", {
                points: regularPolygonPoints(
                    feature.position,
                    feature.radius,
                    feature.sides,
                    mapper,
                ),
                class: className,
            }),
        );
    }
}


function drawFeatureCallout(svg, feature, mapper) {
    if (!feature.isPrimary) {
        return;
    }

    const center = mapper.point(...boundsCenter(feature.bounds));
    const calloutPoint = mapper.point(feature.bounds[2], feature.bounds[3]);
    const elbowPoint = [
        Math.min(calloutPoint[0] + 20, PREVIEW_WIDTH - 70),
        Math.max(calloutPoint[1] - 18, 20),
    ];
    let calloutText = "";

    if (feature.profile === "circle") {
        calloutText = `Ø${formatDimension(feature.radius * 2)}`;
        if (feature.operation === "cut") {
            calloutText += " THRU";
        }
    } else if (feature.profile === "rectangle") {
        const renderedWidth = mapper.length(boundsWidth(feature.bounds));
        const renderedHeight = mapper.length(boundsHeight(feature.bounds));
        if (
            renderedWidth >= SMALL_FEATURE_CALLOUT_THRESHOLD
            && renderedHeight >= SMALL_FEATURE_CALLOUT_THRESHOLD
        ) {
            return;
        }
        calloutText = `${formatDimension(feature.width)} × ${formatDimension(feature.height)}`;
    } else if (feature.profile === "polygon") {
        calloutText = `${feature.sides}X ON Ø${formatDimension(feature.radius * 2)}`;
    }

    if (calloutText === "") {
        return;
    }

    svg.appendChild(
        createSvgElement("line", {
            x1: center[0],
            y1: center[1],
            x2: elbowPoint[0],
            y2: elbowPoint[1],
            class: "preview-leader-line",
        }),
    );
    drawPreviewText(
        svg,
        calloutText,
        elbowPoint[0] + 4,
        elbowPoint[1] - 4,
        "preview-callout-text",
    );
}


function drawPreviewLabel(svg, feature, mapper) {
    const center = mapper.point(...boundsCenter(feature.bounds));
    svg.appendChild(
        createSvgElement("text", {
            x: center[0],
            y: center[1] + 4,
            class: "preview-label",
        }),
    ).textContent = feature.featureNumber;
}


function drawPreviewView(svg, baseGeometry, featureData, sharedScale = null) {
    svg.innerHTML = "";
    svg.setAttribute("viewBox", `0 0 ${PREVIEW_WIDTH} ${PREVIEW_HEIGHT}`);
    drawPreviewDefs(svg);

    if (baseGeometry === null) {
        drawPreviewEmptyMessage(svg, "No exact base dimensions");
        return;
    }

    const visibleFeatures = featureData.filter(
        (feature) => validBounds(feature.bounds),
    );
    const worldBounds = allPreviewBounds(baseGeometry, visibleFeatures);
    const mapper = createPreviewMapper(worldBounds, sharedScale);

    drawPreviewGrid(svg, mapper, worldBounds);
    drawBasePreview(svg, baseGeometry, mapper);
    drawOverallDimensions(svg, baseGeometry, mapper);

    for (const feature of visibleFeatures) {
        drawFeaturePreview(svg, feature, mapper);
        drawFeatureDimensions(svg, feature, mapper);
        if (feature.isPrimary) {
            drawPreviewLabel(svg, feature, mapper);
            drawFeatureCallout(svg, feature, mapper);
        }
    }

    if (visibleFeatures.length === 0) {
        svg.appendChild(
            createSvgElement("text", {
                x: PREVIEW_WIDTH / 2,
                y: PREVIEW_HEIGHT - 16,
                class: "preview-note-text",
                "text-anchor": "middle",
            }),
        ).textContent = "No exact features in this view";
    }
}


function updateManualPreview() {
    const panel = document.getElementById("manualPreviewPanel");
    const topSvg = document.getElementById("manualPreviewTopSvg");
    const frontSvg = document.getElementById("manualPreviewFrontSvg");
    const rightSvg = document.getElementById("manualPreviewRightSvg");
    const message = document.getElementById("manualPreviewMessage");
    if (!panel || !topSvg || !frontSvg || !rightSvg || !message) {
        return;
    }

    const isManualMode = !document.getElementById("manualBuilder").classList.contains("hidden");
    panel.classList.toggle("hidden", !isManualMode);
    if (!isManualMode) {
        return;
    }

    const baseGeometry = getManualBaseReviewGeometry();
    if (baseGeometry === null) {
        message.textContent = "Preview is available for exact rectangle, circle, and polygon bases. API-assisted dimensions can preview after they are generated.";
        drawPreviewEmptyMessage(topSvg, "Enter exact base dimensions");
        drawPreviewEmptyMessage(frontSvg, "Enter exact base dimensions");
        drawPreviewEmptyMessage(rightSvg, "Enter exact base dimensions");
        return;
    }

    if (
        !validNumber(boundsWidth(baseGeometry.bounds))
        || !validNumber(boundsHeight(baseGeometry.bounds))
        || !validNumber(baseGeometry.thickness)
        || (baseGeometry.profile === "polygon" && baseGeometry.sides < 3)
    ) {
        message.textContent = "Preview needs positive base dimensions and thickness.";
        drawPreviewEmptyMessage(topSvg, "Check base dimensions");
        drawPreviewEmptyMessage(frontSvg, "Check base dimensions");
        drawPreviewEmptyMessage(rightSvg, "Check base dimensions");
        return;
    }

    const featureData = collectExactFeaturePreviewData(baseGeometry).filter(
        (feature) => validBounds(feature.bounds),
    );
    const featureCards = Array.from(document.querySelectorAll(".feature-card"));
    const skippedCount = featureCards.length - new Set(featureData.map((feature) => feature.card)).size;
    const topGeometry = baseViewGeometry(baseGeometry, "top");
    const frontGeometry = baseViewGeometry(baseGeometry, "front");
    const rightGeometry = baseViewGeometry(baseGeometry, "right");
    const topFeatureData = featureData.filter((feature) => feature.viewName === "top");
    const frontFeatureData = featureData.filter((feature) => feature.viewName === "front");
    const rightFeatureData = featureData.filter((feature) => feature.viewName === "right");
    const viewBounds = [
        allPreviewBounds(topGeometry, topFeatureData),
        allPreviewBounds(frontGeometry, frontFeatureData),
        allPreviewBounds(rightGeometry, rightFeatureData),
    ];
    const sharedScale = Math.min(...viewBounds.map(previewScaleForBounds));

    drawPreviewView(
        topSvg,
        topGeometry,
        topFeatureData,
        sharedScale,
    );
    drawPreviewView(
        frontSvg,
        frontGeometry,
        frontFeatureData,
        sharedScale,
    );
    drawPreviewView(
        rightSvg,
        rightGeometry,
        rightFeatureData,
        sharedScale,
    );

    const primaryFeatureCount = featureData.filter((feature) => feature.isPrimary).length;
    const featureSummary = primaryFeatureCount === 1 ? "1 feature instance" : `${primaryFeatureCount} feature instances`;
    if (skippedCount > 0) {
        message.textContent = `Previewing ${featureSummary} across top/front/right views. ${skippedCount} API-assisted, feature-face, or polyline feature(s) are not shown yet.`;
    } else {
        message.textContent = `Previewing ${featureSummary} across top/front/right views from exact manual dimensions.`;
    }
}


function uniquePositions(positions) {
    const seen = new Set();
    const unique = [];

    for (const position of positions) {
        const key = position.map((value) => value.toFixed(6)).join(",");
        if (!seen.has(key)) {
            seen.add(key);
            unique.push(position);
        }
    }

    return unique;
}


function transformFeaturePositions(featureCard, seedPositions) {
    const pattern = featureCard.querySelector(".feature-pattern").value;
    const mirrorX = pattern !== "circular" && featureCard.querySelector(".feature-mirror-x").checked;
    const mirrorY = pattern !== "circular" && featureCard.querySelector(".feature-mirror-y").checked;

    let positions = seedPositions;

    if (pattern === "circular") {
        const count = Number(featureCard.querySelector(".feature-circular-count").value);
        const circularPositions = [];

        for (const seedPosition of seedPositions) {
            const positionX = seedPosition[0];
            const positionY = seedPosition[1];

            for (let index = 0; index < count; index += 1) {
                const angle = (2 * Math.PI * index) / count;
                const rotatedX = positionX * Math.cos(angle) - positionY * Math.sin(angle);
                const rotatedY = positionX * Math.sin(angle) + positionY * Math.cos(angle);
                circularPositions.push([
                    Number(rotatedX.toFixed(6)),
                    Number(rotatedY.toFixed(6)),
                ]);
            }
        }

        positions = circularPositions;
    }

    if (mirrorX) {
        positions = positions.flatMap((position) => [
            position,
            [position[0], -position[1]],
        ]);
    }

    if (mirrorY) {
        positions = positions.flatMap((position) => [
            position,
            [-position[0], position[1]],
        ]);
    }

    return uniquePositions(positions);
}


function buildExactFeatureOperation(featureCard) {
    const operationType = featureCard.querySelector(".feature-operation").value;
    const target = featureCard.querySelector(".feature-target").value;
    const profile = featureCard.querySelector(".feature-profile").value;
    const featureNumber = featureCard.dataset.featureNumber;
    const depthMode = featureCard.querySelector(".feature-depth-mode").value;
    const amount = Number(featureCard.querySelector(".feature-amount").value);

    const operation = {
        type: operationType,
        target: target,
        profile: profile,
        positions: transformFeaturePositions(
            featureCard,
            [[
                Number(featureCard.querySelector(".feature-position-x").value),
                Number(featureCard.querySelector(".feature-position-y").value),
            ]],
        ),
    };

    if (operationType === "cut") {
        operation.depth = depthMode === "through" ? "through" : amount;
    } else {
        operation.id = `feature_${featureNumber}`;
        operation.distance = amount;
    }

    if (profile === "rectangle") {
        operation.width = Number(featureCard.querySelector(".feature-width").value);
        operation.height = Number(featureCard.querySelector(".feature-height").value);
    } else if (profile === "circle") {
        operation.diameter = Number(featureCard.querySelector(".feature-diameter").value);
    } else if (profile === "polygon") {
        operation.diameter = Number(featureCard.querySelector(".feature-polygon-diameter").value);
        operation.sides = Number(featureCard.querySelector(".feature-polygon-sides").value);
    } else if (profile === "polyline") {
        throw new Error("Polyline features need the API-assisted point generator for profile points.");
    }

    return operation;
}


async function suggestFeatureOperation(featureCard) {
    const operationType = featureCard.querySelector(".feature-operation").value;
    const target = featureCard.querySelector(".feature-target").value;
    const profile = featureCard.querySelector(".feature-profile").value;
    const polylineDescription = featureCard.querySelector(".feature-polyline-description").value;

    let description = "Choose reasonable dimensions and position for a simple " + profile + " feature.";
    if (profile === "polyline") {
        description = polylineDescription;
    }

    const response = await fetch("/suggest-feature", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            operation_type: operationType,
            target: target,
            profile: profile,
            description: description,
        }),
    });

    const data = await response.json();
    if (data.status !== "success") {
        throw new Error(data.message);
    }

    return data.model_data.operations[0];
}


function applyExactFeaturePlacement(featureCard, operation) {
    const operationType = featureCard.querySelector(".feature-operation").value;
    const featureNumber = featureCard.dataset.featureNumber;
    const depthMode = featureCard.querySelector(".feature-depth-mode").value;
    const amount = Number(featureCard.querySelector(".feature-amount").value);

    operation.positions = transformFeaturePositions(featureCard, operation.positions);

    if (operationType === "cut") {
        operation.depth = depthMode === "through" ? "through" : amount;
        delete operation.id;
        delete operation.distance;
    } else {
        operation.id = `feature_${featureNumber}`;
        operation.distance = amount;
        delete operation.depth;
    }

    return operation;
}


function applyFeatureId(featureCard, operation) {
    const featureNumber = featureCard.dataset.featureNumber;

    if (operation.type === "add_extrude") {
        operation.id = `feature_${featureNumber}`;
    } else {
        delete operation.id;
    }

    return operation;
}


async function buildFeatureOperations() {
    const featureCards = document.querySelectorAll(".feature-card");
    const operations = [];

    for (const featureCard of featureCards) {
        const profile = featureCard.querySelector(".feature-profile").value;
        const useReasonableDimensions = featureCard.querySelector(".feature-reasonable").checked;

        if (useReasonableDimensions || profile === "polyline") {
            const suggestedOperation = await suggestFeatureOperation(featureCard);
            if (!useReasonableDimensions) {
                operations.push(
                    applyFeatureId(
                        featureCard,
                        applyExactFeaturePlacement(featureCard, suggestedOperation),
                    ),
                );
            } else {
                operations.push(applyFeatureId(featureCard, suggestedOperation));
            }
        } else {
            operations.push(applyFeatureId(featureCard, buildExactFeatureOperation(featureCard)));
        }
    }

    return operations;
}


async function suggestBaseModelData() {
    const baseProfile = document.getElementById("baseProfile").value;
    const useReasonableDefaults = document.getElementById("useReasonableDefaults").checked;
    const distance = Number(document.getElementById("baseDistance").value);
    const polylineDescription = document.getElementById("polylineDescription").value;

    let description = "Choose reasonable dimensions for a simple " + baseProfile + " base.";
    if (baseProfile === "polyline") {
        description = polylineDescription;
    }

    const requestBody = {
        profile: baseProfile,
        description: description,
        distance: useReasonableDefaults ? null : distance,
    };

    const response = await fetch("/suggest-base", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
    });

    const data = await response.json();
    if (data.status !== "success") {
        throw new Error(data.message);
    }

    return data.model_data;
}


async function buildManualCAD() {
    const button = document.getElementById("buildManualButton");
    const downloadLink = document.getElementById("downloadLink");
    const output = document.getElementById("output");
    const resultActions = document.getElementById("resultActions");
    const status = document.getElementById("status");

    status.textContent = "Building manual CAD model...";
    status.className = "status-message";
    output.textContent = "";
    resultActions.classList.add("hidden");
    resultSummary.classList.add("hidden");
    downloadLink.classList.add("hidden");

    button.disabled = true;
    button.textContent = "Building...";

    try {
        const baseProfile = document.getElementById("baseProfile").value;
        const useReasonableDefaults = document.getElementById("useReasonableDefaults").checked;
        let modelData;

        if (useReasonableDefaults || baseProfile === "polyline") {
            modelData = await suggestBaseModelData();
        } else {
            modelData = buildManualModelData();
        }

        const featureOperations = await buildFeatureOperations();
        modelData.operations.push(...featureOperations);

        const response = await fetch("/build", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                model_data: modelData,
                filename_hint: "manual " + document.getElementById("baseProfile").value + " base",
            }),
        });

        const data = await response.json();
        showResult(data);
    } catch (error) {
        showResult({
            status: "error",
            message: String(error),
            model_data: null,
        });
    } finally {
        button.disabled = false;
        button.textContent = "Build Manual Model";
    }
}


const buildManualButton = document.getElementById("buildManualButton");
buildManualButton.addEventListener("click", buildManualCAD);

const copyJsonButton = document.getElementById("copyJsonButton");
copyJsonButton.addEventListener("click", copyResultJson);

const useDemoPromptButton = document.getElementById("useDemoPromptButton");
useDemoPromptButton.addEventListener("click", useSelectedDemoPrompt);

const addFeatureButton = document.getElementById("addFeatureButton");
addFeatureButton.addEventListener("click", addFeatureCard);

const baseProfileSelect = document.getElementById("baseProfile");
baseProfileSelect.addEventListener("change", updateManualBuilderFields);

const useReasonableDefaultsCheckbox = document.getElementById("useReasonableDefaults");
useReasonableDefaultsCheckbox.addEventListener("change", updateManualBuilderFields);

const manualBuilder = document.getElementById("manualBuilder");
manualBuilder.addEventListener("input", updateDesignReviewWarnings);
manualBuilder.addEventListener("change", updateDesignReviewWarnings);
manualBuilder.addEventListener("input", updateManualPreview);
manualBuilder.addEventListener("change", updateManualPreview);

updateManualBuilderFields();
updateDesignReviewWarnings();
updateManualPreview();
loadDemoExamples();

const promptModeButton = document.getElementById("promptModeButton");
promptModeButton.addEventListener("click", () => setBuilderMode("prompt"));

const manualModeButton = document.getElementById("manualModeButton");
manualModeButton.addEventListener("click", () => setBuilderMode("manual"));
