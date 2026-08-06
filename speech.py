"""Speech input and output for the voice assistant."""

import os
import tempfile

import playsound3
import speech_recognition as sr
from gtts import gTTS

from config import LANGUAGE


def play_audio(file_path):
    """Play an audio file through the current playback library."""
    playsound3.playsound(file_path)


def bot_speak(text):
    """Convert text to Hindi speech, play it, and clean up the temporary file."""
    temp_file_path = None
    try:
        # Create a unique temporary MP3, then close it so Windows can write to it.
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio:
            temp_file_path = temp_audio.name

        tts = gTTS(text=text, lang=LANGUAGE)
        tts.save(temp_file_path)
        play_audio(temp_file_path)
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


def voice_input():
    """Listen through the microphone and return the recognized speech."""
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("\n Listening...")
        audio = recognizer.listen(source)
        said = ""
        try:
            said = recognizer.recognize_google(audio)
            print(said)
        except (sr.UnknownValueError, sr.RequestError):
            bot_speak("Maalik, Phir se boliye mai sun nahi paa rahi hu!")
    return said