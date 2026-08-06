"""Greeting boundary tests."""

import datetime
import unittest
from unittest.mock import patch

import personality


class FrozenDateTime(datetime.datetime):
    current_time = datetime.datetime(2026, 1, 1)

    @classmethod
    def now(cls, tz=None):
        return cls.current_time


class PersonalityTests(unittest.TestCase):
    def test_greeting_time_ranges(self):
        cases = (
            (6, "Good Morning Sir, Abhi Subah ke 6 baj rahe hai!"),
            (11, "Good Morning Sir, Abhi Subah ke 11 baj rahe hai!"),
            (12, "Good Afternoon Sir, Abhi Dophar ke 12 baj rahe hai!"),
            (13, "Good Afternoon Sir, Abhi Dophar ke 1 baj rahe hai!"),
            (17, "Good Evening Sir, Abhi Shaam ke 5 baj rahe hai!"),
            (18, "Hello Night Owl, Abhi Raat ke 6 baj rahe hai !"),
        )

        for hour, expected_message in cases:
            with self.subTest(hour=hour):
                FrozenDateTime.current_time = datetime.datetime(2026, 1, 1, hour)
                with patch.object(personality.datetime, "datetime", FrozenDateTime), patch.object(personality, "bot_speak") as bot_speak:
                    personality.greet_user()

                bot_speak.assert_called_once_with(expected_message)


if __name__ == "__main__":
    unittest.main()