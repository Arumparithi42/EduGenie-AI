"""Question answering module (Gemini)."""

from __future__ import annotations

import gemini_client

QNA_PROMPT = """You are EduGenie, a friendly and accurate AI tutor for students.
Answer the student's question clearly and concisely (a short paragraph or a few bullet
points). Use simple language, give a small example when it helps, and do not invent facts.
If the question is not educational or is unclear, politely say so and suggest how to rephrase.

Question: {question}
"""


def answer_question_with_gemini(question: str) -> str:
    """Return a concise answer to `question`. Raises gemini_client.GeminiError on failure."""
    return gemini_client.generate(QNA_PROMPT.format(question=question.strip()), temperature=0.3)
