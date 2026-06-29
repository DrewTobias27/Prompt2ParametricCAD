async function generateCAD() {
    const button = document.getElementById("generateButton");
    const downloadLink = document.getElementById("downloadLink");
    const output = document.getElementById("output");
    const prompt = document.getElementById("prompt").value;
    const status = document.getElementById("status");

    status.textContent = "Generating CAD model...";
    output.textContent = "";
    downloadLink.style.display = "none";

    button.disabled = true;
    button.textContent = "Generating...";

    try {
        const response = await fetch("/generate", {
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
}


function showResult(data) {
    const downloadLink = document.getElementById("downloadLink");
    const output = document.getElementById("output");
    const status = document.getElementById("status");

    if (data.status === "success") {
        status.textContent = "Success";
        downloadLink.style.display = "block";
        downloadLink.href = data.download_url;
    } else {
        status.textContent = "Error: " + data.message;
        downloadLink.style.display = "none";
    }

    output.textContent = JSON.stringify(data, null, 2);
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
    const rectangleFields = featureCard.querySelector(".feature-rectangle-fields");
    const circleFields = featureCard.querySelector(".feature-circle-fields");
    const polygonFields = featureCard.querySelector(".feature-polygon-fields");
    const polylineFields = featureCard.querySelector(".feature-polyline-fields");
    const positionFields = featureCard.querySelector(".feature-position-fields");
    const mirrorFields = featureCard.querySelector(".feature-mirror-fields");
    const circularPatternFields = featureCard.querySelector(".feature-circular-pattern-fields");
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
    amountFields.classList.toggle("hidden", usesApiAssistance);

    if (featureOperation === "cut") {
        amountLabel.textContent = "Cut depth";
    } else {
        amountLabel.textContent = "Extrusion distance";
    }
}


function addFeatureCard() {
    featureCount += 1;

    const featureList = document.getElementById("featureList");
    const featureCard = document.createElement("div");
    featureCard.className = "feature-card";
    featureCard.innerHTML = `
        <div class="feature-card-header">
            <h4>Feature ${featureCount}</h4>
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
                    <option value="base.top">Top</option>
                    <option value="base.bottom">Bottom</option>
                    <option value="base.front">Front</option>
                    <option value="base.back">Back</option>
                    <option value="base.left">Left</option>
                    <option value="base.right">Right</option>
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
        </div>

        <label class="checkbox-row">
            <input class="feature-reasonable" type="checkbox" checked>
            Use reasonable dimensions
        </label>

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
    });

    const featureOperationSelect = featureCard.querySelector(".feature-operation");
    featureOperationSelect.addEventListener("change", () => {
        updateFeatureCardFields(featureCard);
    });

    const featureProfileSelect = featureCard.querySelector(".feature-profile");
    featureProfileSelect.addEventListener("change", () => {
        updateFeatureCardFields(featureCard);
    });

    const featurePatternSelect = featureCard.querySelector(".feature-pattern");
    featurePatternSelect.addEventListener("change", () => {
        updateFeatureCardFields(featureCard);
    });

    const featureReasonableCheckbox = featureCard.querySelector(".feature-reasonable");
    featureReasonableCheckbox.addEventListener("change", () => {
        updateFeatureCardFields(featureCard);
    });

    featureList.appendChild(featureCard);
    updateFeatureCardFields(featureCard);
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
    const mirrorX = featureCard.querySelector(".feature-mirror-x").checked;
    const mirrorY = featureCard.querySelector(".feature-mirror-y").checked;

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
        operation.depth = amount;
    } else {
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
    const amount = Number(featureCard.querySelector(".feature-amount").value);

    operation.positions = transformFeaturePositions(featureCard, operation.positions);

    if (operationType === "cut") {
        operation.depth = amount;
        delete operation.distance;
    } else {
        operation.distance = amount;
        delete operation.depth;
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
                operations.push(applyExactFeaturePlacement(featureCard, suggestedOperation));
            } else {
                operations.push(suggestedOperation);
            }
        } else {
            operations.push(buildExactFeatureOperation(featureCard));
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
    const status = document.getElementById("status");

    status.textContent = "Building manual CAD model...";
    output.textContent = "";
    downloadLink.style.display = "none";

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

const addFeatureButton = document.getElementById("addFeatureButton");
addFeatureButton.addEventListener("click", addFeatureCard);

const baseProfileSelect = document.getElementById("baseProfile");
baseProfileSelect.addEventListener("change", updateManualBuilderFields);

const useReasonableDefaultsCheckbox = document.getElementById("useReasonableDefaults");
useReasonableDefaultsCheckbox.addEventListener("change", updateManualBuilderFields);

updateManualBuilderFields();

const promptModeButton = document.getElementById("promptModeButton");
promptModeButton.addEventListener("click", () => setBuilderMode("prompt"));

const manualModeButton = document.getElementById("manualModeButton");
manualModeButton.addEventListener("click", () => setBuilderMode("manual"));
