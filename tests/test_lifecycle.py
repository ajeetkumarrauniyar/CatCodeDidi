"""Hide to background, restore on a wake word, and really quit."""

import pytest

import gui
import wakeword

pytestmark = pytest.mark.gui


@pytest.fixture
def app(monkeypatch, tk_root, gui_pump):
    """A window whose wake listener is stubbed but reports as running."""
    monkeypatch.setattr(gui.Assistant, "startup_greeting", lambda self: None)
    monkeypatch.setattr(gui.speech, "stop_audio", lambda: None)
    for name in ("start", "pause", "resume", "stop"):
        monkeypatch.setattr(wakeword.WakeWordDetector, name, lambda self: None)
    # Report as running without actually opening the microphone.
    monkeypatch.setattr(wakeword.WakeWordDetector, "running",
                        property(lambda self: True))
    window = gui.CatCodeDidiGUI(tk_root)
    gui_pump(tk_root, 0.4)
    return window


def _enable_wake(app, tk_root, gui_pump):
    app.wake_switch.select()
    app._on_wake_switch()
    gui_pump(tk_root, 0.2)


def test_close_quits_when_nothing_is_listening(app, tk_root, gui_pump):
    """Hiding with no wake listener would leave an unreachable process, so
    the close button does what it normally means instead."""
    assert app._wake_enabled is False
    app._on_close()
    assert app._alive is False
    assert app._hidden is False


def test_close_hides_when_the_wake_listener_is_running(app, tk_root, gui_pump):
    _enable_wake(app, tk_root, gui_pump)
    app._on_close()
    gui_pump(tk_root, 0.3)

    assert app._hidden is True
    assert app._alive is True                 # still running in the background
    assert tk_root.state() == "withdrawn"


def test_wake_word_restores_a_hidden_window_and_listens(app, tk_root, gui_pump,
                                                        monkeypatch):
    listened = []
    monkeypatch.setattr(gui.Assistant, "run_interaction",
                        lambda self: listened.append(1))
    _enable_wake(app, tk_root, gui_pump)
    app._on_close()
    gui_pump(tk_root, 0.3)
    assert app._hidden is True

    app._handle("wake", None)                 # arrives via the queue, Tk thread
    for _ in range(300):
        if not app._busy():
            break
        tk_root.update()
    gui_pump(tk_root, 0.3)

    assert app._hidden is False
    assert tk_root.state() == "normal"        # restored
    assert listened == [1]                    # and went straight to listening


def test_repeated_hide_show_cycles(app, tk_root, gui_pump):
    _enable_wake(app, tk_root, gui_pump)
    for _ in range(4):
        app._on_close()
        gui_pump(tk_root, 0.15)
        assert app._hidden is True and app._alive is True
        app.show()
        gui_pump(tk_root, 0.15)
        assert app._hidden is False
        assert tk_root.state() == "normal"


def test_hide_is_idempotent(app, tk_root, gui_pump):
    _enable_wake(app, tk_root, gui_pump)
    app.hide()
    app.hide()
    gui_pump(tk_root, 0.2)
    assert app._hidden is True
    app.show()
    gui_pump(tk_root, 0.2)
    assert app._hidden is False


def test_quit_button_terminates_even_while_listening(app, tk_root, gui_pump):
    _enable_wake(app, tk_root, gui_pump)
    assert app._alive is True
    app.quit_button.invoke()
    assert app._alive is False


def test_quit_stops_wake_detection(monkeypatch, tk_root, gui_pump):
    """Detection cannot outlive the process, and we must not pretend it does."""
    monkeypatch.setattr(gui.Assistant, "startup_greeting", lambda self: None)
    for name in ("start", "pause", "resume"):
        monkeypatch.setattr(wakeword.WakeWordDetector, name, lambda self: None)
    stopped = []
    monkeypatch.setattr(wakeword.WakeWordDetector, "stop",
                        lambda self: stopped.append(1))

    window = gui.CatCodeDidiGUI(tk_root)
    gui_pump(tk_root, 0.4)
    window.wake_switch.select()
    window._on_wake_switch()

    window._shutdown()
    assert stopped == [1]
    assert window._alive is False


def test_hiding_does_not_animate(app, tk_root, gui_pump):
    """A withdrawn window must not keep repainting the orb."""
    _enable_wake(app, tk_root, gui_pump)
    app._state = "Listening..."
    app._on_close()
    gui_pump(tk_root, 0.3)

    before = app._phase
    gui_pump(tk_root, 0.5)
    assert app._phase == before               # no frames drawn while hidden

    app.show()
    gui_pump(tk_root, 0.4)
    assert app._phase > before                # and it resumes when visible


def test_show_and_hide_are_safe_after_quit(app, tk_root, gui_pump):
    app._shutdown()
    app.hide()          # must not raise on a destroyed window
    app.show()
    assert app._alive is False
