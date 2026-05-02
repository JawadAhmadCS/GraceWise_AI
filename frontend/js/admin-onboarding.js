const API_BASE_URL = (() => {
    if (window.API_BASE_URL) return window.API_BASE_URL;
    const origin = window.location.origin;
    const host = window.location.hostname;
    const onPublicHost = host !== "127.0.0.1" && host !== "localhost";
    return onPublicHost ? `${origin}/api` : `${window.location.protocol}//${host}:5000`;
})();

function getToken() {
    return localStorage.getItem("access_token") || localStorage.getItem("accessToken");
}

function setBusy(isBusy) {
    const saveBtn = document.getElementById("saveBtn");
    const reloadBtn = document.getElementById("reloadBtn");
    const formatBtn = document.getElementById("formatBtn");

    saveBtn.disabled = isBusy;
    reloadBtn.disabled = isBusy;
    formatBtn.disabled = isBusy;
    saveBtn.textContent = isBusy ? "Saving..." : "Save Changes";
}

function setStatus(text) {
    const el = document.getElementById("statusText");
    el.textContent = text || "";
}

function showEditor() {
    document.getElementById("editorCard").style.display = "block";
    document.getElementById("superadminDenied").style.display = "none";
}

function showDenied() {
    document.getElementById("editorCard").style.display = "none";
    document.getElementById("superadminDenied").style.display = "block";
}

function renderSummary(questionBank) {
    const sections = Array.isArray(questionBank?.sections) ? questionBank.sections.length : 0;
    const questions = Array.isArray(questionBank?.questions) ? questionBank.questions.length : 0;
    document.getElementById("summaryText").textContent = `Questions: ${questions} | Sections: ${sections}`;
}

async function ensureSuperadmin() {
    if (!auth?.isLoggedIn()) {
        window.location.href = "sign_in.html";
        return false;
    }

    try {
        await auth.syncCurrentUser();
    } catch (_) {
        // Ignore sync failure and fallback to local user snapshot.
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
    setStatus("Loading onboarding config...");

    const response = await fetch(`${API_BASE_URL}/onboarding/v2/admin/question-bank`, {
        headers: {
            Authorization: `Bearer ${getToken()}`
        }
    });
    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.message || "Failed to load onboarding config");
    }

    const bank = data.question_bank || {};
    document.getElementById("filePath").textContent = `Path: ${data.path || "unknown"}`;
    document.getElementById("questionBankInput").value = JSON.stringify(bank, null, 2);
    renderSummary(bank);
    setStatus("Loaded latest onboarding config.");
}

function formatJson() {
    const input = document.getElementById("questionBankInput");
    try {
        const parsed = JSON.parse(input.value || "{}");
        input.value = JSON.stringify(parsed, null, 2);
        renderSummary(parsed);
        setStatus("JSON formatted.");
    } catch (error) {
        if (typeof Toast !== "undefined") Toast.error("JSON format invalid");
        setStatus(`JSON error: ${error.message}`);
    }
}

async function saveQuestionBank() {
    const input = document.getElementById("questionBankInput");
    let parsed;

    try {
        parsed = JSON.parse(input.value || "{}");
    } catch (error) {
        if (typeof Toast !== "undefined") Toast.error("Please fix JSON before saving");
        setStatus(`JSON error: ${error.message}`);
        return;
    }

    setBusy(true);
    setStatus("Saving onboarding config...");

    try {
        const response = await fetch(`${API_BASE_URL}/onboarding/v2/admin/question-bank`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${getToken()}`
            },
            body: JSON.stringify({ question_bank: parsed })
        });
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.message || "Save failed");
        }

        renderSummary(parsed);
        const backupPath = data?.result?.backup_path ? ` Backup: ${data.result.backup_path}` : "";
        setStatus(`Saved successfully.${backupPath}`);
        if (typeof Toast !== "undefined") Toast.success("Onboarding config saved");
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

document.addEventListener("DOMContentLoaded", async () => {
    initMobileMenu();

    const allowed = await ensureSuperadmin();
    if (!allowed) return;

    document.getElementById("reloadBtn").addEventListener("click", async () => {
        try {
            await loadQuestionBank();
        } catch (error) {
            setStatus(`Load failed: ${error.message}`);
            if (typeof Toast !== "undefined") Toast.error(error.message || "Load failed");
        }
    });
    document.getElementById("formatBtn").addEventListener("click", formatJson);
    document.getElementById("saveBtn").addEventListener("click", saveQuestionBank);

    try {
        await loadQuestionBank();
    } catch (error) {
        setStatus(`Load failed: ${error.message}`);
        if (typeof Toast !== "undefined") Toast.error(error.message || "Load failed");
    }
});
