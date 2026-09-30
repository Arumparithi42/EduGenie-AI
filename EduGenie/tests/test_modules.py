"""Unit tests for the individual modules."""

import pytest

import explanation_module
import gemini_client
import learning_path
import quiz_module


def test_clean_json_block_removes_fences():
    assert quiz_module.clean_json_block('```json\n[{"a": 1}]\n```') == '[{"a": 1}]'
    assert quiz_module.clean_json_block("```\n[]\n```") == "[]"
    assert quiz_module.clean_json_block("[1, 2]") == "[1, 2]"


def test_parse_quiz_accepts_wrapped_object_and_skips_bad_items():
    raw = """{"questions": [
        {"question": "Q1", "options": ["a", "b", "c", "d"], "answer": "A"},
        {"question": "Q2", "options": ["a", "b"], "answer": "a"},
        {"question": "Q3", "options": ["w", "x", "y", "z"], "answer": "not an option"}
    ]}"""
    quiz = quiz_module.parse_quiz(raw)
    assert len(quiz) == 1
    assert quiz[0]["answer"] == "a"


def test_parse_quiz_extracts_array_from_surrounding_text():
    raw = 'Here is your quiz: [{"question": "Q", "options": ["1","2","3","4"], "answer": "3"}] Enjoy!'
    assert quiz_module.parse_quiz(raw)[0]["answer"] == "3"


def test_parse_quiz_raises_on_garbage():
    with pytest.raises(quiz_module.QuizFormatError):
        quiz_module.parse_quiz("no json here")


def test_quiz_format_error_is_gemini_error():
    assert issubclass(quiz_module.QuizFormatError, gemini_client.GeminiError)


def test_learning_path_invalid_level_defaults_to_beginner(fake_gemini):
    learning_path.get_learning_recommendations("SQL", "expert")
    assert "current level is: beginner" in fake_gemini.calls[0]["prompt"]


def test_explain_falls_back_to_gemini_when_local_fails(fake_gemini, monkeypatch):
    monkeypatch.setenv("EXPLAIN_BACKEND", "local")

    def broken(_topic):
        raise RuntimeError("model not installed")

    monkeypatch.setattr(explanation_module, "explain_with_local_model", broken)
    fake_gemini.reply = "Gemini explanation"
    assert explanation_module.explain_topic("Gravity") == ("Gemini explanation", "gemini")


def test_explain_uses_local_model_when_selected(fake_gemini, monkeypatch):
    monkeypatch.setenv("EXPLAIN_BACKEND", "local")
    monkeypatch.setattr(explanation_module, "explain_with_local_model", lambda t: f"Local: {t}")
    assert explanation_module.explain_topic("Gravity") == ("Local: Gravity", "local")
    assert fake_gemini.calls == []


def test_generate_without_key_raises(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(gemini_client.GeminiNotConfiguredError):
        gemini_client.generate("hello")


def test_placeholder_key_is_treated_as_missing(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "your_gemini_api_key_here")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert gemini_client.is_configured() is False


def test_model_name_default_and_override(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    assert gemini_client.get_model_name() == gemini_client.DEFAULT_MODEL
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    assert gemini_client.get_model_name() == "gemini-2.5-flash"
