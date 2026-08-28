"""Speech input and output for the voice assistant.

Cross-platform notes:
- Microphone capture goes through SpeechRecognition + PyAudio (PortAudio).
- Recognition uses Google's free web API, so it needs an internet connection.
- Text-to-speech uses gTTS (also online) and playsound3 for playback, which
  picks a working audio backend on Windows, macOS and Linux.
"""

import re
import tempfile
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


@dataclass
class RecognitionResult:
    """Outcome of a single microphone listen + recognition attempt."""

    text: str = ""
    error: str = ""

    @property
    def ok(self):
        return bool(self.text) and not self.error


def clean_for_speech(text):
    """Strip Markdown punctuation that sounds wrong when read aloud."""
    return re.sub(r"[*:;/\\|`#]", "", text)


def play_audio(file_path):
    """Play an audio file through a platform-appropriate backend."""
    playsound3.playsound(str(file_path))


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


def recognize_once():
    """Listen through the microphone once and return a RecognitionResult.

    Unlike voice_input(), this never speaks on failure; the caller decides how
    to surface the error. Every failure mode returns a friendly message instead
    of raising.
    """
    if not _has_microphone():
        return RecognitionResult(error="Koi microphone nahi mila. Ek mic connect kijiye.")

    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.4)
            audio = recognizer.listen(
                source, timeout=LISTEN_TIMEOUT, phrase_time_limit=PHRASE_TIME_LIMIT
            )
    except sr.WaitTimeoutError:
        return RecognitionResult(error="Kuch sunai nahi diya. Mic button dabaakar phir boliye.")
    except OSError as error:
        return RecognitionResult(error=f"Microphone use nahi ho pa raha: {error}")
    except Exception as error:  # PortAudio / permission errors vary by platform
        return RecognitionResult(error=f"Microphone error: {error}")

    try:
        return RecognitionResult(text=recognizer.recognize_google(audio))
    except sr.UnknownValueError:
        return RecognitionResult(error="Samajh nahi aaya, phir se boliye.")
    except sr.RequestError as error:
        return RecognitionResult(error=f"Speech service se connect nahi ho paya: {error}")


def voice_input():
    """Listen once and return the recognized text (console flow)."""
    print("\n Listening...")
    result = recognize_once()
    if result.ok:
        print(f"You: {result.text}")
        return result.text
    bot_speak("Maalik, Phir se boliye mai sun nahi paa rahi hu!")
    return ""
