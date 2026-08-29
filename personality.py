"""Personality responses for the voice assistant."""

import datetime

from speech import bot_speak

# (first hour, last hour inclusive) -> (English greeting, Hindi day part)
_DAY_PARTS = (
    (5, 11, "Good Morning Sir", "Subah"),
    (12, 16, "Good Afternoon Sir", "Dopahar"),
    (17, 20, "Good Evening Sir", "Shaam"),
)
_NIGHT = ("Hello Night Owl", "Raat")

# Halves that have their own word in Hindi: 1:30 is "dedh", 2:30 is "dhai".
_HALF_WORDS = {1: "dedh", 2: "dhai"}


def _twelve_hour(hour):
    """24-hour clock -> 12-hour clock (0 and 12 both read as 12)."""
    return hour % 12 or 12


def time_phrase(now=None):
    """Spoken Hindi phrase for the time, e.g. '10 baj kar 33 minute'.

    Quarters use the natural Hindi words people actually say (sawa / sadhe /
    paune) instead of reading the digits out.
    """
    now = now or datetime.datetime.now()
    hour, minute = now.hour, now.minute
    current = _twelve_hour(hour)
    following = _twelve_hour(hour + 1)

    if minute == 0:
        return f"{current} baj rahe hai"
    if minute == 15:
        return f"sawa {current} baj rahe hai"
    if minute == 30:
        return f"{_HALF_WORDS.get(current, f'sadhe {current}')} baj rahe hai"
    if minute == 45:
        return f"paune {following} baj rahe hai"
    return f"{current} baj kar {minute} minute ho rahe hai"


def greeting(now=None):
    """Return the time-based greeting text."""
    now = now or datetime.datetime.now()
    for first, last, hello, day_part in _DAY_PARTS:
        if first <= now.hour <= last:
            break
    else:
        hello, day_part = _NIGHT

    return f"{hello}, Abhi {day_part} ke {time_phrase(now)}!"


def greet_user():
    """Speak the time-based greeting (console flow)."""
    bot_speak(greeting())
