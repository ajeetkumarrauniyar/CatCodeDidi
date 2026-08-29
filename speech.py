"""Speech input and output for the voice assistant.

Cross-platform notes:
- Microphone capture goes through SpeechRecognition + PyAudio (PortAudio).
- Recognition uses Google's free web API, so it needs an internet connection.
- Text-to-speech uses gTTS (also online) and playsound3 for playback, which
  picks a working audio backend on Windows (WinMM), macOS (afplay) and
  Linux (GStreamer / ffmpeg).
"""

import platform
import re
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import playsound3
import speech_recognition as sr
from gtts import gTTS

from config import LANGUAGE

# Give the user a moment to start talking, and cap a single utterance so a
# silent room can never block the GUI worker forever.
LISTEN_TIMEOUT = 8
PHRASE_TIME_LIMIT = 15

_MIC_HELP = {
    "Darwin": "Open System Settings → Privacy & Security → Microphone and enable "
              "access for your terminal (or the app you launched CatCodeDidi from).",
    "Windows": "Open Settings → Privacy & security → Microphone and allow desktop "
               "apps to use the microphone.",
    "Linux": "Check your sound settings and that PulseAudio / PipeWire can see an "
             "input device.",
}
_MIC_HELP_DEFAULT = "Check your system sound settings and that an input device is available."


def mic_permission_help(system=None):
    """Platform-specific advice for a microphone that will not open."""
    return _MIC_HELP.get(system or platform.system(), _MIC_HELP_DEFAULT)


class MicrophoneBusy(RuntimeError):
    """Raised when something tries to record while another part already is."""


class _MicrophoneOwner:
    """Exactly one component may hold the microphone at a time.

    The wake-word listener and the command listener both record, and two open
    input streams at once produce silence, garbage or a hard PortAudio error
    depending on the platform. The design already hands ownership over rather
    than sharing it; this guard makes a mistake loud instead of mysterious.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._owner = None

    @property
    def owner(self):
        return self._owner

    @contextmanager
    def claim(self, who):
        if not self._lock.acquire(blocking=False):
            raise MicrophoneBusy(
                f"{who} wanted the microphone but {self._owner} is using it")
        self._owner = who
        try:
            yield
        finally:
            self._owner = None
            self._lock.release()


microphone = _MicrophoneOwner()


@dataclass
class RecognitionResult:
    """Outcome of a single microphone listen + recognition attempt."""

    text: str = ""
    error: str = ""
    error_title: str = ""

    @property
    def ok(self):
        return bool(self.text) and not self.error


def clean_for_speech(text):
    """Strip Markdown punctuation that sounds wrong when read aloud."""
    return re.sub(r"[*:;/\\|`#]", "", text)


# The clip currently playing, so another thread (the UI pressing mute) can cut
# it short. playsound3 returns a handle with a supported stop(); we do not
# manage any audio processes ourselves.
_playing = None
_playing_lock = threading.Lock()


def play_audio(file_path):
    """Play an audio file, blocking until it finishes or is stopped."""
    global _playing
    sound = playsound3.playsound(str(file_path), block=False)
    with _playing_lock:
        _playing = sound
    try:
        sound.wait()
    finally:
        with _playing_lock:
            if _playing is sound:
                _playing = None


def stop_audio():
    """Cut off whatever is playing. Safe to call from any thread, and a no-op
    when nothing is playing."""
    with _playing_lock:
        sound = _playing
    if sound is None:
        return
    try:
        sound.stop()
    except Exception:
        pass    # already finished, or the backend cannot be interrupted


def bot_speak(text):
    """Convert text to Hindi speech and play it.

    The temporary MP3 is created with a real filename and closed before gTTS
    writes to it (Windows keeps a lock on open handles), then removed once
    playback finishes or fails.
    """
    text = (text or "").strip()
    if not text:
        return

    temp_path = None
    try:
        handle = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        temp_path = Path(handle.name)
        handle.close()

        gTTS(text=text, lang=LANGUAGE).save(str(temp_path))
        play_audio(temp_path)
    finally:
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def _has_microphone():
    try:
        return bool(sr.Microphone.list_microphone_names())
    except Exception:
        # If we cannot even enumerate devices, let the real listen() attempt
        # surface the specific error.
        return True


def _looks_like_permission_error(error):
    text = str(error).lower()
    return any(s in text for s in ("permission", "denied", "-9986", "access", "not authorized"))


def recognize_once():
    """Listen through the microphone once and return a RecognitionResult.

    Never speaks and never raises: every failure mode becomes a friendly
    (title, message) pair the GUI can present.
    """
    if not _has_microphone():
        return RecognitionResult(
            error_title="No microphone found",
            error="CatCodeDidi couldn't find an input device. Connect a microphone and try again.",
        )

    recognizer = sr.Recognizer()
    try:
        with microphone.claim("command listener"), sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.4)
            audio = recognizer.listen(
                source, timeout=LISTEN_TIMEOUT, phrase_time_limit=PHRASE_TIME_LIMIT
            )
    except MicrophoneBusy:
        return RecognitionResult(
            error_title="Microphone busy",
            error="Something else is using the microphone. Try again in a moment.",
        )
    except sr.WaitTimeoutError:
        return RecognitionResult(
            error_title="Didn't hear anything",
            error="No speech was picked up. Tap the mic and speak clearly.",
        )
    except Exception as error:  # OSError / PortAudio / permission errors vary
        if _looks_like_permission_error(error):
            return RecognitionResult(
                error_title="Microphone access needed",
                error=f"CatCodeDidi can't use the microphone. {mic_permission_help()}",
            )
        return RecognitionResult(
            error_title="Microphone unavailable",
            error=f"The microphone couldn't be opened. {mic_permission_help()}",
        )

    try:
        return RecognitionResult(text=recognizer.recognize_google(audio))
    except sr.UnknownValueError:
        return RecognitionResult(
            error_title="Didn't catch that",
            error="CatCodeDidi couldn't make out the words. Try again in a quieter spot.",
        )
    except sr.RequestError:
        return RecognitionResult(
            error_title="Speech service unreachable",
            error="Couldn't reach the speech-recognition service. Check your internet connection.",
        )


def voice_input():
    """Listen once and return the recognized text (console flow)."""
    print("\n Listening...")
    result = recognize_once()
    if result.ok:
        print(f"You: {result.text}")
        return result.text
    bot_speak("Maalik, Phir se boliye mai sun nahi paa rahi hu!")
    return ""
