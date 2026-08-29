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

    # 4. activity log stays capped
    for i in range(10):
        app._add_activity("info", f"row {i}")
    assert len(app._activity_rows) <= gui.MAX_ACTIVITY_ROWS

    # 5. clean shutdown
    app._shutdown()
    assert app._alive is False
