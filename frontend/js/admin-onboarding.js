const API_BASE_URL = (() => {
    if (window.API_BASE_URL) return window.API_BASE_URL;
    const origin = window.location.origin;
    const host = window.location.hostname;
    const onPublicHost = host !== "127.0.0.1" && host !== "localhost";
    return onPublicHost ? `${origin}/api` : `${window.location.protocol}//${host}:5000`;
})();

let bank = null;
let selectedQuestionIndex = -1;

const REQUIRED_SECTION_KEYS = [
    "family_profile",
    "child_profiles",
    "education_homeschool_plan",
    "special_needs_learning_support",
    "schedule_meal_planning",
    "goals_preferences"
];

function getToken() {
    return localStorage.getItem("access_token") || localStorage.getItem("accessToken");
}

function setStatus(text) {
    const el = document.getElementById("statusText");
    el.textContent = text || "";
}

function setBusy(isBusy) {
    [
        "reloadBtn",
        "saveBtn",
        "addQuestionBtn",
        "duplicateQuestionBtn",
        "moveUpBtn",
        "moveDownBtn",
        "deleteQuestionBtn",
        "applyQuestionBtn",
        "addOptionBtn"
    ].forEach((id) => {
        const btn = document.getElementById(id);
        if (btn) btn.disabled = isBusy;
    });

    const saveBtn = document.getElementById("saveBtn");
    if (saveBtn) saveBtn.textContent = isBusy ? "Saving..." : "Save All Changes";
}

function showEditor() {
    document.getElementById("editorCard").style.display = "block";
    document.getElementById("superadminDenied").style.display = "none";
}

function showDenied() {
    document.getElementById("editorCard").style.display = "none";
    document.getElementById("superadminDenied").style.display = "block";
}

function cloneData(data) {
    return JSON.parse(JSON.stringify(data));
}

function normalizeBankShape(raw) {
    const normalized = cloneData(raw || {});
    if (!normalized.flow || typeof normalized.flow !== "object") normalized.flow = { mode: "linear" };
    if (!Array.isArray(normalized.sections)) normalized.sections = [];
    if (!Array.isArray(normalized.questions)) normalized.questions = [];

    // Ensure required section keys exist.
    const byKey = new Map(normalized.sections.map((s) => [s.key, s]));
    normalized.sections = REQUIRED_SECTION_KEYS.map((key) => {
        const existing = byKey.get(key) || {};
        return {
            key,
            title: String(existing.title || key.replace(/_/g, " "))
        };
    });

    return normalized;
}

function renderSummary() {
    const sections = Array.isArray(bank?.sections) ? bank.sections.length : 0;
    const questions = Array.isArray(bank?.questions) ? bank.questions.length : 0;
    document.getElementById("summaryText").textContent = `Questions: ${questions} | Sections: ${sections}`;
}

function renderGeneralFields() {
    document.getElementById("versionInput").value = bank.version || "";
    document.getElementById("flowModeInput").value = (bank.flow && bank.flow.mode) ? bank.flow.mode : "linear";
}

function renderSectionTitles() {
    const container = document.getElementById("sectionTitleList");
    container.innerHTML = "";

    bank.sections.forEach((section) => {
        const row = document.createElement("div");
        row.className = "section-item";

        const keyPill = document.createElement("div");
        keyPill.className = "section-key-pill";
        keyPill.textContent = section.key;

        const titleInput = document.createElement("input");
        titleInput.type = "text";
        titleInput.value = section.title || "";
        titleInput.dataset.sectionKey = section.key;
        titleInput.addEventListener("input", () => {
            section.title = titleInput.value;
        });

        row.appendChild(keyPill);
        row.appendChild(titleInput);
        container.appendChild(row);
    });
}

function applyGeneralFieldsToBank() {
    bank.version = document.getElementById("versionInput").value.trim();
    if (!bank.flow || typeof bank.flow !== "object") bank.flow = {};
    bank.flow.mode = document.getElementById("flowModeInput").value || "linear";
}

function slugifyValue(value, fallback = "item") {
    const slug = String(value || "")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_")
        .replace(/^_+|_+$/g, "")
        .slice(0, 48);
    return slug || fallback;
}

function buildQuestionId(sectionKey, promptText) {
    const sectionSlug = slugifyValue(sectionKey, "section");
    const promptSlug = slugifyValue(promptText, "question");
    return `q_${sectionSlug}_${promptSlug}`;
}

function buildFieldKey(sectionKey, promptText) {
    const sectionSlug = slugifyValue(sectionKey, "section");
    const promptSlug = slugifyValue(promptText, "field");
    return `${sectionSlug}_${promptSlug}`;
}

function makeUniqueValue(baseValue, usedSet) {
    if (!usedSet.has(baseValue)) return baseValue;
    let counter = 2;
    let candidate = `${baseValue}_${counter}`;
    while (usedSet.has(candidate)) {
        counter += 1;
        candidate = `${baseValue}_${counter}`;
    }
    return candidate;
}

function getUsedIdSet(indexToIgnore = -1) {
    const used = new Set();
    bank.questions.forEach((question, idx) => {
        if (idx === indexToIgnore) return;
        const id = String(question.id || "").trim();
        if (id) used.add(id);
    });
    return used;
}

function getUsedFieldSet(indexToIgnore = -1) {
    const used = new Set();
    bank.questions.forEach((question, idx) => {
        if (idx === indexToIgnore) return;
        const field = String(question.field || "").trim();
        if (field) used.add(field);
    });
    return used;
}

function generateIdentifiers(sectionKey, promptText, indexToIgnore = -1) {
    const baseId = buildQuestionId(sectionKey, promptText);
    const baseField = buildFieldKey(sectionKey, promptText);
    const id = makeUniqueValue(baseId, getUsedIdSet(indexToIgnore));
    const field = makeUniqueValue(baseField, getUsedFieldSet(indexToIgnore));
    return { id, field };
}

function ensureQuestionIdentifiers(question, indexToIgnore = -1) {
    const hasId = String(question.id || "").trim().length > 0;
    const hasField = String(question.field || "").trim().length > 0;
    if (hasId && hasField) return question;

    const generated = generateIdentifiers(question.section, question.prompt, indexToIgnore);
    if (!hasId) question.id = generated.id;
    if (!hasField) question.field = generated.field;
    return question;
}

function ensureAllIdentifiers() {
    bank.questions.forEach((question, index) => {
        ensureQuestionIdentifiers(question, index);
        validateUnique(question, index);
    });
}

function formatQuestionRowText(question) {
    const section = question.section || "no-section";
    const type = question.type || "text";
    const required = question.required ? "Required" : "Optional";
    return `${section} | ${type} | ${required}`;
}

function renderQuestionList() {
    const listEl = document.getElementById("questionList");
    const searchText = (document.getElementById("questionSearch").value || "").trim().toLowerCase();
    listEl.innerHTML = "";

    bank.questions.forEach((q, index) => {
        const haystack = `${q.id || ""} ${q.field || ""} ${q.prompt || ""}`.toLowerCase();
        if (searchText && !haystack.includes(searchText)) return;

        const row = document.createElement("div");
        row.className = `question-row ${index === selectedQuestionIndex ? "active" : ""}`;
        row.dataset.index = String(index);

        const id = document.createElement("div");
        id.className = "question-row-id";
        id.textContent = q.prompt || "Untitled question";

        const meta = document.createElement("div");
        meta.className = "question-row-meta";
        meta.textContent = formatQuestionRowText(q);

        row.appendChild(id);
        row.appendChild(meta);

        row.addEventListener("click", () => {
            if (!applyQuestionFromEditor()) return;
            selectedQuestionIndex = index;
            renderQuestionList();
            renderQuestionEditor();
        });

        listEl.appendChild(row);
    });
}

function renderSectionSelect() {
    const select = document.getElementById("qSectionInput");
    select.innerHTML = "";
    bank.sections.forEach((section) => {
        const option = document.createElement("option");
        option.value = section.key;
        option.textContent = `${section.title} (${section.key})`;
        select.appendChild(option);
    });
}

function stringifyPrimitive(value) {
    if (typeof value === "boolean") return value ? "true" : "false";
    if (typeof value === "number") return String(value);
    if (value === null || value === undefined) return "";
    return String(value);
}

function isSelectType(type) {
    return type === "single_select" || type === "multi_select";
}

function renderCondition(question) {
    const cond = question.condition;
    const modeInput = document.getElementById("condModeInput");
    const fieldInput = document.getElementById("condFieldInput");
    const valueInput = document.getElementById("condValueInput");

    modeInput.value = "none";
    fieldInput.value = "";
    valueInput.value = "";

    if (!cond || typeof cond !== "object") return;

    fieldInput.value = cond.field || "";

    if (Object.prototype.hasOwnProperty.call(cond, "equals")) {
        modeInput.value = "equals";
        valueInput.value = stringifyPrimitive(cond.equals);
        return;
    }

    if (Array.isArray(cond.in)) {
        modeInput.value = "in";
        valueInput.value = cond.in.map((item) => stringifyPrimitive(item)).join(", ");
        return;
    }

    if (cond.exists === true) {
        modeInput.value = "exists";
    }
}

function createOptionRow(initialLabel = "", initialValue = "") {
    const row = document.createElement("div");
    row.className = "option-row";

    const labelInput = document.createElement("input");
    labelInput.type = "text";
    labelInput.className = "option-label-input";
    labelInput.placeholder = "Option name (e.g. Morning)";
    labelInput.value = initialLabel;

    const valueInput = document.createElement("input");
    valueInput.type = "hidden";
    valueInput.className = "option-value-input";
    valueInput.value = initialValue;

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "remove-option-btn";
    removeBtn.textContent = "Remove";
    removeBtn.addEventListener("click", () => {
        row.remove();
    });

    row.appendChild(labelInput);
    row.appendChild(removeBtn);
    row.appendChild(valueInput);
    return row;
}

function setOptionsEditorState(enabled) {
    const container = document.getElementById("optionRows");
    const addBtn = document.getElementById("addOptionBtn");
    container.style.opacity = enabled ? "1" : "0.6";
    addBtn.disabled = !enabled;

    Array.from(container.querySelectorAll("input,button")).forEach((el) => {
        el.disabled = !enabled;
    });
}

function renderOptions(question) {
    const container = document.getElementById("optionRows");
    container.innerHTML = "";

    const options = Array.isArray(question.options) ? question.options : [];
    options.forEach((opt) => {
        if (opt && typeof opt === "object" && !Array.isArray(opt)) {
            const value = String(opt.value || "").trim();
            const label = String(opt.label || value).trim();
            container.appendChild(createOptionRow(label, value));
            return;
        }
        const val = String(opt || "").trim();
        if (val) container.appendChild(createOptionRow(val, ""));
    });

    if (!container.children.length) {
        container.appendChild(createOptionRow("", ""));
    }
}

function parseOptionsFromRows() {
    const container = document.getElementById("optionRows");
    const rows = Array.from(container.querySelectorAll(".option-row"));
    const parsed = [];
    const usedValues = new Set();

    for (const row of rows) {
        const labelInput = row.querySelector(".option-label-input");
        const valueInput = row.querySelector(".option-value-input");
        const label = String(labelInput?.value || "").trim();
        const existingValue = String(valueInput?.value || "").trim();
        if (!label) continue;

        const candidateBase = existingValue || slugifyValue(label, "option");
        const value = makeUniqueValue(candidateBase, usedValues);
        usedValues.add(value);
        if (valueInput) valueInput.value = value;

        parsed.push({ value, label });
    }

    return parsed;
}

function renderQuestionEditor() {
    const q = bank.questions[selectedQuestionIndex];

    if (!q) {
        [
            "qPromptInput",
            "qRetryPromptInput",
            "condFieldInput",
            "condValueInput"
        ].forEach((id) => {
            document.getElementById(id).value = "";
        });
        document.getElementById("optionRows").innerHTML = "";
        document.getElementById("qRequiredInput").checked = false;
        document.getElementById("qTypeInput").value = "text";
        document.getElementById("condModeInput").value = "none";
        setOptionsEditorState(false);
        return;
    }

    document.getElementById("qSectionInput").value = q.section || "";
    document.getElementById("qTypeInput").value = q.type || "text";
    document.getElementById("qRequiredInput").checked = !!q.required;
    document.getElementById("qPromptInput").value = q.prompt || "";
    document.getElementById("qRetryPromptInput").value = q.retry_prompt || "";

    renderOptions(q);
    renderCondition(q);
    setOptionsEditorState(isSelectType(q.type));
}

function parsePrimitive(raw) {
    const value = String(raw || "").trim();
    if (!value) return "";
    if (value.toLowerCase() === "true") return true;
    if (value.toLowerCase() === "false") return false;
    if (/^-?\d+$/.test(value)) return Number(value);
    return value;
}

function buildConditionFromEditor() {
    const mode = document.getElementById("condModeInput").value;
    const field = document.getElementById("condFieldInput").value.trim();
    const rawValue = document.getElementById("condValueInput").value.trim();

    if (mode === "none") return null;
    if (!field) throw new Error("Condition field key is required.");

    if (mode === "equals") {
        if (!rawValue) throw new Error("Condition value is required for equals rule.");
        return { field, equals: parsePrimitive(rawValue) };
    }

    if (mode === "in") {
        if (!rawValue) throw new Error("At least one condition value is required.");
        const values = rawValue
            .split(",")
            .map((item) => parsePrimitive(item))
            .filter((item) => String(item).trim() !== "");
        if (!values.length) throw new Error("At least one valid condition value is required.");
        return { field, in: values };
    }

    if (mode === "exists") {
        return { field, exists: true };
    }

    return null;
}

function validateUnique(question, indexToIgnore) {
    const dupId = bank.questions.findIndex((q, idx) => idx !== indexToIgnore && q.id === question.id);
    if (dupId !== -1) throw new Error(`Question ID '${question.id}' is already used.`);

    const dupField = bank.questions.findIndex((q, idx) => idx !== indexToIgnore && q.field === question.field);
    if (dupField !== -1) throw new Error(`Field key '${question.field}' is already used.`);
}

function applyQuestionFromEditor() {
    if (selectedQuestionIndex < 0 || !bank.questions[selectedQuestionIndex]) return true;

    const q = bank.questions[selectedQuestionIndex];

    try {
        const section = document.getElementById("qSectionInput").value;
        const type = document.getElementById("qTypeInput").value;
        const required = document.getElementById("qRequiredInput").checked;
        const prompt = document.getElementById("qPromptInput").value.trim();
        const retryPrompt = document.getElementById("qRetryPromptInput").value.trim();

        if (!section) throw new Error("Section is required.");
        if (!prompt) throw new Error("Question prompt is required.");

        const updated = { ...q };
        updated.section = section;
        updated.type = type;
        updated.required = required;
        updated.prompt = prompt;

        if (retryPrompt) updated.retry_prompt = retryPrompt;
        else delete updated.retry_prompt;

        if (isSelectType(type)) {
            const options = parseOptionsFromRows();
            if (!options.length) throw new Error("Select questions need at least one option.");
            updated.options = options;
        } else {
            delete updated.options;
        }

        const condition = buildConditionFromEditor();
        if (condition) updated.condition = condition;
        else delete updated.condition;

        ensureQuestionIdentifiers(updated, selectedQuestionIndex);
        validateUnique(updated, selectedQuestionIndex);
        bank.questions[selectedQuestionIndex] = updated;

        renderQuestionList();
        renderSummary();
        setStatus("Question updated locally.");
        return true;
    } catch (error) {
        setStatus(error.message || "Could not apply question changes.");
        if (typeof Toast !== "undefined") Toast.error(error.message || "Question update failed");
        return false;
    }
}

function selectQuestion(index) {
    if (index < 0 || index >= bank.questions.length) {
        selectedQuestionIndex = -1;
    } else {
        selectedQuestionIndex = index;
    }
    renderQuestionList();
    renderQuestionEditor();
}

function createDefaultQuestion() {
    const section = bank.sections[0]?.key || REQUIRED_SECTION_KEYS[0];
    const prompt = "New onboarding question";
    const generated = generateIdentifiers(section, prompt);
    return {
        id: generated.id,
        section,
        field: generated.field,
        type: "text",
        required: false,
        prompt
    };
}

function addQuestion() {
    if (!applyQuestionFromEditor()) return;
    bank.questions.push(createDefaultQuestion());
    selectQuestion(bank.questions.length - 1);
    renderSummary();
}

function duplicateQuestion() {
    const current = bank.questions[selectedQuestionIndex];
    if (!current) return;
    if (!applyQuestionFromEditor()) return;

    const copy = cloneData(current);
    const generated = generateIdentifiers(copy.section, `${copy.prompt} copy`);
    copy.id = generated.id;
    copy.field = generated.field;

    bank.questions.splice(selectedQuestionIndex + 1, 0, copy);
    selectQuestion(selectedQuestionIndex + 1);
    renderSummary();
}

function moveQuestion(direction) {
    if (!applyQuestionFromEditor()) return;
    const from = selectedQuestionIndex;
    const to = from + direction;
    if (from < 0 || to < 0 || to >= bank.questions.length) return;

    const temp = bank.questions[from];
    bank.questions[from] = bank.questions[to];
    bank.questions[to] = temp;
    selectQuestion(to);
}

function deleteQuestion() {
    if (selectedQuestionIndex < 0) return;
    const q = bank.questions[selectedQuestionIndex];
    const promptLabel = q.prompt || "this question";
    const ok = window.confirm(`Delete '${promptLabel}'?`);
    if (!ok) return;

    bank.questions.splice(selectedQuestionIndex, 1);
    const newIndex = Math.min(selectedQuestionIndex, bank.questions.length - 1);
    selectQuestion(newIndex);
    renderSummary();
}

async function ensureSuperadmin() {
    if (!auth?.isLoggedIn()) {
        window.location.href = "sign_in.html";
        return false;
    }

    try {
        await auth.syncCurrentUser();
    } catch (_) {
        // Keep local snapshot if sync fails.
    }

    const user = auth.getCurrentUser();
    if (!user || !user.is_admin) {
        window.location.href = "dashboard.html";
        return false;
    }

    if (!user.is_superadmin) {
        showDenied();
        return false;
    }

    showEditor();
    return true;
}

async function loadQuestionBank() {
    setStatus("Loading onboarding settings...");

    const response = await fetch(`${API_BASE_URL}/onboarding/v2/admin/question-bank`, {
        headers: {
            Authorization: `Bearer ${getToken()}`
        }
    });
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.message || "Failed to load onboarding settings");
    }

    bank = normalizeBankShape(data.question_bank || {});
    document.getElementById("filePath").textContent = `Path: ${data.path || "unknown"}`;

    renderGeneralFields();
    renderSectionTitles();
    renderSectionSelect();

    selectQuestion(bank.questions.length ? 0 : -1);
    renderSummary();
    setStatus("Loaded onboarding settings.");
}

async function saveAllChanges() {
    if (!applyQuestionFromEditor()) return;
    try {
        ensureAllIdentifiers();
    } catch (error) {
        setStatus(error.message || "Could not prepare question IDs.");
        if (typeof Toast !== "undefined") Toast.error(error.message || "Save blocked");
        return;
    }

    applyGeneralFieldsToBank();

    setBusy(true);
    setStatus("Saving onboarding settings...");

    try {
        const response = await fetch(`${API_BASE_URL}/onboarding/v2/admin/question-bank`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${getToken()}`
            },
            body: JSON.stringify({ question_bank: bank })
        });
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.message || "Save failed");
        }

        const backupPath = data?.result?.backup_path ? ` Backup: ${data.result.backup_path}` : "";
        setStatus(`Saved successfully.${backupPath}`);
        if (typeof Toast !== "undefined") Toast.success("Onboarding settings saved");
    } catch (error) {
        setStatus(`Save failed: ${error.message}`);
        if (typeof Toast !== "undefined") Toast.error(error.message || "Save failed");
    } finally {
        setBusy(false);
    }
}

function initMobileMenu() {
    const mobileToggle = document.querySelector(".mobile-menu-toggle");
    const sidebar = document.querySelector(".sidebar");
    const overlay = document.querySelector(".mobile-overlay");
    const body = document.body;

    function toggleMobileMenu() {
        sidebar.classList.toggle("mobile-open");
        overlay.classList.toggle("active");
        body.classList.toggle("menu-open");
        const icon = mobileToggle.querySelector("i");
        icon.className = sidebar.classList.contains("mobile-open") ? "fas fa-times" : "fas fa-bars";
    }

    if (mobileToggle) mobileToggle.addEventListener("click", toggleMobileMenu);
    if (overlay) overlay.addEventListener("click", toggleMobileMenu);
}

function bindEvents() {
    document.getElementById("questionSearch").addEventListener("input", renderQuestionList);
    document.getElementById("qTypeInput").addEventListener("change", () => {
        const type = document.getElementById("qTypeInput").value;
        const enabled = isSelectType(type);
        setOptionsEditorState(enabled);
        if (enabled) {
            const container = document.getElementById("optionRows");
            if (!container.children.length) {
                container.appendChild(createOptionRow("", ""));
            }
        }
    });

    document.getElementById("addOptionBtn").addEventListener("click", () => {
        const container = document.getElementById("optionRows");
        container.appendChild(createOptionRow("", ""));
    });

    document.getElementById("reloadBtn").addEventListener("click", async () => {
        try {
            await loadQuestionBank();
        } catch (error) {
            setStatus(`Load failed: ${error.message}`);
            if (typeof Toast !== "undefined") Toast.error(error.message || "Load failed");
        }
    });

    document.getElementById("saveBtn").addEventListener("click", saveAllChanges);
    document.getElementById("addQuestionBtn").addEventListener("click", addQuestion);
    document.getElementById("duplicateQuestionBtn").addEventListener("click", duplicateQuestion);
    document.getElementById("moveUpBtn").addEventListener("click", () => moveQuestion(-1));
    document.getElementById("moveDownBtn").addEventListener("click", () => moveQuestion(1));
    document.getElementById("deleteQuestionBtn").addEventListener("click", deleteQuestion);
    document.getElementById("applyQuestionBtn").addEventListener("click", applyQuestionFromEditor);
}

document.addEventListener("DOMContentLoaded", async () => {
    initMobileMenu();

    const allowed = await ensureSuperadmin();
    if (!allowed) return;

    bindEvents();

    try {
        await loadQuestionBank();
    } catch (error) {
        setStatus(`Load failed: ${error.message}`);
        if (typeof Toast !== "undefined") Toast.error(error.message || "Load failed");
    }
});
