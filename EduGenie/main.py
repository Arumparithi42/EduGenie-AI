"""EduGenie - Google Gemini powered learning assistant (FastAPI app).

Run from the EduGenie/ folder:
    uvicorn main:app --reload
then open http://127.0.0.1:8000  (interactive API docs: http://127.0.0.1:8000/docs)
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

import explanation_module
import gemini_client
from explanation_module import explain_topic
from learning_path import LEVELS, get_learning_recommendations
from qna import answer_question_with_gemini
from quiz_module import DEFAULT_NUM_QUESTIONS, MAX_NUM_QUESTIONS, generate_quiz
from summary_module import summarize_text

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("edugenie")

BASE_DIR = Path(__file__).resolve().parent
MAX_TOPIC_CHARS = 300
MAX_TEXT_CHARS = 20_000


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not gemini_client.is_configured():
        logger.warning("GEMINI_API_KEY is not set - AI features will return an error until it is configured.")
    else:
        logger.info("Using Gemini model: %s", gemini_client.get_model_name())
    if os.getenv("PRELOAD_LOCAL_MODEL", "false").lower() == "true":
        explanation_module.preload()
    yield


app = FastAPI(
    title="EduGenie API",
    description="Google Gemini powered learning assistant: Q&A, explanations, quizzes, summaries and learning paths.",
    version="1.0.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# ---------------------------------------------------------------- request models
class ExplainRequest(BaseModel):
    topic: str = Field("", examples=["Photosynthesis"])


class TextRequest(BaseModel):
    text: str = Field("", examples=["The Pacific Ocean is the largest and deepest ocean on Earth..."])


class QuizRequest(BaseModel):
    text: str = Field("", examples=["The Pythagoras Theorem"])
    num_questions: int = Field(DEFAULT_NUM_QUESTIONS, ge=1, le=MAX_NUM_QUESTIONS)


# ---------------------------------------------------------------- helpers
def error(message: str, status_code: int) -> JSONResponse:
    return JSONResponse(content={"error": message}, status_code=status_code)


def validate_input(value: str | None, name: str, max_chars: int) -> str | JSONResponse:
    value = (value or "").strip()
    if not value:
        return error(f"Please provide {name}.", 400)
    if len(value) > max_chars:
        return error(f"Input is too long ({len(value)} characters). The limit is {max_chars}.", 400)
    return value


def ai_error(exc: gemini_client.GeminiError) -> JSONResponse:
    if isinstance(exc, gemini_client.GeminiBusyError):
        response = error(str(exc), 503)
        response.headers["Retry-After"] = "60"
        return response
    status = 503 if isinstance(exc, gemini_client.GeminiNotConfiguredError) else 502
    return error(str(exc), status)


# ---------------------------------------------------------------- pages
@app.get("/", include_in_schema=False)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"levels": LEVELS})


@app.get("/health", tags=["system"])
def health():
    return {
        "status": "ok",
        "gemini_configured": gemini_client.is_configured(),
        "gemini_model": gemini_client.get_model_name(),
        "gemini_fallback_models": gemini_client.get_fallback_models(),
        "gemini_max_retries": gemini_client.get_max_retries(),
        "explain_backend": explanation_module.get_backend(),
        "local_model_available": explanation_module.local_model_available(),
    }


# ---------------------------------------------------------------- API routes
# Endpoints are plain `def` so FastAPI runs the blocking model calls in a thread pool.

# Q&A - GET API using Gemini
@app.get("/qa", tags=["learning"])
def answer_question(question: str = Query(..., description="The question to answer")):
    question = validate_input(question, "a question", MAX_TOPIC_CHARS * 4)
    if isinstance(question, JSONResponse):
        return question
    try:
        return {"question": question, "answer": answer_question_with_gemini(question)}
    except gemini_client.GeminiError as exc:
        return ai_error(exc)


# Explanation - POST API (local LaMini-Flan-T5 or Gemini)
@app.post("/explain", tags=["learning"])
def explain_api(body: ExplainRequest):
    topic = validate_input(body.topic, "a topic", MAX_TOPIC_CHARS)
    if isinstance(topic, JSONResponse):
        return topic
    try:
        explanation, source = explain_topic(topic)
        return {"topic": topic, "explanation": explanation, "source": source}
    except gemini_client.GeminiError as exc:
        return ai_error(exc)


# Summarization - POST API
@app.post("/summarize", tags=["learning"])
def summarize_api(body: TextRequest):
    text = validate_input(body.text, "text to summarize", MAX_TEXT_CHARS)
    if isinstance(text, JSONResponse):
        return text
    try:
        return {"summary": summarize_text(text)}
    except gemini_client.GeminiError as exc:
        return ai_error(exc)


# Quiz Generation - POST API
@app.post("/quiz", tags=["learning"])
def quiz_api(body: QuizRequest):
    text = validate_input(body.text, "text or a topic for the quiz", MAX_TEXT_CHARS)
    if isinstance(text, JSONResponse):
        return text
    try:
        quiz = generate_quiz(text, body.num_questions)
        logger.info("Generated quiz with %d questions", len(quiz))
        return {"quiz": quiz}
    except gemini_client.GeminiError as exc:
        return ai_error(exc)


# Learning Recommendations - GET API
@app.get("/learn/recommendations", tags=["learning"])
def learning_recommendation_api(
    topic: str = Query(..., description="Topic the student wants to learn"),
    level: str = Query("beginner", description="beginner | intermediate | advanced"),
):
    topic = validate_input(topic, "a topic", MAX_TOPIC_CHARS)
    if isinstance(topic, JSONResponse):
        return topic
    try:
        return {"topic": topic, "level": level, "recommendation": get_learning_recommendations(topic, level)}
    except gemini_client.GeminiError as exc:
        return ai_error(exc)


if __name__ == "__main__":  # allows `python main.py`
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=int(os.getenv("PORT", "8000")), reload=True)
