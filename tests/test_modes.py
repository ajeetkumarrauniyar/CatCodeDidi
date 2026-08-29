"""Voice Mode / Text Mode: the input method changes, nothing else does."""

import assistant as assistant_mod
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









