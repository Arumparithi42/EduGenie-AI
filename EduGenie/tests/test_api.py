"""End-to-end tests of the FastAPI endpoints (Gemini is faked)."""

import json

import gemini_client


def test_index_page_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Welcome to EduGenie" in response.text
    assert "/static/script.js" in response.text


def test_static_files_served(client):
    assert client.get("/static/style.css").status_code == 200
    assert client.get("/static/script.js").status_code == 200


def test_health(client):
    data = client.get("/health").json()
    assert data["status"] == "ok"
    assert data["gemini_configured"] is True
    assert data["explain_backend"] == "gemini"


# ------------------------------------------------------------------ Q&A
def test_qa(client, fake_gemini):
    fake_gemini.reply = "The Pacific Ocean is the largest ocean."
    response = client.get("/qa", params={"question": "Which is the largest ocean?"})
    assert response.status_code == 200
    assert response.json()["answer"] == "The Pacific Ocean is the largest ocean."
    assert "Which is the largest ocean?" in fake_gemini.calls[0]["prompt"]


def test_qa_requires_question(client):
    assert client.get("/qa").status_code == 422
    response = client.get("/qa", params={"question": "   "})
    assert response.status_code == 400
    assert "error" in response.json()


# ------------------------------------------------------------------ Explain
def test_explain(client, fake_gemini):
    fake_gemini.reply = "Plants make food from sunlight."
    response = client.post("/explain", json={"topic": "Photosynthesis"})
    assert response.status_code == 200
    data = response.json()
    assert data == {"topic": "Photosynthesis", "explanation": "Plants make food from sunlight.", "source": "gemini"}


def test_explain_trailing_slash_like_original_doc(client):
    response = client.post("/explain/", json={"topic": "Gravity"})
    assert response.status_code == 200
    assert response.json()["topic"] == "Gravity"


def test_explain_empty_topic(client):
    response = client.post("/explain", json={"topic": ""})
    assert response.status_code == 400
    assert response.json() == {"error": "Please provide a topic."}


def test_explain_topic_too_long(client):
    response = client.post("/explain", json={"topic": "x" * 1000})
    assert response.status_code == 400


# ------------------------------------------------------------------ Summarize
def test_summarize(client, fake_gemini):
    fake_gemini.reply = "Short summary."
    response = client.post("/summarize", json={"text": "A very long passage about rivers."})
    assert response.status_code == 200
    assert response.json() == {"summary": "Short summary."}


def test_summarize_empty(client):
    response = client.post("/summarize", json={"text": ""})
    assert response.status_code == 400


# ------------------------------------------------------------------ Quiz
QUIZ = [
    {"question": "What is 2+2?", "options": ["3", "4", "5", "6"], "answer": "4", "explanation": "Basic addition."},
    {"question": "Capital of France?", "options": ["Paris", "Rome", "Berlin", "Madrid"], "answer": "Paris"},
    {"question": "H2O is?", "options": ["Salt", "Water", "Air", "Gold"], "answer": "B"},
]


def test_quiz(client, fake_gemini):
    fake_gemini.reply = "```json\n" + json.dumps(QUIZ) + "\n```"
    response = client.post("/quiz", json={"text": "The Pythagoras Theorem"})
    assert response.status_code == 200
    quiz = response.json()["quiz"]
    assert len(quiz) == 3
    assert quiz[2]["answer"] == "Water"  # letter answer mapped to option text
    assert all(len(q["options"]) == 4 and q["answer"] in q["options"] for q in quiz)
    assert fake_gemini.calls[0]["json_mode"] is True


def test_quiz_num_questions(client, fake_gemini):
    fake_gemini.reply = json.dumps(QUIZ)
    response = client.post("/quiz", json={"text": "Math", "num_questions": 2})
    assert len(response.json()["quiz"]) == 2
    assert "create 2 multiple-choice" in fake_gemini.calls[0]["prompt"]


def test_quiz_invalid_num_questions(client):
    assert client.post("/quiz", json={"text": "Math", "num_questions": 50}).status_code == 422


def test_quiz_invalid_ai_output(client, fake_gemini):
    fake_gemini.reply = "Sorry, I cannot do that."
    response = client.post("/quiz", json={"text": "Solar System"})
    assert response.status_code == 502
    assert "error" in response.json()


def test_quiz_empty(client):
    response = client.post("/quiz", json={"text": " "})
    assert response.status_code == 400


# ------------------------------------------------------------------ Learning path
def test_learning_recommendations(client, fake_gemini):
    fake_gemini.reply = "## Beginner\n- SELECT basics"
    response = client.get("/learn/recommendations", params={"topic": "SQL", "level": "intermediate"})
    assert response.status_code == 200
    data = response.json()
    assert data["topic"] == "SQL"
    assert data["recommendation"].startswith("## Beginner")
    assert "intermediate" in fake_gemini.calls[0]["prompt"]


def test_learning_recommendations_requires_topic(client):
    assert client.get("/learn/recommendations").status_code == 422


# ------------------------------------------------------------------ Errors
def test_gemini_failure_returns_502(client, fake_gemini):
    fake_gemini.error = gemini_client.GeminiError("Gemini request failed: quota exceeded")
    response = client.get("/qa", params={"question": "Hi?"})
    assert response.status_code == 502
    assert "quota exceeded" in response.json()["error"]


def test_missing_api_key_returns_503(client, fake_gemini):
    fake_gemini.error = gemini_client.GeminiNotConfiguredError("Gemini API key is not configured.")
    response = client.post("/summarize", json={"text": "Some text"})
    assert response.status_code == 503
