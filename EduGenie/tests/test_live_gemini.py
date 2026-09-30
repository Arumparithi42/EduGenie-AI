"""Optional smoke tests against the REAL Gemini API.

Skipped by default. Run them after configuring EduGenie/.env:
    Windows (PowerShell):  $env:RUN_LIVE_TESTS="1"; pytest -m live -v
    macOS / Linux:         RUN_LIVE_TESTS=1 pytest -m live -v
"""

import os

import pytest
from fastapi.testclient import TestClient

import gemini_client

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(os.getenv("RUN_LIVE_TESTS") != "1", reason="set RUN_LIVE_TESTS=1 to call the real Gemini API"),
]


@pytest.fixture(scope="module")
def live_client():
    if not gemini_client.is_configured():
        pytest.skip("GEMINI_API_KEY is not configured")
    from main import app

    with TestClient(app) as c:
        yield c


def test_live_qa(live_client):
    response = live_client.get("/qa", params={"question": "Which is the largest ocean?"})
    assert response.status_code == 200, response.text
    assert "pacific" in response.json()["answer"].lower()


def test_live_quiz(live_client):
    response = live_client.post("/quiz", json={"text": "The Pythagoras Theorem"})
    assert response.status_code == 200, response.text
    quiz = response.json()["quiz"]
    assert 1 <= len(quiz) <= 3
    assert all(q["answer"] in q["options"] for q in quiz)


def test_live_learning_path(live_client):
    response = live_client.get("/learn/recommendations", params={"topic": "SQL"})
    assert response.status_code == 200, response.text
    assert len(response.json()["recommendation"]) > 100
