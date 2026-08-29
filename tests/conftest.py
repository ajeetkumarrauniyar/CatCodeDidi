"""Shared test fixtures. Adds the project root to sys.path so `import router`
etc. work when pytest is run from anywhere."""

import os
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


@pytest.fixture
def tk_root():
    """A hidden CTk root, or skip the test if no display is available."""
    try:
        import customtkinter as ctk
        root = ctk.CTk()
    except Exception as exc:  # pragma: no cover - depends on environment
        pytest.skip(f"no Tk display: {exc}")
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


def pump(root, seconds):
    """Spin the Tk event loop for `seconds` without blocking."""
    import time
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.02)


@pytest.fixture
def gui_pump():
    return pump
