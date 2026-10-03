"""Shared Google Gemini client used by every EduGenie module.

Configuration comes from environment variables (or a local `.env` file):

    GEMINI_API_KEY   Your key from https://aistudio.google.com/app/apikey
                     (GOOGLE_API_KEY is accepted as an alternative name)
    GEMINI_MODEL     Gemini model to call (default: gemini-flash-latest)
    GEMINI_FALLBACK_MODELS
                     Comma-separated backup models tried when the main model is
                     overloaded (default: gemini-flash-latest,gemini-flash-lite-latest;
                     set to "none" to disable)
    GEMINI_MAX_RETRIES
                     Retries per model for temporary errors such as 503 "high demand"
                     or 429 rate limits (default: 2)
"""

from __future__ import annotations

import logging
import os
import random
import time
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Load EduGenie/.env regardless of the directory the server is started from.
load_dotenv(Path(__file__).resolve().parent / ".env")

logger = logging.getLogger("edugenie.gemini")

DEFAULT_MODEL = "gemini-flash-latest"
DEFAULT_FALLBACK_MODELS = "gemini-flash-latest,gemini-flash-lite-latest"
DEFAULT_MAX_RETRIES = 2
RETRY_BASE_DELAY = 2.0  # seconds; doubles on each retry (2 s, 4 s, ...) plus jitter

# HTTP status codes that mean "temporary problem - try again" (overloaded, rate limited, server error).
RETRYABLE_CODES = {429, 500, 502, 503, 504}

# Indirection so tests can skip the real waiting.
_sleep = time.sleep


class GeminiError(RuntimeError):
    """Raised when Gemini cannot produce a usable response."""


class GeminiNotConfiguredError(GeminiError):
    """Raised when no API key has been configured."""


class GeminiBusyError(GeminiError):
    """Raised when Gemini stays overloaded / rate limited after all retries and fallbacks."""


def get_api_key() -> str | None:
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if key and key.strip() and key.strip() != "your_gemini_api_key_here":
        return key.strip()
    return None


def get_model_name() -> str:
    return os.getenv("GEMINI_MODEL", "").strip() or DEFAULT_MODEL


def get_fallback_models() -> list[str]:
    """Backup models to try after the main model, without duplicates or the main model itself."""
    raw = os.getenv("GEMINI_FALLBACK_MODELS", DEFAULT_FALLBACK_MODELS).strip()
    if raw.lower() in {"", "none", "off", "false"}:
        return []
    primary = get_model_name()
    models: list[str] = []
    for name in (m.strip() for m in raw.split(",")):
        if name and name != primary and name not in models:
            models.append(name)
    return models


def get_max_retries() -> int:
    try:
        return max(0, min(int(os.getenv("GEMINI_MAX_RETRIES", DEFAULT_MAX_RETRIES)), 5))
    except ValueError:
        return DEFAULT_MAX_RETRIES


def is_configured() -> bool:
    return get_api_key() is not None


@lru_cache(maxsize=1)
def _client(api_key: str):
    # Imported lazily so the app (and the test-suite) can start without the SDK being used.
    from google import genai

    return genai.Client(api_key=api_key)


def generate(prompt: str, *, json_mode: bool = False, temperature: float | None = None) -> str:
    """Send `prompt` to Gemini and return the response text.

    `json_mode=True` asks Gemini to reply with raw JSON (no Markdown).
    Temporary errors (503 "high demand", 429 rate limits, 5xx, network errors) are retried
    with exponential backoff, then the fallback models are tried in order.
    Raises GeminiNotConfiguredError / GeminiBusyError / GeminiError on failure.
    """
    api_key = get_api_key()
    if api_key is None:
        raise GeminiNotConfiguredError(
            "Gemini API key is not configured. Copy EduGenie/.env.example to "
            "EduGenie/.env and set GEMINI_API_KEY, then restart the server."
        )

    from google.genai import types

    config = types.GenerateContentConfig(
        temperature=temperature,
        response_mime_type="application/json" if json_mode else None,
    )

    primary = get_model_name()
    models = [primary] + get_fallback_models()
    retries = get_max_retries()
    last_exc: Exception | None = None

    for model in models:
        for attempt in range(retries + 1):
            try:
                response = _client(api_key).models.generate_content(model=model, contents=prompt, config=config)
            except Exception as exc:  # network errors, invalid key, quota, overload, unknown model ...
                last_exc = exc
                code = _error_code(exc)
                if _is_retryable(exc):
                    if attempt < retries:
                        delay = RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1)
                        logger.warning("Gemini %s busy (%s); retry %d/%d in %.1fs", model, code or exc, attempt + 1, retries, delay)
                        _sleep(delay)
                        continue
                    logger.warning("Gemini %s still busy after %d retries", model, retries)
                    break  # try the next (fallback) model
                if code == 404:  # model name not available for this key - try the next model
                    logger.warning("Gemini model %s not found; trying the next model", model)
                    break
                # Not temporary (invalid API key, bad request, ...): retrying will not help.
                logger.error("Gemini request failed: %s", exc)
                raise GeminiError(f"Gemini request failed: {_error_message(exc)}") from exc

            if model != primary:
                logger.warning("Answered with fallback model %s because %s was unavailable", model, primary)
            text = _extract_text(response)
            if not text:
                raise GeminiError(
                    "Gemini returned an empty response (it may have been blocked by safety filters). "
                    "Try rephrasing your input."
                )
            return text.strip()

    if last_exc is not None and _error_code(last_exc) == 404:
        raise GeminiError(
            f"Gemini model '{primary}' was not found for this API key. Set GEMINI_MODEL in "
            f"EduGenie/.env to a model listed in Google AI Studio. ({_error_message(last_exc)})"
        ) from last_exc
    tried = ", ".join(models)
    raise GeminiBusyError(
        "Gemini is very busy right now (high demand or rate limit). EduGenie retried automatically "
        f"and also tried the backup models ({tried}). Please wait a minute and try again. "
        f"Details: {_error_message(last_exc)}"
    ) from last_exc


def _error_code(exc: Exception) -> int | None:
    """HTTP status code of a google-genai APIError (None for other errors)."""
    code = getattr(exc, "code", None)
    return code if isinstance(code, int) else None


def _is_retryable(exc: Exception) -> bool:
    if _error_code(exc) in RETRYABLE_CODES:
        return True
    try:
        import httpx

        return isinstance(exc, (httpx.TimeoutException, httpx.NetworkError))
    except ImportError:  # pragma: no cover
        return False


def _error_message(exc: Exception | None) -> str:
    # google-genai APIError exposes a short human-readable `.message`.
    return (getattr(exc, "message", None) or str(exc)) if exc is not None else "unknown error"


def _extract_text(response) -> str:
    """Return the text of a Gemini response, tolerating unusual response shapes."""
    try:
        text = response.text
    except Exception:  # .text raises on some blocked/multi-part responses
        text = None
    if text:
        return text

    parts: list[str] = []
    for candidate in getattr(response, "candidates", None) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", None) or []:
            if getattr(part, "text", None):
                parts.append(part.text)
    return "".join(parts)
