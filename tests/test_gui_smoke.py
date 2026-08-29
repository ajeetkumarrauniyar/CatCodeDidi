"""End-to-end GUI smoke test. Marked `gui`: skipped automatically when Tk
cannot open a display (the tk_root fixture handles that).

One test drives one app instance through the whole flow - creating several
CTk() roots in a single process is unreliable.
"""

import pytest

import commands
import gui
import speech

pytestmark = pytest.mark.gui


def test_gui_end_to_end(monkeypatch, tk_root, gui_pump):
    monkeypatch.setattr(gui.Assistant, "startup_greeting", lambda self: None)
    monkeypatch.setattr("speech.bot_speak", lambda text: None)
    monkeypatch.setattr(commands, "_open_application", lambda name: None)

    transcripts = iter([
        speech.RecognitionResult(text="open Safari"),
        speech.RecognitionResult(error_title="Microphone access needed",
                                 error="Enable it in settings."),
    ])
    monkeypatch.setattr("speech.recognize_once", lambda: next(transcripts))

    app = gui.CatCodeDidiGUI(tk_root)
    gui_pump(tk_root, 0.4)

    # 1. builds and reaches Ready
    assert app._alive and app._state == gui.STATE_READY
    assert app.orb is not None and app.pill_text.cget("text") == "Ready"

    def run_once():
        app._trigger()
        for _ in range(400):
            if not app._busy():
                break
            tk_root.update()
        gui_pump(tk_root, 0.3)

    # 2. a local command: transcript + reply cards, back to Ready
    run_once()
    texts = [c.body.cget("text") for c in app._cards]
    assert "open Safari" in texts
    assert any("Safari" in t for t in texts if t != "open Safari")
    assert app._state == gui.STATE_READY
    assert app.orb._enabled is True

    # 3. a mic failure: error card, recovered to Ready, no crash
    run_once()
    assert any(c.body.cget("text") == "Enable it in settings." for c in app._cards)
    assert app._state == gui.STATE_READY

    # 4. the Activity panel is gone, and the dock took its row
    assert not hasattr(app, "activity")
    assert not hasattr(app, "_activity_rows")
    assert app.dock.grid_info()["row"] == 3
    assert app.controls.winfo_exists()

    # 5. clean shutdown
    app._shutdown()
    assert app._alive is False


def test_activity_events_are_logged_not_shown(monkeypatch, tk_root, gui_pump, caplog):
    """Diagnostics must survive the panel removal - they go to the log now."""
    monkeypatch.setattr(gui.Assistant, "startup_greeting", lambda self: None)
    app = gui.CatCodeDidiGUI(tk_root)
    gui_pump(tk_root, 0.3)
    cards_before = len(app._cards)

    with caplog.at_level("INFO", logger="catcodedidi"):
        app._handle("activity", ("open", "Opened Google Chrome"))
        app._handle("activity", ("warn", "Gemini unavailable"))

    assert "Opened Google Chrome" in caplog.text
    assert "Gemini unavailable" in caplog.text
    assert any(r.levelname == "WARNING" for r in caplog.records)
    assert len(app._cards) == cards_before          # nothing added to the window
    app._shutdown()


def test_layout_has_no_dead_space_after_removing_activity(tk_root, monkeypatch, gui_pump):
    """The reclaimed height must go to the conversation, not become a gap.

    Regression: an empty CTkFrame defaults to 200px, so the reserved controls
    strip silently left a dead band under the conversation.
    """
    monkeypatch.setattr(gui.Assistant, "startup_greeting", lambda self: None)
    app = gui.CatCodeDidiGUI(tk_root)
    gui_pump(tk_root, 0.4)
    tk_root.update()

    weights = {r: tk_root.grid_rowconfigure(r).get("weight") for r in range(4)}
    assert weights[2] > 0                            # conversation grows
    assert all(weights[r] == 0 for r in (0, 1, 3))   # header/voice/dock do not

    # The dock is sized by its contents, never by CTkFrame's 200px default.
    assert app.controls.winfo_height() < 120
    assert app.dock.winfo_height() < 220

    conversation = [c for c in tk_root.grid_slaves() if c.grid_info()["row"] == 2][0]
    assert conversation.winfo_height() > app.dock.winfo_height()
    app._shutdown()


def test_window_resize_keeps_layout_sane(tk_root, monkeypatch, gui_pump):
    monkeypatch.setattr(gui.Assistant, "startup_greeting", lambda self: None)
    app = gui.CatCodeDidiGUI(tk_root)
    gui_pump(tk_root, 0.3)

    for geometry in ("1100x950", "760x700", "900x900"):
        tk_root.geometry(geometry)
        gui_pump(tk_root, 0.25)
        conversation = [c for c in tk_root.grid_slaves()
                        if c.grid_info()["row"] == 2][0]
        assert app.dock.winfo_height() < 220              # never inflates
        assert conversation.winfo_height() > app.dock.winfo_height()
    app._shutdown()
