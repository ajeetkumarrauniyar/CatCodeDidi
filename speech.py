"""Speech input and output for the voice assistant."""

import playsound3
import speech_recognition as sr
from gtts import gTTS

if __package__:
    from .config import LANGUAGE, VOICE_FILE
else:
    from config import LANGUAGE, VOICE_FILE


def bot_speak(text):
    """Convert text to Hindi speech and play it."""
    tts = gTTS(text=text, lang=LANGUAGE)
    tts.save(VOICE_FILE)
    playsound3.playsound(VOICE_FILE)


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