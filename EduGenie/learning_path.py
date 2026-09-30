"""Personalized learning path / recommendation module (Gemini)."""

from __future__ import annotations

import gemini_client

LEVELS = ("beginner", "intermediate", "advanced")

LEARNING_PATH_PROMPT = """You are an expert AI tutor. The student wants to learn about: {topic}.
The student's current level is: {level}.

Create a structured and adaptive learning path formatted in Markdown:
1. A short introduction to what the student will be able to do at the end.
2. Sections "## Beginner", "## Intermediate" and "## Advanced" (start from the student's level;
   briefly list earlier-level prerequisites if they are skipping ahead).
3. In every section list the key topics in the order they should be learned, each with a
   one-line description and an estimated time (for example "~3 days").
4. A "## Resources" section with free, well-known resources (official documentation,
   YouTube channels, articles, books). Only recommend resources you are confident exist.
5. A "## Practice Projects" section with 2-3 hands-on project ideas.
6. A "## Suggested Timeline" section summarising a realistic week-by-week plan.
"""


def get_learning_recommendations(topic: str, level: str = "beginner") -> str:
    """Return a Markdown learning path for `topic`. Raises gemini_client.GeminiError on failure."""
    level = level.lower().strip() if level else "beginner"
    if level not in LEVELS:
        level = "beginner"
    prompt = LEARNING_PATH_PROMPT.format(topic=topic.strip(), level=level)
    return gemini_client.generate(prompt, temperature=0.5)
