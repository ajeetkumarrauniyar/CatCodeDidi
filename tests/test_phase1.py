"""Phase 1 command-routing tests without audio or desktop side effects."""

import unittest
from unittest.mock import patch

import commands
import main


class PhaseOneTests(unittest.TestCase):
    def test_father_query_ignores_case_and_outer_whitespace(self):
        self.assertTrue(commands.is_father_query("  WHO IS YOUR FATHER  "))
        self.assertFalse(commands.is_father_query("who is your mother"))

    def test_open_command_preserves_multi_word_application_name(self):
        with (
            patch.object(main, "greet_user"),
            patch.object(main, "voice_input", side_effect=["open Google Chrome", "shutdown"]),
            patch.object(main, "handle_open_command") as open_command,
            patch.object(main, "bot_speak"),
        ):
            main.main()

        open_command.assert_called_once_with("Google Chrome")


if __name__ == "__main__":
    unittest.main()