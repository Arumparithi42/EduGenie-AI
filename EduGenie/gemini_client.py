"""Shared Google Gemini client used by every EduGenie module.

Configuration comes from environment variables (or a local `.env` file):

    GEMINI_API_KEY   Your key from https://aistudio.google.com/app/apikey
                     (GOOGLE_API_KEY is accepted as an alternative name)
    GEMINI_MODEL     Gemini model to call (default: gemini-flash-latest)
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Load EduGenie/.env regardless of the directory the server is started from.
load_dotenv(Path(__file__).resolve().parent / ".env")

logger = logging.getLogger("edugenie.gemini")

DEFAULT_MODEL = "gemini-flash-latest"


class GeminiError(RuntimeError):
    """Raised when Gemini cannot produce a usable response."""


class GeminiNotConfiguredError(GeminiError):
    """Raised when no API key has been configured."""


def get_api_key() -> str | None:
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if key and key.strip() and key.strip() != "your_gemini_api_key_here":
        return key.strip()
    return None


def get_model_name() -> str:
    return os.getenv("GEMINI_MODEL", "").strip() or DEFAULT_MODEL


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
    Raises GeminiNotConfiguredError / GeminiError on failure.
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

    try:
        response = _client(api_key).models.generate_content(
            model=get_model_name(),
            contents=prompt,
            config=config,
        )
    except Exception as exc:  # network errors, invalid key, quota, unknown model ...
        logger.error("Gemini request failed: %s", exc)
        # google-genai APIError exposes a short human-readable `.message`.
        message = getattr(exc, "message", None) or str(exc)
        raise GeminiError(f"Gemini request failed: {message}") from exc

    text = _extract_text(response)
    if not text:
        raise GeminiError(
            "Gemini returned an empty response (it may have been blocked by safety filters). "
            "Try rephrasing your input."
        )
    return text.strip()


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
