(function () {
    const apiBaseUrl = (window.API_BASE_URL || "").replace(/\/+$/, "");
    const resultState = document.getElementById("quizResultState");
    const resultList = document.getElementById("quizResultList");

    function setState(message) {
        if (resultState) {
            resultState.textContent = message;
            resultState.style.display = "block";
        }
    }

    function hideState() {
        if (resultState) {
            resultState.style.display = "none";
        }
    }

    function formatDate(isoString) {
        if (!isoString) return "Unknown date";
        const date = new Date(isoString);
        if (Number.isNaN(date.getTime())) return "Unknown date";
        return date.toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
        });
    }

    function formatLabel(key) {
        return String(key || "")
            .replace(/_/g, " ")
            .replace(/\b\w/g, (c) => c.toUpperCase());
    }

    function renderResults(results) {
        if (!resultList) return;

        if (!Array.isArray(results) || results.length === 0) {
            setState("No saved quiz results found for your account email yet.");
            resultList.innerHTML = "";
            return;
        }

        hideState();
        resultList.innerHTML = results
            .map((item) => {
                const scoreBreakdown = Object.entries(item.score_breakdown || {})
                    .sort((a, b) => b[1] - a[1])
                    .map(
                        ([style, score]) =>
                            `<div class="score-pill"><span>${formatLabel(style)}</span><strong>${score}</strong></div>`,
                    )
                    .join("");

                return `
                    <article class="history-card">
                        <div class="history-head">
                            <h3>${item.result_title || "Quiz Result"}</h3>
                            <span class="history-date">${formatDate(item.completed_at)}</span>
                        </div>
                        <p class="history-summary">${item.result_summary || ""}</p>
                        <div class="score-grid">${scoreBreakdown}</div>
                    </article>
                `;
            })
            .join("");
    }

    async function loadMyResults() {
        if (!auth || !auth.accessToken) {
            setState("Please sign in to view your saved quiz results.");
            return;
        }

        try {
            setState("Loading your quiz results...");
            const response = await fetch(`${apiBaseUrl}/quiz/homeschool-style/my-results`, {
                headers: {
                    Authorization: `Bearer ${auth.accessToken}`,
                    "Content-Type": "application/json",
                },
            });
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.message || "Could not load your quiz results.");
            }

            renderResults(data.results || []);
        } catch (error) {
            setState(error.message || "Could not load your quiz results.");
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        var toggle = document.querySelector(".mobile-menu-toggle");
        var sidebar = document.querySelector(".sidebar");
        var overlay = document.querySelector(".mobile-overlay");
        if (toggle && sidebar) {
            toggle.addEventListener("click", function () {
                sidebar.classList.toggle("mobile-open");
                if (overlay) overlay.classList.toggle("active");
                var icon = toggle.querySelector("i");
                icon.className = sidebar.classList.contains("mobile-open") ? "fas fa-times" : "fas fa-bars";
            });
        }
        if (overlay && sidebar) {
            overlay.addEventListener("click", function () {
                sidebar.classList.remove("mobile-open");
                overlay.classList.remove("active");
            });
        }

        loadMyResults();
    });
})();
