"""Speech output tests without network or audio-device side effects."""

import os
import unittest
from unittest.mock import MagicMock, patch

import speech


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