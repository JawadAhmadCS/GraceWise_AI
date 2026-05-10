(function () {
    const apiBaseUrl = (window.API_BASE_URL || "").replace(/\/+$/, "");
    const statusBox = document.getElementById("result-status");
    const resultCard = document.getElementById("result-card");
    const STYLE_CONTENT = {
        CL: {
            title: "Classical",
            summary: "You thrive with structure, deep learning, and clear academic progression.",
        },
        CM: {
            title: "Charlotte Mason",
            summary: "You lean toward rich books, short focused lessons, and heart-level learning.",
        },
        UN: {
            title: "Unit Study",
            summary: "You love connecting subjects around shared themes and real-life projects.",
        },
        TR: {
            title: "Traditional",
            summary: "You prefer proven classroom-like methods and measurable progress.",
        },
        ON: {
            title: "Online",
            summary: "You value digital tools and flexible platform-based learning.",
        },
        US: {
            title: "Unschooling",
            summary: "You trust natural curiosity and prioritize intrinsic motivation.",
        },
        HY: {
            title: "Hybrid",
            summary: "You blend methods based on season, child, and subject.",
        },
    };

    function setStatus(message, type) {
        statusBox.textContent = message;
        statusBox.className = `status-box ${type || "info"}`;
    }

    function renderResult(styleCode) {
        const content = STYLE_CONTENT[styleCode];
        document.getElementById("result-title").textContent = `${content.title} (${styleCode})`;
        document.getElementById("result-summary").textContent = content.summary;
        document.getElementById("result-scores").innerHTML = `<li><span>Final Result Code</span><strong>${styleCode}</strong></li>`;
        resultCard.style.display = "block";
        setStatus("Your personalized result is ready.", "success");
    }

    async function loadResultFromToken(token) {
        const response = await fetch(`${apiBaseUrl}/quiz/homeschool-style/result?token=${encodeURIComponent(token)}`);
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.message || "Could not load your result.");
        }

        const styleCode = String((data.result && data.result.result_key) || "").trim().toUpperCase();
        if (!STYLE_CONTENT[styleCode]) {
            throw new Error("Invalid result style code.");
        }
        renderResult(styleCode);
    }

    async function loadResult() {
        const params = new URLSearchParams(window.location.search);
        const styleCode = String(params.get("style") || "").trim().toUpperCase();
        const token = String(params.get("token") || "").trim();

        if (STYLE_CONTENT[styleCode]) {
            renderResult(styleCode);
            return;
        }

        if (token) {
            try {
                setStatus("Loading your result...", "info");
                await loadResultFromToken(token);
            } catch (error) {
                setStatus(error.message || "Could not load your result.", "error");
            }
            return;
        }

        setStatus("Invalid or missing style code in URL.", "error");
    }

    loadResult();
})();
