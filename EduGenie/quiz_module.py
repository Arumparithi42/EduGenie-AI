"""Quiz generation module (Gemini).

Generates multiple-choice questions (4 options each) from a passage or a topic and
returns them as a validated Python list of dicts:
    [{"question": str, "options": [str, str, str, str], "answer": str, "explanation": str}]
"""

from __future__ import annotations

import json
import re

import gemini_client

DEFAULT_NUM_QUESTIONS = 3
MAX_NUM_QUESTIONS = 10

QUIZ_PROMPT = """You are a quiz generator for students.

From the following input, create {n} multiple-choice questions. The input is either a
passage (then only ask about information in the passage) or a short topic name (then ask
about the core concepts of that topic). Each question must include:
- A "question"
- A list of exactly 4 "options" (plausible distractors, no "All of the above")
- A correct "answer" that must exactly match one of the options
- A one-sentence "explanation" of why the answer is correct

Format your output as valid JSON only, like this:
[
  {{
    "question": "What is ...?",
    "options": ["A", "B", "C", "D"],
    "answer": "A",
    "explanation": "Because ..."
  }}
]

Input:
\"\"\"
{text}
\"\"\"
"""


class QuizFormatError(gemini_client.GeminiError):
    """Raised when Gemini's reply cannot be turned into a valid quiz."""


def clean_json_block(text: str) -> str:
    """Remove Markdown ```json code fences (if any) around the model output."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, flags=re.DOTALL)
    if match:
        text = match.group(1).strip()
    return text


def parse_quiz(raw: str) -> list[dict]:
    """Parse and validate the model output. Raises QuizFormatError if it is unusable."""
    cleaned = clean_json_block(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Fall back to the first JSON array found anywhere in the text.
        match = re.search(r"\[.*\]", cleaned, flags=re.DOTALL)
        if not match:
            raise QuizFormatError("The AI response was not valid JSON. Please try again.")
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise QuizFormatError("The AI response was not valid JSON. Please try again.") from exc

    if isinstance(data, dict):  # e.g. {"questions": [...]}
        data = data.get("questions") or data.get("quiz") or []
    if not isinstance(data, list):
        raise QuizFormatError("The AI response did not contain a list of questions.")

    quiz: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "")).strip()
        options = item.get("options")
        answer = str(item.get("answer", "")).strip()
        if not question or not isinstance(options, list) or len(options) != 4:
            continue
        options = [str(o).strip() for o in options]
        answer = _match_answer(answer, options)
        if answer is None:
            continue
        quiz.append(
            {
                "question": question,
                "options": options,
                "answer": answer,
                "explanation": str(item.get("explanation", "")).strip(),
            }
        )

    if not quiz:
        raise QuizFormatError("The AI did not return any valid questions. Please try again.")
    return quiz


def _match_answer(answer: str, options: list[str]) -> str | None:
    """Map the model's answer onto one of the options (exact, case-insensitive or letter)."""
    if answer in options:
        return answer
    lowered = {o.lower(): o for o in options}
    if answer.lower() in lowered:
        return lowered[answer.lower()]
    letter = answer.strip().rstrip(").:").upper()
    if len(letter) == 1 and letter in "ABCD":
        return options["ABCD".index(letter)]
    return None


def generate_quiz(text: str, num_questions: int = DEFAULT_NUM_QUESTIONS) -> list[dict]:
    """Generate a validated MCQ quiz from `text`. Raises gemini_client.GeminiError on failure."""
    n = max(1, min(int(num_questions), MAX_NUM_QUESTIONS))
    raw = gemini_client.generate(QUIZ_PROMPT.format(n=n, text=text.strip()), json_mode=True, temperature=0.4)
    return parse_quiz(raw)[:n]
