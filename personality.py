"""Personality responses for the voice assistant."""

import datetime

from speech import bot_speak


def greet_user():
    """Speak the original time-based greeting."""
    current_time = int(datetime.datetime.now().strftime("%H"))
    if current_time <= 5:
        bot_speak(f"Good Morning Sir, Abhi Subah ke {current_time} baj rahe hai!")
    elif current_time == 12:
        bot_speak("Good Afternoon Sir, Abhi Dophar ke 12 baj rahe hai!")
    elif current_time <= 13:
        bot_speak(f"Good Afternoon Sir, Abhi Dophar ke {current_time - 12} baj rahe hai!")
    elif current_time <= 17:
        bot_speak(f"Good Evening Sir, Abhi Shaam ke {current_time - 12} baj rahe hai!")
    else:
        bot_speak(f"Hello Night Owl, Abhi Raat ke {current_time - 12} baj rahe hai !")