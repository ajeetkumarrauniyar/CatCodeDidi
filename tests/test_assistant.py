import assistant
import speech


class Recorder:
    def __init__(self):
        self.events = []

    def __call__(self, kind, payload):
        self.events.append((kind, payload))

    def kinds(self):
        return [k for k, _ in self.events]

    def first(self, kind):
        return next(p for k, p in self.events if k == kind)


def _quiet(monkeypatch):
    monkeypatch.setattr(assistant.speech, "bot_speak", lambda text: None)
    monkeypatch.setattr(assistant.speech, "clean_for_speech", lambda t: t)


def test_run_interaction_happy_path(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(assistant.speech, "recognize_once",
                        lambda: speech.RecognitionResult(text="open safari"))
    monkeypatch.setattr(assistant.router, "classify", lambda t: ("open", "safari"))
    monkeypatch.setattr(assistant.router, "route",
                        lambda t: assistant.router.RouteResult(
                            user_text=t, response_text="Opening safari",
                            activity=[("open", "Opened safari")]))
    rec = Recorder()
    assistant.Assistant(rec).run_interaction()

    assert ("transcript", "open safari") in rec.events
    assert ("message", ("CatCodeDidi", "Opening safari")) in rec.events
    assert ("activity", ("open", "Opened safari")) in rec.events
    # ends back at Ready
    assert rec.kinds()[-1] == "state" and rec.events[-1][1] == assistant.STATE_READY
    assert "exit" not in rec.kinds()


def test_run_interaction_recognition_failure_emits_error_card(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(assistant.speech, "recognize_once",
                        lambda: speech.RecognitionResult(
                            error_title="Microphone access needed",
                            error="Enable it in settings."))
    rec = Recorder()
    assistant.Assistant(rec).run_interaction()

    assert ("error", ("Microphone access needed", "Enable it in settings.")) in rec.events
    assert "transcript" not in rec.kinds()
    assert "message" not in rec.kinds()
    assert rec.events[-1] == ("state", assistant.STATE_READY)


def test_run_interaction_exit(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(assistant.speech, "recognize_once",
                        lambda: speech.RecognitionResult(text="shutdown"))
    monkeypatch.setattr(assistant.router, "classify", lambda t: ("exit", None))
    monkeypatch.setattr(assistant.router, "route",
                        lambda t: assistant.router.RouteResult(
                            user_text=t, response_text="bye", is_exit=True))
    rec = Recorder()
    assistant.Assistant(rec).run_interaction()
    assert rec.events[-1] == ("exit", None)


def test_speak_failure_is_logged_not_raised(monkeypatch):
    def boom(text):
        raise RuntimeError("no audio device")
    monkeypatch.setattr(assistant.speech, "bot_speak", boom)
    monkeypatch.setattr(assistant.speech, "clean_for_speech", lambda t: t)
    rec = Recorder()
    assistant.Assistant(rec)._speak("hello")          # must not raise
    assert any(k == "activity" and p[0] == "warn" for k, p in rec.events)


def test_startup_greeting_without_key(monkeypatch):
    _quiet(monkeypatch)
    monkeypatch.setattr(assistant.gemini_ai, "is_configured", lambda: False)
    monkeypatch.setattr(assistant, "greeting", lambda: "Namaste")
    rec = Recorder()
    assistant.Assistant(rec).startup_greeting()
    assert any(k == "activity" and "No Gemini key" in p[1] for k, p in rec.events)
    assert ("message", ("CatCodeDidi", "Namaste")) in rec.events
