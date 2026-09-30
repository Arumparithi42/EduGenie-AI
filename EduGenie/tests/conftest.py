"""Shared pytest fixtures. Unit tests never call the real Gemini API."""

import pytest
from fastapi.testclient import TestClient

import gemini_client


@pytest.fixture
def fake_gemini(monkeypatch):
    """Replace gemini_client.generate with a controllable fake and record every call."""

    class FakeGemini:
        def __init__(self):
            self.calls = []
            self.reply = "Fake Gemini reply"
            self.error = None

        def __call__(self, prompt, *, json_mode=False, temperature=None):
            self.calls.append({"prompt": prompt, "json_mode": json_mode, "temperature": temperature})
            if self.error:
                raise self.error
            return self.reply

    fake = FakeGemini()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("EXPLAIN_BACKEND", "gemini")
    monkeypatch.setattr(gemini_client, "generate", fake)
    return fake


@pytest.fixture
def client(fake_gemini):
    from main import app

    with TestClient(app) as test_client:
        yield test_client
