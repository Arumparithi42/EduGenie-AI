/* EduGenie frontend: sends the selected task to the FastAPI backend and renders the result. */
(() => {
    "use strict";

    const TASKS = {
        qa: {
            label: "Your question",
            placeholder: "Which is the largest ocean?",
            hint: "Ask any academic or general-knowledge question.",
            button: "Get Answer",
            title: "Answer",
            examples: ["Which is the largest ocean?", "Why is the sky blue?", "What causes the seasons on Earth?"],
        },
        explain: {
            label: "Concept or topic",
            placeholder: "Photosynthesis",
            hint: "Enter a concept to get a simple, student-friendly explanation.",
            button: "Explain",
            title: "Explanation",
            examples: ["Photosynthesis", "Gravity", "Recursion in programming"],
        },
        quiz: {
            label: "Topic or passage",
            placeholder: "The Pythagoras Theorem",
            hint: "Enter a topic or paste a passage to generate multiple-choice questions.",
            button: "Generate Quiz",
            title: "Quiz",
            examples: ["The Pythagoras Theorem", "Solar System", "World War II"],
        },
        summarize: {
            label: "Text to summarize",
            placeholder: "Paste a long paragraph or chapter section here...",
            hint: "Paste long educational content to get a concise revision summary.",
            button: "Summarize",
            title: "Summary",
            examples: [
                "The water cycle describes how water evaporates from the surface of the earth, rises into the atmosphere, cools and condenses into clouds, and falls again to the surface as precipitation. Water falling on land collects in rivers and lakes, soil, and porous layers of rock, and much of it flows back into the oceans, where it will once more evaporate. The cycling of water in and out of the atmosphere is a significant aspect of the weather patterns on Earth.",
            ],
        },
        path: {
            label: "What do you want to learn?",
            placeholder: "SQL",
            hint: "Get a structured beginner-to-advanced plan with timelines and resources.",
            button: "Get Learning Path",
            title: "Learning Path",
            examples: ["SQL", "Machine Learning", "Web Development"],
        },
    };

    const $ = (id) => document.getElementById(id);
    const form = $("taskForm");
    const taskSelect = $("task");
    const input = $("userInput");
    const submitBtn = $("submitBtn");
    const resultCard = $("resultCard");
    const resultEl = $("result");
    const loadingEl = $("loading");
    const sourceBadge = $("sourceBadge");
    let lastPlainText = "";

    // ------------------------------------------------------------------ helpers
    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function inlineMarkdown(text) {
        // `text` is already HTML-escaped.
        return text
            .replace(/`([^`]+)`/g, "<code>$1</code>")
            .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
            .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>")
            .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
            .replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, '$1<a href="$2" target="_blank" rel="noopener">$2</a>');
    }

    /** Minimal, safe Markdown renderer (headings, lists, bold/italic, code, links). */
    function renderMarkdown(md) {
        const lines = escapeHtml(md).split(/\r?\n/);
        const html = [];
        let listType = null;
        let inCode = false;
        let paragraph = [];

        const flushParagraph = () => {
            if (paragraph.length) {
                html.push(`<p>${inlineMarkdown(paragraph.join(" "))}</p>`);
                paragraph = [];
            }
        };
        const closeList = () => {
            if (listType) {
                html.push(`</${listType}>`);
                listType = null;
            }
        };

        for (const rawLine of lines) {
            const line = rawLine.trimEnd();
            if (line.trim().startsWith("```")) {
                flushParagraph();
                closeList();
                html.push(inCode ? "</code></pre>" : "<pre><code>");
                inCode = !inCode;
                continue;
            }
            if (inCode) {
                html.push(line + "\n");
                continue;
            }

            const heading = line.match(/^(#{1,6})\s+(.*)$/);
            const bullet = line.match(/^\s*[-*+]\s+(.*)$/);
            const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);

            if (heading) {
                flushParagraph();
                closeList();
                const level = Math.min(heading[1].length + 1, 6);
                html.push(`<h${level}>${inlineMarkdown(heading[2])}</h${level}>`);
            } else if (bullet || numbered) {
                flushParagraph();
                const type = bullet ? "ul" : "ol";
                if (listType !== type) {
                    closeList();
                    html.push(`<${type}>`);
                    listType = type;
                }
                html.push(`<li>${inlineMarkdown((bullet || numbered)[1])}</li>`);
            } else if (/^\s*(-{3,}|\*{3,})\s*$/.test(line)) {
                flushParagraph();
                closeList();
                html.push("<hr>");
            } else if (line.trim() === "") {
                flushParagraph();
                closeList();
            } else {
                closeList();
                paragraph.push(line.trim());
            }
        }
        if (inCode) html.push("</code></pre>");
        flushParagraph();
        closeList();
        return html.join("\n");
    }

    async function callApi(url, options = {}) {
        const response = await fetch(url, options);
        let data = {};
        try {
            data = await response.json();
        } catch (_) {
            /* non-JSON body */
        }
        if (!response.ok) {
            let message = data.error || data.detail || `Request failed (HTTP ${response.status}).`;
            if (Array.isArray(message)) message = message.map((d) => d.msg).join("; ");
            const err = new Error(message);
            err.status = response.status;
            throw err;
        }
        return data;
    }

    const postJson = (url, body) =>
        callApi(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });

    // ------------------------------------------------------------------ UI state
    function applyTask() {
        const task = TASKS[taskSelect.value];
        $("inputLabel").innerHTML = `<strong>${escapeHtml(task.label)}</strong>`;
        input.placeholder = task.placeholder;
        $("hint").textContent = task.hint;
        submitBtn.textContent = task.button;
        $("quizOptions").classList.toggle("hidden", taskSelect.value !== "quiz");
        $("pathOptions").classList.toggle("hidden", taskSelect.value !== "path");

        const chips = $("examples");
        chips.innerHTML = "";
        task.examples.forEach((example) => {
            const chip = document.createElement("button");
            chip.type = "button";
            chip.className = "chip";
            chip.textContent = example.length > 40 ? example.slice(0, 37) + "…" : example;
            chip.title = example;
            chip.addEventListener("click", () => {
                input.value = example;
                updateCount();
                input.focus();
            });
            chips.appendChild(chip);
        });
    }

    function updateCount() {
        $("charCount").textContent = `${input.value.length} / ${input.maxLength}`;
    }

    let slowTimer = null;

    function setLoading(isLoading) {
        submitBtn.disabled = isLoading;
        loadingEl.classList.toggle("hidden", !isLoading);
        clearTimeout(slowTimer);
        $("loadingText").textContent = "EduGenie is thinking…";
        if (isLoading) {
            resultEl.innerHTML = "";
            sourceBadge.classList.add("hidden");
            // The backend retries automatically when Gemini is overloaded, which can take a while.
            slowTimer = setTimeout(() => {
                $("loadingText").textContent = "Gemini is busy – EduGenie is retrying automatically, please wait…";
            }, 8000);
        }
    }

    function showText(markdown, badge) {
        lastPlainText = markdown;
        resultEl.innerHTML = renderMarkdown(markdown);
        if (badge) {
            sourceBadge.textContent = badge;
            sourceBadge.classList.remove("hidden");
        }
    }

    function showError(message, canRetry = false) {
        lastPlainText = message;
        resultEl.innerHTML = `<div class="error">⚠️ ${escapeHtml(message)}</div>`;
        if (canRetry) {
            const retryBtn = document.createElement("button");
            retryBtn.type = "button";
            retryBtn.className = "secondary small retry-btn";
            retryBtn.textContent = "Try again";
            retryBtn.addEventListener("click", () => form.requestSubmit());
            resultEl.appendChild(retryBtn);
        }
    }

    // ------------------------------------------------------------------ quiz
    function renderQuiz(quiz) {
        let answered = 0;
        let score = 0;
        resultEl.innerHTML = "";
        lastPlainText = quiz
            .map((q, i) => `${i + 1}. ${q.question}\n${q.options.map((o, j) => `   ${"ABCD"[j]}) ${o}`).join("\n")}\nAnswer: ${q.answer}`)
            .join("\n\n");

        const scoreEl = document.createElement("div");
        scoreEl.className = "quiz-score";
        scoreEl.textContent = `Score: 0 / ${quiz.length}`;

        quiz.forEach((q, index) => {
            const block = document.createElement("div");
            block.className = "quiz-question";

            const title = document.createElement("h3");
            title.textContent = `${index + 1}. ${q.question}`;
            block.appendChild(title);

            const feedback = document.createElement("p");
            feedback.className = "quiz-feedback";

            const buttons = q.options.map((option, j) => {
                const btn = document.createElement("button");
                btn.type = "button";
                btn.className = "quiz-option";
                btn.textContent = `${"ABCD"[j]}) ${option}`;
                btn.addEventListener("click", () => {
                    buttons.forEach((b) => (b.disabled = true));
                    const correctIndex = q.options.indexOf(q.answer);
                    buttons[correctIndex].classList.add("correct");
                    answered += 1;
                    if (option === q.answer) {
                        score += 1;
                        feedback.textContent = "✅ Correct!";
                    } else {
                        btn.classList.add("wrong");
                        feedback.textContent = `❌ Not quite. The correct answer is: ${q.answer}`;
                    }
                    if (q.explanation) feedback.textContent += ` — ${q.explanation}`;
                    scoreEl.textContent =
                        `Score: ${score} / ${quiz.length}` + (answered === quiz.length ? " 🎉 Quiz complete!" : "");
                });
                block.appendChild(btn);
                return btn;
            });

            block.appendChild(feedback);
            resultEl.appendChild(block);
        });
        resultEl.appendChild(scoreEl);
    }

    // ------------------------------------------------------------------ submit
    async function handleSubmit(event) {
        event.preventDefault();
        const task = taskSelect.value;
        const value = input.value.trim();
        if (!value) {
            input.focus();
            input.reportValidity();
            return;
        }

        resultCard.classList.remove("hidden");
        $("resultTitle").textContent = TASKS[task].title;
        setLoading(true);

        try {
            if (task === "qa") {
                const data = await callApi(`/qa?question=${encodeURIComponent(value)}`);
                showText(data.answer, "Gemini");
            } else if (task === "explain") {
                const data = await postJson("/explain", { topic: value });
                showText(data.explanation, data.source === "local" ? "LaMini-Flan-T5 (local)" : "Gemini");
            } else if (task === "quiz") {
                const data = await postJson("/quiz", { text: value, num_questions: Number($("numQuestions").value) });
                renderQuiz(data.quiz);
                sourceBadge.textContent = "Gemini";
                sourceBadge.classList.remove("hidden");
            } else if (task === "summarize") {
                const data = await postJson("/summarize", { text: value });
                showText(data.summary, "Gemini");
            } else if (task === "path") {
                const params = new URLSearchParams({ topic: value, level: $("level").value });
                const data = await callApi(`/learn/recommendations?${params}`);
                showText(data.recommendation, "Gemini");
            }
        } catch (err) {
            // 502/503/504 (AI busy or failed) and network errors are worth retrying; 4xx input errors are not.
            const canRetry = !err.status || err.status >= 500;
            showError(err.message || "Something went wrong. Please try again.", canRetry);
        } finally {
            setLoading(false);
            resultCard.scrollIntoView({ behavior: "smooth", block: "start" });
        }
    }

    async function checkHealth() {
        const status = $("status");
        try {
            const data = await callApi("/health");
            if (data.gemini_configured) {
                status.textContent = `Connected · ${data.gemini_model}`;
                status.className = "status status-ok";
            } else {
                status.textContent = "Gemini API key missing – add GEMINI_API_KEY to EduGenie/.env";
                status.className = "status status-error";
            }
        } catch (_) {
            status.textContent = "Backend not reachable";
            status.className = "status status-error";
        }
    }

    // ------------------------------------------------------------------ wiring
    taskSelect.addEventListener("change", applyTask);
    input.addEventListener("input", updateCount);
    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) form.requestSubmit();
    });
    form.addEventListener("submit", handleSubmit);
    $("clearBtn").addEventListener("click", () => {
        input.value = "";
        updateCount();
        resultCard.classList.add("hidden");
        input.focus();
    });
    $("copyBtn").addEventListener("click", async () => {
        try {
            await navigator.clipboard.writeText(lastPlainText);
            $("copyBtn").textContent = "Copied!";
        } catch (_) {
            $("copyBtn").textContent = "Copy failed";
        }
        setTimeout(() => ($("copyBtn").textContent = "Copy"), 1500);
    });

    applyTask();
    updateCount();
    checkHealth();
})();
