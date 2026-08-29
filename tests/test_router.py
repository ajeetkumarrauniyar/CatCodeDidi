import pytest

import commands
import router


@pytest.mark.parametrize("text, expected", [
    ("open google chrome", ("open", "google chrome")),
    ("Open  Google  Chrome", ("open", "Google Chrome")),   # split() collapses spaces
    ("close chrome", ("close", "chrome")),
    ("take a screenshot", ("screenshot", None)),
    ("SCREENSHOT now", ("screenshot", None)),
    ("who is your father", ("creator", None)),
    ("shutdown", ("exit", None)),
    ("good night", ("exit", None)),
    ("what is python", ("ai", None)),
    ("open", ("ai", None)),          # bare verb, no target -> not a command
    ("", ("ai", None)),
])
def test_classify(text, expected):
    assert router.classify(text) == expected


def test_route_creator():
    r = router.route("who is your father")
    assert r.response_text == router.FATHER_ANSWER
    assert r.is_exit is False
    assert r.activity and r.activity[0][0] == "ok"


def test_route_exit():
    r = router.route("shutdown")
    assert r.is_exit is True
    assert r.response_text == router.EXIT_REPLY


def test_route_open_success(monkeypatch):
    monkeypatch.setattr(
        router, "handle_open_command",
        lambda name: commands.CommandResult(f"opening {name}", f"Opened {name}", ok=True),
    )
    r = router.route("open Safari")
    assert r.response_text == "opening Safari"
    assert r.activity == [("open", "Opened Safari")]


def test_route_open_failure_marks_warn(monkeypatch):
    monkeypatch.setattr(
        router, "handle_open_command",
        lambda name: commands.CommandResult("no such app", "Could not open X", ok=False),
    )
    r = router.route("open Nonesuch")
    assert r.activity[0][0] == "warn"


def test_route_screenshot(monkeypatch):
    monkeypatch.setattr(
        router, "take_screenshot",
        lambda: commands.CommandResult("done", "Screenshot saved to /x.png", ok=True),
    )
    r = router.route("take a screenshot")
    assert r.activity == [("shot", "Screenshot saved to /x.png")]


def test_route_ai_success(monkeypatch):
    monkeypatch.setattr(router, "ask_gemini", lambda prompt: "42")
    r = router.route("what is six times seven")
    assert r.response_text == "42"
    kinds = [k for k, _ in r.activity]
    assert kinds == ["ai", "ai"]


def test_route_ai_gemini_error_is_safe(monkeypatch):
    def boom(prompt):
        raise router.GeminiError("Gemini API key not configured.")
    monkeypatch.setattr(router, "ask_gemini", boom)
    r = router.route("tell me a joke")
    assert r.response_text == "Gemini API key not configured."
    assert r.activity[-1][0] == "warn"


def test_route_ai_unexpected_error_does_not_leak(monkeypatch):
    def boom(prompt):
        raise ValueError("secret-token-should-not-appear")
    monkeypatch.setattr(router, "ask_gemini", boom)
    r = router.route("hello")
    assert "secret-token" not in r.response_text
    assert "ValueError" in r.activity[-1][1]
