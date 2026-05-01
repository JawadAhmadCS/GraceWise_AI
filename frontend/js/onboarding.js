document.addEventListener('DOMContentLoaded', async function () {
    if (typeof auth !== 'undefined' && !auth.isLoggedIn()) {
        window.location.href = 'sign_in.html';
        return;
    }

    const apiBase = window.API_BASE_URL;

    const chatMessagesEl = document.getElementById('chatMessages');
    const chatForm = document.getElementById('chatForm');
    const chatInput = document.getElementById('chatInput');
    const sendBtn = document.getElementById('sendBtn');
    const voiceBtn = document.getElementById('voiceBtn');

    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');

    const sectionSelect = document.getElementById('sectionSelect');
    const sectionForm = document.getElementById('sectionForm');
    const saveSectionBtn = document.getElementById('saveSectionBtn');
    const refreshProfileBtn = document.getElementById('refreshProfileBtn');
    const statusText = document.getElementById('statusText');

    let currentQuestion = null;
    let questionBank = null;
    let profileData = null;

    function token() {
        return localStorage.getItem('access_token') || localStorage.getItem('token');
    }

    function authHeaders() {
        return {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token()}`,
        };
    }

    function setStatus(message, isGood) {
        statusText.textContent = message || '';
        statusText.className = isGood == null ? 'status-text' : (isGood ? 'status-text good' : 'status-text bad');
    }

    function addMessage(role, text) {
        const div = document.createElement('div');
        div.className = `message ${role}`;
        div.textContent = text;
        chatMessagesEl.appendChild(div);
        chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
    }

    function updateProgress(progress) {
        const overall = progress?.overall || {};
        const percent = Number(overall.percent || 0);
        progressFill.style.width = `${percent}%`;
        progressText.textContent = `Progress: ${percent}% (${overall.required_completed || 0}/${overall.required_total || 0} required)`;
    }

    function getSectionTitle(sectionKey) {
        const found = (questionBank?.sections || []).find((s) => s.key === sectionKey);
        return found?.title || sectionKey;
    }

    function buildField(question, value) {
        const wrap = document.createElement('div');
        wrap.className = 'field-row';

        const label = document.createElement('label');
        label.textContent = question.prompt || question.field;
        label.setAttribute('for', `field_${question.field}`);
        wrap.appendChild(label);

        const qType = (question.type || 'text').toLowerCase();
        let input;

        if (qType === 'single_select') {
            input = document.createElement('select');
            const blank = document.createElement('option');
            blank.value = '';
            blank.textContent = 'Select one';
            input.appendChild(blank);

            (question.options || []).forEach((opt) => {
                const option = document.createElement('option');
                if (typeof opt === 'object') {
                    option.value = String(opt.value || '');
                    option.textContent = String(opt.label || opt.value || '');
                } else {
                    option.value = String(opt);
                    option.textContent = String(opt);
                }
                input.appendChild(option);
            });
            input.value = value == null ? '' : String(value);
        } else if (qType === 'boolean') {
            input = document.createElement('select');
            [
                { value: '', label: 'Select one' },
                { value: 'true', label: 'Yes' },
                { value: 'false', label: 'No' },
            ].forEach((opt) => {
                const option = document.createElement('option');
                option.value = opt.value;
                option.textContent = opt.label;
                input.appendChild(option);
            });
            if (value === true) input.value = 'true';
            else if (value === false) input.value = 'false';
            else input.value = '';
        } else if (qType === 'number') {
            input = document.createElement('input');
            input.type = 'number';
            input.value = value == null ? '' : String(value);
        } else {
            input = document.createElement('textarea');
            input.rows = 2;
            input.value = value == null ? '' : String(value);
        }

        input.id = `field_${question.field}`;
        input.dataset.field = question.field;
        input.dataset.type = qType;
        wrap.appendChild(input);
        return wrap;
    }

    function getSectionQuestions(sectionKey) {
        return (questionBank?.questions || []).filter((q) => q.section === sectionKey);
    }

    function getSectionData(sectionKey) {
        return profileData?.profile?.[sectionKey] || {};
    }

    function renderSectionEditor(sectionKey) {
        sectionForm.innerHTML = '';
        const questions = getSectionQuestions(sectionKey);
        const sectionData = getSectionData(sectionKey);

        if (questions.length === 0) {
            sectionForm.innerHTML = '<p>No fields configured for this section yet.</p>';
            return;
        }

        questions.forEach((q) => {
            sectionForm.appendChild(buildField(q, sectionData[q.field]));
        });
    }

    function parseInputValue(el) {
        const qType = (el.dataset.type || 'text').toLowerCase();
        const raw = el.value;

        if (qType === 'number') {
            if (raw === '') return null;
            return Number(raw);
        }
        if (qType === 'boolean') {
            if (raw === '') return null;
            return raw === 'true';
        }
        return raw;
    }

    async function fetchQuestionBank() {
        const res = await fetch(`${apiBase}/onboarding/v2/question-bank`, { headers: authHeaders() });
        const data = await res.json();
        if (!res.ok) throw new Error(data.message || 'Could not load question bank');
        questionBank = data;
    }

    async function fetchProfile() {
        const res = await fetch(`${apiBase}/onboarding/v2/profile`, { headers: authHeaders() });
        const data = await res.json();
        if (!res.ok) throw new Error(data.message || 'Could not load profile');
        profileData = data;
    }

    function initSectionSelect() {
        sectionSelect.innerHTML = '';
        (questionBank?.sections || []).forEach((section) => {
            const opt = document.createElement('option');
            opt.value = section.key;
            opt.textContent = section.title;
            sectionSelect.appendChild(opt);
        });
        if (sectionSelect.value) {
            renderSectionEditor(sectionSelect.value);
        }
    }

    async function startSession() {
        const res = await fetch(`${apiBase}/onboarding/v2/session/start`, {
            method: 'POST',
            headers: authHeaders(),
        });
        const data = await res.json();

        if (!res.ok) {
            throw new Error(data.message || 'Could not start onboarding session');
        }

        currentQuestion = data.current_question || null;
        updateProgress(data.progress);
        addMessage('ai', data.assistant_message || 'Let us begin.');
    }

    async function sendAnswer(answerText, answerSource) {
        const payload = {
            message: answerText,
            answer_source: answerSource || 'text',
            question_id: currentQuestion?.id || undefined,
        };

        const res = await fetch(`${apiBase}/onboarding/v2/session/message`, {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify(payload),
        });
        const data = await res.json();

        if (!res.ok) {
            throw new Error(data.message || 'Could not save answer');
        }

        currentQuestion = data.current_question || null;
        updateProgress(data.progress);
        addMessage('ai', data.assistant_message || 'Saved.');

        await fetchProfile();
        renderSectionEditor(sectionSelect.value);
    }

    chatForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        const text = chatInput.value.trim();
        if (!text) return;

        sendBtn.disabled = true;
        addMessage('user', text);
        chatInput.value = '';

        try {
            await sendAnswer(text, 'text');
            setStatus('Answer saved.', true);
        } catch (error) {
            setStatus(error.message || 'Could not send answer.', false);
        } finally {
            sendBtn.disabled = false;
            chatInput.focus();
        }
    });

    sectionSelect.addEventListener('change', function () {
        renderSectionEditor(sectionSelect.value);
    });

    saveSectionBtn.addEventListener('click', async function () {
        const sectionKey = sectionSelect.value;
        if (!sectionKey) return;

        const values = {};
        Array.from(sectionForm.querySelectorAll('[data-field]')).forEach((el) => {
            values[el.dataset.field] = parseInputValue(el);
        });

        saveSectionBtn.disabled = true;
        setStatus('Saving section...', null);

        try {
            const res = await fetch(`${apiBase}/onboarding/v2/profile/section/${encodeURIComponent(sectionKey)}`, {
                method: 'PATCH',
                headers: authHeaders(),
                body: JSON.stringify({ data: values }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.message || 'Could not save section');

            profileData = { profile: data.profile };
            setStatus(`${getSectionTitle(sectionKey)} updated.`, true);
        } catch (error) {
            setStatus(error.message || 'Could not save section.', false);
        } finally {
            saveSectionBtn.disabled = false;
        }
    });

    refreshProfileBtn.addEventListener('click', async function () {
        try {
            await fetchProfile();
            renderSectionEditor(sectionSelect.value);
            setStatus('Profile refreshed.', true);
        } catch (error) {
            setStatus(error.message || 'Could not refresh profile.', false);
        }
    });

    function initVoiceInput() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) {
            voiceBtn.disabled = true;
            voiceBtn.title = 'Voice input not supported in this browser';
            return;
        }

        const recognition = new SpeechRecognition();
        recognition.lang = 'en-US';
        recognition.interimResults = false;

        recognition.onstart = function () {
            voiceBtn.textContent = 'Listening...';
            voiceBtn.disabled = true;
        };

        recognition.onresult = function (event) {
            const transcript = event.results?.[0]?.[0]?.transcript || '';
            if (transcript) {
                chatInput.value = transcript;
                addMessage('user', transcript);
                sendBtn.disabled = true;
                sendAnswer(transcript, 'voice')
                    .then(() => setStatus('Voice answer saved.', true))
                    .catch((error) => setStatus(error.message || 'Could not send voice answer.', false))
                    .finally(() => {
                        sendBtn.disabled = false;
                        chatInput.value = '';
                    });
            }
        };

        recognition.onerror = function () {
            setStatus('Voice input failed. Please type your answer.', false);
        };

        recognition.onend = function () {
            voiceBtn.textContent = 'Voice';
            voiceBtn.disabled = false;
        };

        voiceBtn.addEventListener('click', function () {
            recognition.start();
        });
    }

    try {
        await fetchQuestionBank();
        await fetchProfile();
        initSectionSelect();
        initVoiceInput();
        await startSession();
        setStatus('Onboarding ready.', true);
    } catch (error) {
        setStatus(error.message || 'Could not initialize onboarding.', false);
        if ((error.message || '').toLowerCase().includes('subscription')) {
            setTimeout(() => {
                window.location.href = 'premium-plan.html';
            }, 1200);
        }
    }
});
