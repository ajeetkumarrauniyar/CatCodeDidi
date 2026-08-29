"""Shared test fixtures.

Adds the project root to sys.path so `import router` and friends work when
pytest is run from anywhere.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def no_gemini_key(monkeypatch):
    """Guarantee GEMINI_API_KEY is absent for a test."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    import gemini_ai
    monkeypatch.setattr(gemini_ai, "_client", None)
    monkeypatch.setattr(gemini_ai, "_client_key", None)


@pytest.fixture
def fake_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
    import gemini_ai
    monkeypatch.setattr(gemini_ai, "_client", None)
    monkeypatch.setattr(gemini_ai, "_client_key", None)
