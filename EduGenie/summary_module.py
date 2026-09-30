"""Summarization module (Gemini)."""

from __future__ import annotations

import gemini_client

SUMMARY_PROMPT = """Summarize the following educational text in simple language for quick revision.
- Start with a one-sentence overview.
- Then list the key points as short bullet points.
- Keep all important facts, remove repetition, and do not add information that is not in the text.

Text:
\"\"\"
{text}
\"\"\"
"""


def summarize_text(text: str) -> str:
    """Return a concise summary of `text`. Raises gemini_client.GeminiError on failure."""
    return gemini_client.generate(SUMMARY_PROMPT.format(text=text.strip()), temperature=0.2)
