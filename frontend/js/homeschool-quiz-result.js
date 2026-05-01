(function () {
    const apiBaseUrl = (window.API_BASE_URL || "").replace(/\/+$/, "");
    const statusBox = document.getElementById("result-status");
    const resultCard = document.getElementById("result-card");

    function setStatus(message, type) {
        statusBox.textContent = message;
        statusBox.className = `status-box ${type || "info"}`;
    }

    function renderResult(result) {
        document.getElementById("result-title").textContent = result.result_title;
        document.getElementById("result-summary").textContent = result.result_summary;

        const scoreList = Object.entries(result.score_breakdown || {})
            .sort((a, b) => b[1] - a[1])
            .map(([style, score]) => {
                const label = style
                    .replace(/_/g, " ")
                    .replace(/\b\w/g, (char) => char.toUpperCase());
                return `<li><span>${label}</span><strong>${score}</strong></li>`;
            })
            .join("");

        document.getElementById("result-scores").innerHTML = scoreList;
        resultCard.style.display = "block";
        setStatus("Your personalized result is ready.", "success");
    }

    async function loadResult() {
        const params = new URLSearchParams(window.location.search);
        const token = params.get("token");

        if (!token) {
            setStatus("Missing result token.", "error");
            return;
        }

        try {
            setStatus("Loading your result...", "info");
            const response = await fetch(`${apiBaseUrl}/quiz/homeschool-style/result?token=${encodeURIComponent(token)}`);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || "Could not load your result.");
            }

            renderResult(data.result);
        } catch (error) {
            setStatus(error.message || "Could not load your result.", "error");
        }
    }

    loadResult();
})();
