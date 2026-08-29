"""Voice Mode / Text Mode: the input method changes, nothing else does."""

import pytest

import assistant as assistant_mod
import gui
import speech


class Recorder:
    def __init__(self):
        self.events = []

    def __call__(self, kind, payload):
        self.events.append((kind, payload))

    def kinds(self):
        return [k for k, _ in self.events]


# ------------------------------------------------------- shared pipeline

def _routed(monkeypatch, response="the answer"):
    """Silence TTS and capture what reaches router.route()."""
    seen = []
    monkeypatch.setattr(assistant_mod.speech, "bot_speak", lambda t: None)
    monkeypatch.setattr(assistant_mod.speech, "clean_for_speech", lambda t: t)
    monkeypatch.setattr(assistant_mod.router, "classify", lambda t: ("ai", None))

    def route(text):
        seen.append(text)
        return assistant_mod.router.RouteResult(user_text=text, response_text=response)

    monkeypatch.setattr(assistant_mod.router, "route", route)
    return seen


def test_voice_and_text_reach_the_same_pipeline(monkeypatch):
    """Both entry points must funnel into process_user_input - no parallel
    AI logic, no second Gemini path."""
    monkeypatch.setattr(assistant_mod.speech, "recognize_once",
                        lambda: speech.RecognitionResult(text="what is python"))
    calls = []
    rec = Recorder()
    a = assistant_mod.Assistant(rec)
    monkeypatch.setattr(a, "process_user_input", lambda text: calls.append(text))

    a.run_interaction()          # voice
    a.submit_text("what is python")   # text
    assert calls == ["what is python", "what is python"]


def test_voice_and_text_produce_identical_events(monkeypatch):
    """Same input, different capture method -> byte-identical event stream."""
    _routed(monkeypatch)
    monkeypatch.setattr(assistant_mod.speech, "recognize_once",
                        lambda: speech.RecognitionResult(text="hello there"))

    voice = Recorder()
    assistant_mod.Assistant(voice).run_interaction()

    text = Recorder()
    assistant_mod.Assistant(text).submit_text("hello there")

    # Voice adds the listening preamble; from the transcript on they match.
    start = voice.kinds().index("transcript")
    assert voice.events[start:] == text.events[text.kinds().index("transcript"):]


def test_text_input_is_routed_verbatim(monkeypatch):
    seen = _routed(monkeypatch)
    assistant_mod.Assistant(Recorder()).submit_text("  open Safari  ")
    assert seen == ["open Safari"]          # trimmed, not otherwise altered


def test_blank_text_is_ignored(monkeypatch):
    seen = _routed(monkeypatch)
    rec = Recorder()
    assistant_mod.Assistant(rec).submit_text("   ")
    assert seen == []
    assert rec.events == []


def test_local_commands_work_from_text_mode(monkeypatch):
    """Text Mode must use the same command routing, not just Gemini."""
    from commands import CommandResult

    monkeypatch.setattr(assistant_mod.speech, "bot_speak", lambda t: None)
    monkeypatch.setattr(assistant_mod.speech, "clean_for_speech", lambda t: t)
    handled = []

    def fake_open(app_name):
        handled.append(app_name)
        return CommandResult(f"opening {app_name}", "ok")

    monkeypatch.setattr(assistant_mod.router, "handle_open_command", fake_open)
    rec = Recorder()
    assistant_mod.Assistant(rec).submit_text("open Safari")
    assert handled == ["Safari"]
    assert ("message", ("CatCodeDidi", "opening Safari")) in rec.events


# ---------------------------------------------------------------- muting

def test_muted_assistant_still_displays_but_does_not_speak(monkeypatch):
    spoken = []
    monkeypatch.setattr(assistant_mod.speech, "bot_speak", lambda t: spoken.append(t))
    monkeypatch.setattr(assistant_mod.speech, "clean_for_speech", lambda t: t)
    monkeypatch.setattr(assistant_mod.router, "classify", lambda t: ("ai", None))
    monkeypatch.setattr(assistant_mod.router, "route",
                        lambda t: assistant_mod.router.RouteResult(
                            user_text=t, response_text="hi"))
    rec = Recorder()
    a = assistant_mod.Assistant(rec)
    a.muted = True
    a.submit_text("hello")
    assert spoken == []
    assert ("message", ("CatCodeDidi", "hi")) in rec.events


# -------------------------------------------------------------- GUI modes

pytestmark_gui = pytest.mark.gui


@pytest.mark.gui
def test_mode_switching(monkeypatch, tk_root, gui_pump):
    monkeypatch.setattr(gui.Assistant, "startup_greeting", lambda self: None)
    monkeypatch.setattr("speech.bot_speak", lambda t: None)
    submitted = []
    monkeypatch.setattr(gui.Assistant, "submit_text",
                        lambda self, text: submitted.append(text))
    monkeypatch.setattr(gui.Assistant, "run_interaction",
                        lambda self: submitted.append("VOICE"))

    app = gui.CatCodeDidiGUI(tk_root)
    gui_pump(tk_root, 0.4)

    def settle():
        for _ in range(200):
            if not app._busy():
                break
            tk_root.update()
        gui_pump(tk_root, 0.2)

    # --- starts in Voice Mode: composer hidden, mic live
    assert app._mode == gui.MODE_VOICE
    assert not app.text_row.winfo_ismapped() or app.text_row.grid_info() == {}
    assert app.orb._enabled is True
    assert str(app.entry.cget("state")) == "disabled"

    # --- Voice -> Text
    app._on_mode_change(gui.MODE_TEXT)
    gui_pump(tk_root, 0.2)
    assert app._mode == gui.MODE_TEXT
    assert app.text_row.grid_info() != {}          # composer shown
    assert str(app.entry.cget("state")) == "normal"
    assert app.orb._enabled is False               # mic not the input here

    # typing + Enter submits through the shared pipeline
    app.entry.insert(0, "what is python")
    app._submit_text()
    settle()
    assert submitted == ["what is python"]
    assert app.entry.get() == ""                   # cleared after send

    # Send button uses the same path
    app.entry.insert(0, "second question")
    app.send_button.invoke()
    settle()
    assert submitted == ["what is python", "second question"]

    # blank input does nothing
    app._submit_text()
    settle()
    assert len(submitted) == 2

    # the mic is inert in Text Mode
    app._trigger()
    settle()
    assert "VOICE" not in submitted

    # --- Text -> Voice
    app._on_mode_change(gui.MODE_VOICE)
    gui_pump(tk_root, 0.2)
    assert app.text_row.grid_info() == {}          # composer hidden again
    assert app.orb._enabled is True
    app._trigger()
    settle()
    assert submitted[-1] == "VOICE"

    # --- repeated switching stays consistent
    for _ in range(3):
        app._on_mode_change(gui.MODE_TEXT)
        gui_pump(tk_root, 0.1)
        assert app.text_row.grid_info() != {}
        app._on_mode_change(gui.MODE_VOICE)
        gui_pump(tk_root, 0.1)
        assert app.text_row.grid_info() == {}
    assert app.orb._enabled is True

    app._shutdown()


@pytest.mark.gui
def test_space_does_not_hijack_typing(monkeypatch, tk_root, gui_pump):
    """The global Space/Enter shortcut must never fire the mic while the user
    is composing a message - a space is a character there, not a shortcut."""
    monkeypatch.setattr(gui.Assistant, "startup_greeting", lambda self: None)
    fired = []
    monkeypatch.setattr(gui.Assistant, "run_interaction",
                        lambda self: fired.append(1))

    app = gui.CatCodeDidiGUI(tk_root)
    gui_pump(tk_root, 0.3)
    app._on_mode_change(gui.MODE_TEXT)
    gui_pump(tk_root, 0.2)

    for _ in range(3):
        app._key_trigger(None)
        gui_pump(tk_root, 0.1)
    assert fired == []                      # mic stayed silent in Text Mode

    # and the composer still holds exactly what was typed
    app.entry.insert(0, "hello world")
    app._key_trigger(None)
    gui_pump(tk_root, 0.1)
    assert app.entry.get() == "hello world"

    # back in Voice Mode the shortcut works again
    app.entry.delete(0, "end")
    app._on_mode_change(gui.MODE_VOICE)
    gui_pump(tk_root, 0.2)
    app._key_trigger(None)
    for _ in range(200):
        if not app._busy():
            break
        tk_root.update()
    assert fired == [1]
    app._shutdown()


@pytest.mark.gui
def test_text_mode_gives_its_space_to_the_conversation(monkeypatch, tk_root, gui_pump):
    """The mic is not the input method in Text Mode, so it is withdrawn and
    the conversation - the top priority - absorbs the height."""
    monkeypatch.setattr(gui.Assistant, "startup_greeting", lambda self: None)
    app = gui.CatCodeDidiGUI(tk_root)
    gui_pump(tk_root, 0.4)
    tk_root.update()

    def row_height(r):
        return [c for c in tk_root.grid_slaves()
                if c.grid_info()["row"] == r][0].winfo_height()

    voice_conversation = row_height(2)
    assert app.orb.grid_info() != {}                 # mic visible in Voice Mode

    app._on_mode_change(gui.MODE_TEXT)
    gui_pump(tk_root, 0.4)
    tk_root.update()
    assert app.orb.grid_info() == {}                 # mic withdrawn
    assert row_height(2) > voice_conversation        # conversation grew

    app._on_mode_change(gui.MODE_VOICE)
    gui_pump(tk_root, 0.4)
    tk_root.update()
    assert app.orb.grid_info() != {}                 # and comes back
    assert row_height(2) == voice_conversation       # exactly as before
    app._shutdown()


@pytest.mark.gui
def test_mode_prompts_tell_the_user_what_to_do(monkeypatch, tk_root, gui_pump):
    monkeypatch.setattr(gui.Assistant, "startup_greeting", lambda self: None)
    app = gui.CatCodeDidiGUI(tk_root)
    gui_pump(tk_root, 0.3)

    assert "mic" in app.caption.cget("text").lower()
    app._on_mode_change(gui.MODE_TEXT)
    gui_pump(tk_root, 0.2)
    assert "type" in app.caption.cget("text").lower()
    assert "enter" in app.hint.cget("text").lower()
    app._shutdown()
