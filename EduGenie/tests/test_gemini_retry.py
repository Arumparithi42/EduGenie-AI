"""Retry / fallback behaviour of gemini_client.generate() using the SDK's real error types."""

import pytest
from fastapi.testclient import TestClient
from google.genai import errors

import gemini_client


def api_error(code, status, message):
    return errors.APIError(code, {"error": {"code": code, "status": status, "message": message}})


BUSY = lambda: api_error(503, "UNAVAILABLE", "This model is currently experiencing high demand.")  # noqa: E731
RATE_LIMITED = lambda: api_error(429, "RESOURCE_EXHAUSTED", "Quota exceeded.")  # noqa: E731


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeModels:
    """Plays back a script of outcomes (exception or text) per model name."""

    def __init__(self, script):
        self.script = {model: list(outcomes) for model, outcomes in script.items()}
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append(model)
        outcome = self.script[model].pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return FakeResponse(outcome)


@pytest.fixture
def fake_sdk(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "gemini-flash-latest,gemini-flash-lite-latest")
    monkeypatch.setenv("GEMINI_MAX_RETRIES", "2")
    sleeps = []
    monkeypatch.setattr(gemini_client, "_sleep", sleeps.append)

    def install(script):
        models = FakeModels(script)

        class FakeClient:
            pass

        client = FakeClient()
        client.models = models
        monkeypatch.setattr(gemini_client, "_client", lambda api_key: client)
        return models, sleeps

    return install


def test_retries_busy_model_then_succeeds(fake_sdk):
    models, sleeps = fake_sdk({"gemini-3.5-flash": [BUSY(), BUSY(), "Pacific Ocean"]})
    assert gemini_client.generate("q") == "Pacific Ocean"
    assert models.calls == ["gemini-3.5-flash"] * 3
    assert len(sleeps) == 2 and sleeps[1] > sleeps[0]  # exponential backoff


def test_falls_back_to_next_model_when_primary_stays_busy(fake_sdk):
    models, _ = fake_sdk({"gemini-3.5-flash": [BUSY(), BUSY(), BUSY()], "gemini-flash-latest": ["From fallback"]})
    assert gemini_client.generate("q") == "From fallback"
    assert models.calls == ["gemini-3.5-flash"] * 3 + ["gemini-flash-latest"]


def test_rate_limit_is_retried(fake_sdk):
    models, _ = fake_sdk({"gemini-3.5-flash": [RATE_LIMITED(), "ok"]})
    assert gemini_client.generate("q") == "ok"
    assert len(models.calls) == 2


def test_all_models_busy_raises_busy_error(fake_sdk):
    models, _ = fake_sdk({m: [BUSY()] * 3 for m in ["gemini-3.5-flash", "gemini-flash-latest", "gemini-flash-lite-latest"]})
    with pytest.raises(gemini_client.GeminiBusyError) as info:
        gemini_client.generate("q")
    assert "high demand" in str(info.value)
    assert len(models.calls) == 9


def test_invalid_key_is_not_retried(fake_sdk):
    models, sleeps = fake_sdk({"gemini-3.5-flash": [api_error(400, "INVALID_ARGUMENT", "API key not valid.")]})
    with pytest.raises(gemini_client.GeminiError) as info:
        gemini_client.generate("q")
    assert not isinstance(info.value, gemini_client.GeminiBusyError)
    assert "API key not valid" in str(info.value)
    assert models.calls == ["gemini-3.5-flash"] and sleeps == []


def test_unknown_model_moves_to_fallback_without_retry(fake_sdk):
    models, sleeps = fake_sdk({"gemini-3.5-flash": [api_error(404, "NOT_FOUND", "model not found")], "gemini-flash-latest": ["ok"]})
    assert gemini_client.generate("q") == "ok"
    assert models.calls == ["gemini-3.5-flash", "gemini-flash-latest"] and sleeps == []


def test_fallback_can_be_disabled(fake_sdk, monkeypatch):
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "none")
    monkeypatch.setenv("GEMINI_MAX_RETRIES", "0")
    models, _ = fake_sdk({"gemini-3.5-flash": [BUSY()]})
    with pytest.raises(gemini_client.GeminiBusyError):
        gemini_client.generate("q")
    assert models.calls == ["gemini-3.5-flash"]


def test_fallback_list_skips_primary_and_duplicates(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-flash-latest")
    monkeypatch.setenv("GEMINI_FALLBACK_MODELS", "gemini-flash-latest, gemini-flash-lite-latest,gemini-flash-lite-latest")
    assert gemini_client.get_fallback_models() == ["gemini-flash-lite-latest"]


def test_busy_error_returns_503_with_retry_after(fake_sdk, monkeypatch):
    monkeypatch.setenv("EXPLAIN_BACKEND", "gemini")
    fake_sdk({m: [BUSY()] * 3 for m in ["gemini-3.5-flash", "gemini-flash-latest", "gemini-flash-lite-latest"]})
    from main import app

    with TestClient(app) as client:
        response = client.post("/quiz", json={"text": "The Pythagoras Theorem"})
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "60"
    assert "busy" in response.json()["error"]
