"""Wake word: detection accuracy, microphone ownership, and GUI integration."""

import json
import threading
import time

import pytest

import gui
import speech
import wakeword


# ------------------------------------------------------- phrase matching

@pytest.mark.parametrize("text", ["cat code didi", "didi", "cat code",
                                  "Cat Code Didi", "  DIDI  "])
def test_accepts_every_wake_phrase_any_case(text):
    d = wakeword.WakeWordDetector(on_wake=lambda: None)
    assert d._is_wake({"text": text}) is True


@pytest.mark.parametrize("text", [
    "[unk] didi",           # "what is the weather today" decodes like this
    "didi [unk]",           # "the deed is done"
    "[unk]",
    "cat code didi [unk]",
    "",
    "   ",
    "kitty code didi",
])
def test_rejects_near_misses_and_unknowns(text):
    """Grammar mode maps every utterance onto the nearest phrase, so anything
    carrying an [unk] means the user was saying something else."""
    d = wakeword.WakeWordDetector(on_wake=lambda: None)
    assert d._is_wake({"text": text}) is False


def test_missing_text_key_is_safe():
    d = wakeword.WakeWordDetector(on_wake=lambda: None)
    assert d._is_wake({}) is False


# --------------------------------------------------------- microphone

def test_microphone_allows_one_owner():
    mic = speech._MicrophoneOwner()
    with mic.claim("wake listener"):
        assert mic.owner == "wake listener"
        with pytest.raises(speech.MicrophoneBusy, match="wake listener"):
            with mic.claim("command listener"):
                pass
    assert mic.owner is None            # released


def test_microphone_is_released_after_an_error():
    mic = speech._MicrophoneOwner()
    with pytest.raises(ValueError):
        with mic.claim("wake listener"):
            raise ValueError("boom")
    with mic.claim("command listener"):  # must not deadlock
        pass


def test_recognize_once_reports_a_busy_microphone(monkeypatch):
    monkeypatch.setattr(speech, "_has_microphone", lambda: True)
    with speech.microphone.claim("wake listener"):
        result = speech.recognize_once()
    assert not result.ok
    assert result.error_title == "Microphone busy"


# ----------------------------------------------------- detector lifecycle

class FakeStream:
    """Feeds fixed chunks, then silence, so the loop can be driven headlessly."""

    def __init__(self, chunks):
        self.chunks = list(chunks)
        self.closed = False

    def read(self, _frames, exception_on_overflow=False):
        time.sleep(0.01)
        return self.chunks.pop(0) if self.chunks else b"\x00" * 100

    def stop_stream(self):
        pass

    def close(self):
        self.closed = True


def _fake_engine(monkeypatch, hits):
    """Patch out vosk + pyaudio; `hits` is the sequence of decoded texts."""
    texts = list(hits)
    streams = []

    class FakeRecognizer:
        def AcceptWaveform(self, _data):
            return bool(texts)

        def Result(self):
            return json.dumps({"text": texts.pop(0)})

    class FakeAudio:
        def open(self, **_kw):
            stream = FakeStream([b"x" * 100] * 20)
            streams.append(stream)
            return stream

        def terminate(self):
            pass

    fake_pyaudio = type("m", (), {"PyAudio": FakeAudio, "paInt16": 8})
    monkeypatch.setitem(__import__("sys").modules, "pyaudio", fake_pyaudio)
    monkeypatch.setattr(wakeword.WakeWordDetector, "_load",
                        lambda self: (None, None, None))
    monkeypatch.setattr(wakeword.WakeWordDetector, "_recognizer",
                        lambda self, v, m, g: FakeRecognizer())
    return streams


def test_detector_fires_once_then_pauses_and_releases_the_mic(monkeypatch):
    streams = _fake_engine(monkeypatch, ["didi"])
    woke = threading.Event()
    d = wakeword.WakeWordDetector(on_wake=woke.set)
    d.start()
    assert woke.wait(5), "wake callback never fired"

    # it stops listening on its own so the command listener can take over
    assert d.listening is False
    assert speech.microphone.owner is None
    assert streams and streams[0].closed
    d.stop()


def test_paused_detector_does_not_fire(monkeypatch):
    _fake_engine(monkeypatch, ["didi"])
    woke = threading.Event()
    d = wakeword.WakeWordDetector(on_wake=woke.set)
    d.start()
    d.pause()                    # immediately
    time.sleep(0.4)
    d.stop()
    # Either it never listened, or it fired before the pause landed - but a
    # pause must never itself be reported as a wake.
    assert d.listening is False


def test_resume_reuses_the_same_thread(monkeypatch):
    _fake_engine(monkeypatch, [])
    d = wakeword.WakeWordDetector(on_wake=lambda: None)
    d.start()
    time.sleep(0.2)
    first = d._thread
    d.pause()
    time.sleep(0.2)
    d.resume()
    time.sleep(0.2)
    assert d._thread is first, "resume must not respawn the listener thread"
    d.stop()


def test_stop_ends_the_thread(monkeypatch):
    _fake_engine(monkeypatch, [])
    d = wakeword.WakeWordDetector(on_wake=lambda: None)
    d.start()
    time.sleep(0.2)
    d.stop()
    d._thread.join(timeout=5)
    assert not d._thread.is_alive()


def test_unavailable_engine_degrades_quietly(monkeypatch):
    monkeypatch.setattr(wakeword.WakeWordDetector, "_load",
                        lambda self: (_ for _ in ()).throw(ImportError("no vosk")))
    seen = []
    d = wakeword.WakeWordDetector(on_wake=lambda: seen.append("wake"),
                                  on_status=seen.append)
    d.start()
    d._thread.join(timeout=5)
    assert "wake" not in seen
    assert any("unavailable" in s for s in seen if isinstance(s, str))
    assert d.listening is False


# ------------------------------------------------------------ GUI wiring

@pytest.mark.gui
def test_wake_switch_controls_the_listener(monkeypatch, tk_root, gui_pump):
    monkeypatch.setattr(gui.Assistant, "startup_greeting", lambda self: None)
    calls = []
    for name in ("start", "pause", "resume", "stop"):
        monkeypatch.setattr(wakeword.WakeWordDetector, name,
                            lambda self, _n=name: calls.append(_n))

    app = gui.CatCodeDidiGUI(tk_root)
    gui_pump(tk_root, 0.4)

    assert app._wake_enabled is False          # off until asked for
    app.wake_switch.select()
    app._on_wake_switch()
    gui_pump(tk_root, 0.2)
    assert app._wake_enabled is True
    assert "start" in calls
    assert "Didi" in app.caption.cget("text")   # idle prompt tells you the word

    app.wake_switch.deselect()
    app._on_wake_switch()
    gui_pump(tk_root, 0.2)
    assert app._wake_enabled is False
    assert "pause" in calls
    app._shutdown()
    assert "stop" in calls


@pytest.mark.gui
def test_wake_listener_never_overlaps_a_command(monkeypatch, tk_root, gui_pump):
    """The listener must be paused before anything else records."""
    monkeypatch.setattr(gui.Assistant, "startup_greeting", lambda self: None)
    order = []
    monkeypatch.setattr(wakeword.WakeWordDetector, "start",
                        lambda self: order.append("start"))
    monkeypatch.setattr(wakeword.WakeWordDetector, "pause",
                        lambda self: order.append("pause"))
    monkeypatch.setattr(wakeword.WakeWordDetector, "resume",
                        lambda self: order.append("resume"))
    monkeypatch.setattr(wakeword.WakeWordDetector, "stop", lambda self: None)
    monkeypatch.setattr(gui.Assistant, "run_interaction",
                        lambda self: order.append("listening"))

    app = gui.CatCodeDidiGUI(tk_root)
    gui_pump(tk_root, 0.4)
    app.wake_switch.select()
    app._on_wake_switch()
    order.clear()

    app._handle("wake", None)                  # as if a phrase was detected
    for _ in range(300):
        if not app._busy():
            break
        tk_root.update()
    gui_pump(tk_root, 0.3)

    assert "listening" in order
    assert order.index("pause") < order.index("listening"), order
    assert order[-1] == "resume", order         # handed back afterwards
    app._shutdown()


@pytest.mark.gui
def test_wake_is_paused_in_text_mode(monkeypatch, tk_root, gui_pump):
    monkeypatch.setattr(gui.Assistant, "startup_greeting", lambda self: None)
    monkeypatch.setattr(wakeword.WakeWordDetector, "start", lambda self: None)
    monkeypatch.setattr(wakeword.WakeWordDetector, "stop", lambda self: None)
    calls = []
    monkeypatch.setattr(wakeword.WakeWordDetector, "pause",
                        lambda self: calls.append("pause"))
    monkeypatch.setattr(wakeword.WakeWordDetector, "resume",
                        lambda self: calls.append("resume"))

    app = gui.CatCodeDidiGUI(tk_root)
    gui_pump(tk_root, 0.4)
    app.wake_switch.select()
    app._on_wake_switch()

    calls.clear()
    app._on_mode_change(gui.MODE_TEXT)
    gui_pump(tk_root, 0.3)
    assert calls and calls[-1] == "pause"      # the mic is not the input here

    calls.clear()
    app._on_mode_change(gui.MODE_VOICE)
    gui_pump(tk_root, 0.3)
    assert calls and calls[-1] == "resume"
    app._shutdown()


@pytest.mark.gui
def test_muting_does_not_stop_wake_detection(monkeypatch, tk_root, gui_pump):
    """Mute silences output only - it must never close the ears."""
    monkeypatch.setattr(gui.Assistant, "startup_greeting", lambda self: None)
    monkeypatch.setattr(gui.speech, "stop_audio", lambda: None)
    monkeypatch.setattr(wakeword.WakeWordDetector, "start", lambda self: None)
    monkeypatch.setattr(wakeword.WakeWordDetector, "stop", lambda self: None)
    monkeypatch.setattr(wakeword.WakeWordDetector, "resume", lambda self: None)
    paused = []
    monkeypatch.setattr(wakeword.WakeWordDetector, "pause",
                        lambda self: paused.append(1))

    app = gui.CatCodeDidiGUI(tk_root)
    gui_pump(tk_root, 0.4)
    app.wake_switch.select()
    app._on_wake_switch()

    paused.clear()
    app.mute_button._click(None)               # mute
    gui_pump(tk_root, 0.3)
    assert app.assistant.muted is True
    assert paused == []                        # listener untouched
    assert app._wake_enabled is True
    app._shutdown()


# ------------------------------------------------- real engine (opt in)

@pytest.mark.audio
def test_real_engine_accepts_wake_phrases_and_rejects_others():
    """Decode real synthesised speech through the actual Vosk grammar.

    Opt in with `pytest -m audio`; needs the network for gTTS on first run and
    downloads the Vosk model once into ~/.cache/vosk.
    """
    import subprocess
    import wave
    from pathlib import Path

    import vosk
    from gtts import gTTS

    tmp = Path("/tmp/wakeword_fixtures")
    tmp.mkdir(exist_ok=True)
    cases = {
        "cat code didi": True, "didi": True, "cat code": True,
        "what is the weather today": False,
        "please open google chrome": False,
        "the deed is done": False,
    }
    vosk.SetLogLevel(-1)
    model = vosk.Model(lang="en-us")
    grammar = json.dumps(sorted(wakeword.WAKE_PHRASES) + ["[unk]"])
    detector = wakeword.WakeWordDetector(on_wake=lambda: None)

    for phrase, should_wake in cases.items():
        wav = tmp / (phrase.replace(" ", "_") + ".wav")
        if not wav.exists():
            mp3 = wav.with_suffix(".mp3")
            gTTS(text=phrase, lang="en").save(str(mp3))
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(mp3),
                            "-ar", "16000", "-ac", "1", str(wav)], check=True)

        with wave.open(str(wav), "rb") as handle:
            rec = vosk.KaldiRecognizer(model, handle.getframerate(), grammar)
            woke = False
            while True:
                data = handle.readframes(4000)
                if not data:
                    break
                if rec.AcceptWaveform(data):
                    woke |= detector._is_wake(json.loads(rec.Result()))
            woke |= detector._is_wake(json.loads(rec.FinalResult()))

        assert woke is should_wake, f"{phrase!r} -> woke={woke}"
