"""Speech output tests without network or audio-device side effects."""

import importlib
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


def install_external_dependency_stubs():
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
speech = importlib.import_module("speech")


class SpeechTests(unittest.TestCase):
    def test_bot_speak_removes_temporary_audio_after_playback(self):
        tts = MagicMock()
        with patch.object(speech, "gTTS", return_value=tts), patch.object(speech, "play_audio") as play_audio:
            speech.bot_speak("Namaste")

        temp_file_path = tts.save.call_args.args[0]
        play_audio.assert_called_once_with(temp_file_path)
        self.assertFalse(os.path.exists(temp_file_path))

    def test_bot_speak_removes_temporary_audio_when_playback_fails(self):
        tts = MagicMock()
        with patch.object(speech, "gTTS", return_value=tts), patch.object(speech, "play_audio", side_effect=RuntimeError("Playback failed")):
            with self.assertRaisesRegex(RuntimeError, "Playback failed"):
                speech.bot_speak("Namaste")

        temp_file_path = tts.save.call_args.args[0]
        self.assertFalse(os.path.exists(temp_file_path))


if __name__ == "__main__":
    unittest.main()