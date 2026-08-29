"""Optional live check against the real Gemini API.

Runs only when GEMINI_API_KEY is set (otherwise skipped), so CI without a key
stays green. Keeps the prompt tiny.
"""

import os

import pytest

import gemini_ai

pytestmark = pytest.mark.live

if not os.environ.get("GEMINI_API_KEY"):
    pytest.skip("GEMINI_API_KEY not set", allow_module_level=True)


def test_live_ask_gemini_returns_text():
    reply = gemini_ai.ask_gemini("Reply with exactly the word: pong")
    assert isinstance(reply, str) and reply.strip()


def test_live_bad_model_reports_friendly(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-does-not-exist-9x")
    monkeypatch.setattr(gemini_ai, "_client", None)
    monkeypatch.setattr(gemini_ai, "_client_key", None)
    with pytest.raises(gemini_ai.GeminiError) as exc:
        gemini_ai.ask_gemini("hi")
    assert "available nahi" in str(exc.value) or "model" in str(exc.value).lower()
