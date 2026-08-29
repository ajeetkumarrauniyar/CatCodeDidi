import speech_recognition as sr

import speech


def test_clean_for_speech_strips_markdown():
    # each of  * : ; / \ | ` #  is deleted (they sound wrong read aloud)
    assert speech.clean_for_speech("**bold** text") == "bold text"
    assert speech.clean_for_speech("note: it works; ok") == "note it works ok"
    for ch in "*:;/\\|`#":
        assert ch not in speech.clean_for_speech(f"a{ch}b")


def test_recognition_result_ok():
    assert speech.RecognitionResult(text="hi").ok is True
    assert speech.RecognitionResult(error="bad").ok is False
    assert speech.RecognitionResult().ok is False


def test_bot_speak_ignores_empty(monkeypatch):
    called = []
    monkeypatch.setattr(speech, "gTTS", lambda **kw: called.append(kw))
    speech.bot_speak("   ")
    assert called == []


def test_recognize_once_no_microphone(monkeypatch):
    monkeypatch.setattr(speech, "_has_microphone", lambda: False)
    r = speech.recognize_once()
    assert not r.ok
    assert r.error_title == "No microphone found"


def test_recognize_once_permission_error(monkeypatch):
    monkeypatch.setattr(speech, "_has_microphone", lambda: True)

    class DeniedMic:
        def __enter__(self):
            raise OSError("Internal PortAudio error -9986: permission denied")

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(speech.sr, "Microphone", lambda *a, **k: DeniedMic())
    r = speech.recognize_once()
    assert r.error_title == "Microphone access needed"
    assert "System Settings" in r.error or "Settings" in r.error


def test_recognize_once_timeout(monkeypatch):
    monkeypatch.setattr(speech, "_has_microphone", lambda: True)

    class Mic:
        def __enter__(self):
            return "src"

        def __exit__(self, *a):
            return False

    class Rec:
        def adjust_for_ambient_noise(self, *a, **k):
            pass

        def listen(self, *a, **k):
            raise sr.WaitTimeoutError()

    monkeypatch.setattr(speech.sr, "Microphone", lambda *a, **k: Mic())
    monkeypatch.setattr(speech.sr, "Recognizer", lambda: Rec())
    r = speech.recognize_once()
    assert r.error_title == "Didn't hear anything"


def test_recognize_once_unknown_value(monkeypatch):
    monkeypatch.setattr(speech, "_has_microphone", lambda: True)

    class Mic:
        def __enter__(self):
            return "src"

        def __exit__(self, *a):
            return False

    class Rec:
        def adjust_for_ambient_noise(self, *a, **k):
            pass

        def listen(self, *a, **k):
            return "audio"

        def recognize_google(self, audio):
            raise sr.UnknownValueError()

    monkeypatch.setattr(speech.sr, "Microphone", lambda *a, **k: Mic())
    monkeypatch.setattr(speech.sr, "Recognizer", lambda: Rec())
    r = speech.recognize_once()
    assert r.error_title == "Didn't catch that"


def test_recognize_once_success(monkeypatch):
    monkeypatch.setattr(speech, "_has_microphone", lambda: True)

    class Mic:
        def __enter__(self):
            return "src"

        def __exit__(self, *a):
            return False

    class Rec:
        def adjust_for_ambient_noise(self, *a, **k):
            pass

        def listen(self, *a, **k):
            return "audio"

        def recognize_google(self, audio):
            return "open google chrome"

    monkeypatch.setattr(speech.sr, "Microphone", lambda *a, **k: Mic())
    monkeypatch.setattr(speech.sr, "Recognizer", lambda: Rec())
    r = speech.recognize_once()
    assert r.ok and r.text == "open google chrome"
