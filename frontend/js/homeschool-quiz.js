(function () {
    const apiBaseUrl = (window.API_BASE_URL || "").replace(/\/+$/, "");
    const quizContainer = document.getElementById("quiz-container");
    const emailGate = document.getElementById("email-gate");
    const quizForm = document.getElementById("homeschool-quiz-form");
    const emailForm = document.getElementById("email-capture-form");
    const statusBox = document.getElementById("status-box");
    const quizTitle = document.getElementById("quiz-title");
    const quizDescription = document.getElementById("quiz-description");

    let quizData = null;
    let submissionToken = null;

    function getUrlMetadata() {
        const params = new URLSearchParams(window.location.search);
        return {
            utm_source: params.get("utm_source") || "instagram",
            utm_medium: params.get("utm_medium") || "bio",
            utm_campaign: params.get("utm_campaign") || "homeschool_style_quiz",
        };
    }

    function setStatus(message, type) {
        statusBox.textContent = message;
        statusBox.className = `status-box ${type || "info"}`;
    }

    async function loadQuiz() {
        try {
            const response = await fetch(`${apiBaseUrl}/quiz/homeschool-style/questions`);
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.message || "Unable to load quiz.");
            }

            quizData = data;
            quizTitle.textContent = data.title;
            quizDescription.textContent = data.description;
            renderQuestions(data.questions || []);
        } catch (error) {
            setStatus(error.message || "Unable to load quiz right now.", "error");
        }
    }

    function renderQuestions(questions) {
        quizContainer.innerHTML = questions
            .map((question, index) => {
                const optionsHtml = (question.options || [])
                    .map(
                        (opt) => `
                            <label class="option-card" for="${opt.key}">
                                <input id="${opt.key}" type="radio" name="${question.id}" value="${opt.key}" required>
                                <span>${opt.text}</span>
                            </label>
                        `,
                    )
                    .join("");

                return `
                    <section class="question-card">
                        <p class="question-step">Question ${index + 1} of ${questions.length}</p>
                        <h3>${question.question}</h3>
                        <div class="options-grid">${optionsHtml}</div>
                    </section>
                `;
            })
            .join("");
    }

    quizForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!quizData) {
            return;
        }

        const submitButton = quizForm.querySelector("button[type='submit']");
        submitButton.disabled = true;
        setStatus("Scoring your responses...", "info");

        try {
            const answers = {};
            (quizData.questions || []).forEach((question) => {
                const selected = quizForm.querySelector(`input[name='${question.id}']:checked`);
                answers[question.id] = selected ? selected.value : "";
            });

            const response = await fetch(`${apiBaseUrl}/quiz/homeschool-style/submit`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    answers,
                    metadata: getUrlMetadata(),
                }),
            });

            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.message || "Could not submit quiz.");
            }

            submissionToken = data.submission_token;
            document.getElementById("quiz-step").style.display = "none";
            emailGate.style.display = "block";
            setStatus("Almost there. Enter your email to see your personalized result.", "success");
        } catch (error) {
            setStatus(error.message || "Could not submit quiz.", "error");
        } finally {
            submitButton.disabled = false;
        }
    });

    emailForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!submissionToken) {
            setStatus("Please complete the quiz first.", "error");
            return;
        }

        const emailInput = document.getElementById("lead-email");
        const submitButton = emailForm.querySelector("button[type='submit']");
        submitButton.disabled = true;
        setStatus("Sending your results...", "info");

        try {
            const response = await fetch(`${apiBaseUrl}/quiz/homeschool-style/capture-lead`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    submission_token: submissionToken,
                    email: emailInput.value.trim(),
                    metadata: getUrlMetadata(),
                }),
            });

            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.message || "Could not send result.");
            }

            window.location.href = data.redirect_url;
        } catch (error) {
            setStatus(error.message || "Could not send result.", "error");
            submitButton.disabled = false;
        }
    });

    loadQuiz();
})();
