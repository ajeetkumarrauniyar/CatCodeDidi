"""The mute control silences spoken output and nothing else."""

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


@pytest.fixture
def spoken(monkeypatch):
    """Capture what actually reaches TTS."""
    said = []
    monkeypatch.setattr(assistant_mod.speech, "bot_speak", lambda t: said.append(t))
    monkeypatch.setattr(assistant_mod.speech, "clean_for_speech", lambda t: t)
    monkeypatch.setattr(assistant_mod.router, "classify", lambda t: ("ai", None))
    monkeypatch.setattr(assistant_mod.router, "route",
                        lambda t: assistant_mod.router.RouteResult(
                            user_text=t, response_text="the reply"))
    return said


# ------------------------------------------------------- central state

def test_assistant_starts_unmuted():
    assert assistant_mod.Assistant(Recorder()).muted is False


def test_muted_does_not_speak_but_still_displays(spoken):
    rec = Recorder()
    a = assistant_mod.Assistant(rec)
    a.muted = True
    a.submit_text("hello")
    assert spoken == []
    assert ("message", ("CatCodeDidi", "the reply")) in rec.events


def test_unmuted_speaks_and_displays(spoken):
    rec = Recorder()
    assistant_mod.Assistant(rec).submit_text("hello")
    assert spoken == ["the reply"]
    assert ("message", ("CatCodeDidi", "the reply")) in rec.events


def test_mute_applies_to_voice_mode_too(spoken, monkeypatch):
    monkeypatch.setattr(assistant_mod.speech, "recognize_once",
                        lambda: speech.RecognitionResult(text="hello"))
    rec = Recorder()
    a = assistant_mod.Assistant(rec)
    a.muted = True
    a.run_interaction()
    assert spoken == []
    assert ("message", ("CatCodeDidi", "the reply")) in rec.events


def test_mute_applies_to_local_command_replies(monkeypatch):
    """Not just AI answers - every spoken response respects the one state."""
    from commands import CommandResult
    said = []
    monkeypatch.setattr(assistant_mod.speech, "bot_speak", lambda t: said.append(t))
    monkeypatch.setattr(assistant_mod.speech, "clean_for_speech", lambda t: t)
    monkeypatch.setattr(assistant_mod.router, "handle_open_command",
                        lambda name: CommandResult(f"opening {name}", "ok"))
    rec = Recorder()
    a = assistant_mod.Assistant(rec)
    a.muted = True
    a.submit_text("open Safari")
    assert said == []
    assert ("message", ("CatCodeDidi", "opening Safari")) in rec.events


def test_mute_does_not_emit_speaking_state(spoken):
    """A muted assistant should not claim to be Speaking."""
    rec = Recorder()
    a = assistant_mod.Assistant(rec)
    a.muted = True
    a.submit_text("hello")
    assert assistant_mod.STATE_SPEAKING not in [
        p for k, p in rec.events if k == "state"]


def test_muting_does_not_block_recognition(monkeypatch, spoken):
    """Muting is about output; input must keep working."""
    listened = []

    def recognise():
        listened.append(True)
        return speech.RecognitionResult(text="hello")

    monkeypatch.setattr(assistant_mod.speech, "recognize_once", recognise)
    a = assistant_mod.Assistant(Recorder())
    a.muted = True
    a.run_interaction()
    a.run_interaction()
    assert len(listened) == 2


# ------------------------------------------------------- stopping audio

def test_stop_audio_is_a_noop_when_nothing_is_playing(monkeypatch):
    monkeypatch.setattr(speech, "_playing", None)
    speech.stop_audio()          # must not raise


def test_stop_audio_stops_the_current_clip(monkeypatch):
    stopped = []

    class FakeSound:
        def stop(self):
            stopped.append(True)

    monkeypatch.setattr(speech, "_playing", FakeSound())
    speech.stop_audio()
    assert stopped == [True]


def test_stop_audio_survives_a_backend_that_cannot_stop(monkeypatch):
    class Stubborn:
        def stop(self):
            raise RuntimeError("backend already exited")

    monkeypatch.setattr(speech, "_playing", Stubborn())
    speech.stop_audio()          # swallowed, never reaches the user


def test_play_audio_clears_the_handle_when_finished(monkeypatch):
    class FakeSound:
        def wait(self):
            pass

        def stop(self):
            pass

    monkeypatch.setattr(speech.playsound3, "playsound",
                        lambda path, block: FakeSound())
    speech.play_audio("x.mp3")
    assert speech._playing is None


@pytest.mark.audio
def test_real_playback_can_actually_be_stopped():
    """End-to-end, with real gTTS audio: muting mid-sentence cuts the clip.

    Opt in with `pytest -m audio` - it needs the network and speakers.
    """
    import threading
    import time

    thread = threading.Thread(
        target=lambda: speech.bot_speak("Yeh ek lamba vaakya hai. " * 4))
    thread.start()

    started = time.time()               # gTTS must fetch the MP3 first
    while speech._playing is None and time.time() - started < 20:
        time.sleep(0.05)
    assert speech._playing is not None, "playback never started"

    time.sleep(1.0)
    speech.stop_audio()
    thread.join(timeout=10)
    assert not thread.is_alive(), "stop_audio did not unblock bot_speak"
    assert speech._playing is None


# ------------------------------------------------------------- GUI

@pytest.mark.gui
def test_mute_button_in_both_modes(monkeypatch, tk_root, gui_pump):
    monkeypatch.setattr(gui.Assistant, "startup_greeting", lambda self: None)
    stopped = []
    monkeypatch.setattr(gui.speech, "stop_audio", lambda: stopped.append(True))

    app = gui.CatCodeDidiGUI(tk_root)
    gui_pump(tk_root, 0.4)

    # one control, starting unmuted, wired to the assistant's central state
    assert app.mute_button.muted is False
    assert app.assistant.muted is False

    # mute -> assistant state flips and any current speech is cut short
    app.mute_button._click(None)
    gui_pump(tk_root, 0.2)
    assert app.mute_button.muted is True
    assert app.assistant.muted is True
    assert stopped == [True]

    # the state survives a mode switch, and the button is still there
    app._on_mode_change(gui.MODE_TEXT)
    gui_pump(tk_root, 0.2)
    assert app.assistant.muted is True
    assert app.mute_button.muted is True
    assert app.mute_button.grid_info() != {}

    app._on_mode_change(gui.MODE_VOICE)
    gui_pump(tk_root, 0.2)
    assert app.assistant.muted is True
    assert app.mute_button.grid_info() != {}

    # unmute -> no extra stop, state clears
    app.mute_button._click(None)
    gui_pump(tk_root, 0.2)
    assert app.assistant.muted is False
    assert stopped == [True]          # stop only happens when muting
    app._shutdown()


@pytest.mark.gui
def test_mute_button_state_is_not_colour_alone(monkeypatch, tk_root, gui_pump):
    """The icon shape must change too, for colour-blind users and screenshots."""
    monkeypatch.setattr(gui.Assistant, "startup_greeting", lambda self: None)
    monkeypatch.setattr(gui.speech, "stop_audio", lambda: None)
    app = gui.CatCodeDidiGUI(tk_root)
    gui_pump(tk_root, 0.3)

    def shapes():
        return sorted(app.mute_button.type(i) for i in app.mute_button.find_all())

    unmuted = shapes()
    app.mute_button._click(None)
    gui_pump(tk_root, 0.2)
    muted = shapes()
    assert unmuted != muted
    assert "arc" in unmuted and "arc" not in muted     # waves -> cross
    assert "line" in muted
    app._shutdown()


@pytest.mark.gui
def test_muting_does_not_disable_any_input(monkeypatch, tk_root, gui_pump):
    monkeypatch.setattr(gui.Assistant, "startup_greeting", lambda self: None)
    monkeypatch.setattr(gui.speech, "stop_audio", lambda: None)
    sent = []
    monkeypatch.setattr(gui.Assistant, "submit_text",
                        lambda self, text: sent.append(text))
    monkeypatch.setattr(gui.Assistant, "run_interaction",
                        lambda self: sent.append("VOICE"))

    app = gui.CatCodeDidiGUI(tk_root)
    gui_pump(tk_root, 0.4)
    app.mute_button._click(None)          # mute everything
    gui_pump(tk_root, 0.2)

    def settle():
        for _ in range(200):
            if not app._busy():
                break
            tk_root.update()
        gui_pump(tk_root, 0.2)

    # voice still listens while muted
    app._trigger()
    settle()
    assert "VOICE" in sent

    # and text still sends while muted
    app._on_mode_change(gui.MODE_TEXT)
    gui_pump(tk_root, 0.2)
    app.entry.insert(0, "still working")
    app._submit_text()
    settle()
    assert "still working" in sent
    app._shutdown()
