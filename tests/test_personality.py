import datetime

import pytest

import personality


def at(hour, minute=0):
    return datetime.datetime(2026, 8, 29, hour, minute)


@pytest.mark.parametrize("hour, hello, part", [
    (5, "Good Morning", "Subah"),
    (8, "Good Morning", "Subah"),
    (11, "Good Morning", "Subah"),
    (12, "Good Afternoon", "Dopahar"),
    (15, "Good Afternoon", "Dopahar"),
    (16, "Good Afternoon", "Dopahar"),
    (17, "Good Evening", "Shaam"),
    (20, "Good Evening", "Shaam"),
    (21, "Night Owl", "Raat"),
    (23, "Night Owl", "Raat"),
    (0, "Night Owl", "Raat"),
    (4, "Night Owl", "Raat"),
])
def test_greeting_day_part(hour, hello, part):
    text = personality.greeting(at(hour))
    assert hello in text
    assert part in text


@pytest.mark.parametrize("hour, minute, expected", [
    (10, 33, "10 baj kar 33 minute ho rahe hai"),
    (10, 0, "10 baj rahe hai"),
    (10, 15, "sawa 10 baj rahe hai"),
    (10, 30, "sadhe 10 baj rahe hai"),
    (10, 45, "paune 11 baj rahe hai"),
    (1, 30, "dedh baj rahe hai"),         # not "sadhe 1"
    (2, 30, "dhai baj rahe hai"),         # not "sadhe 2"
    (11, 45, "paune 12 baj rahe hai"),
    (23, 45, "paune 12 baj rahe hai"),
    (12, 0, "12 baj rahe hai"),
    (0, 0, "12 baj rahe hai"),            # midnight reads as 12, never 0
    (13, 5, "1 baj kar 5 minute ho rahe hai"),
    (23, 59, "11 baj kar 59 minute ho rahe hai"),
])
def test_time_phrase(hour, minute, expected):
    assert personality.time_phrase(at(hour, minute)) == expected


def test_minutes_are_not_dropped():
    """Regression: 10:33 used to announce a bare '10'."""
    assert "33" in personality.greeting(at(10, 33))


@pytest.mark.parametrize("hour", range(24))
def test_greeting_never_says_a_negative_or_zero_hour(hour):
    """Regression: hours 0-4 used to render as '-12' .. '-8' via hour - 12."""
    for minute in (0, 7, 15, 30, 45):
        text = personality.greeting(at(hour, minute))
        assert "-" not in text
        assert " 0 " not in text


@pytest.mark.parametrize("hour", range(24))
def test_twelve_hour_conversion_in_range(hour):
    assert 1 <= personality._twelve_hour(hour) <= 12


def test_greeting_uses_current_time_by_default():
    assert isinstance(personality.greeting(), str)
    assert personality.greeting()
