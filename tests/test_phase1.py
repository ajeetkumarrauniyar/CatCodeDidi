"""Phase 1 command-routing tests without audio or desktop side effects."""

import importlib
import sys
import types
import unittest
from unittest.mock import patch


def install_external_dependency_stubs():
    app_opener = types.ModuleType("AppOpener")
    app_opener.open = lambda *args, **kwargs: None
    app_opener.close = lambda *args, **kwargs: None
    sys.modules.setdefault("AppOpener", app_opener)

    playsound = types.ModuleType("playsound3")
    playsound.playsound = lambda *args, **kwargs: None
    sys.modules.setdefault("playsound3", playsound)

    recognition = types.ModuleType("speech_recognition")
    recognition.UnknownValueError = type("UnknownValueError", (Exception,), {})
    recognition.RequestError = type("RequestError", (Exception,), {})
    recognition.Recognizer = object
    recognition.Microphone = object
    sys.modules.setdefault("speech_recognition", recognition)

    gtts = types.ModuleType("gtts")
    gtts.gTTS = object
    sys.modules.setdefault("gtts", gtts)


install_external_dependency_stubs()
commands = importlib.import_module("commands")
main = importlib.import_module("main")


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