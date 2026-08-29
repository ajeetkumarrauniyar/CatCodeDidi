"""Assistant orchestration: the 'brain' that runs one voice interaction.

The GUI is a presentation layer on top of this. Progress is reported through
the `emit` callback (see gui.py for the event vocabulary). All methods here
block and are expected to run off the UI thread.
"""

import gemini_ai
import router
import speech
from config import BOT_NAME
from personality import greeting

STATE_READY = "Ready"
STATE_LISTENING = "Listening..."
STATE_PROCESSING = "Processing..."
STATE_SPEAKING = "Speaking..."
STATE_ERROR = "Error"

_STATUS_BY_KIND = {
    "open": "Opening {target}…",
    "close": "Closing {target}…",
    "screenshot": "Taking a screenshot…",
    "creator": "One moment…",
    "exit": "Wrapping up…",
    "ai": "Thinking…",
}


class Assistant:
    def __init__(self, emit):
        self._emit = emit

    # -- helpers ---------------------------------------------------------

    def _speak(self, text):
        """Speak text. The caller has already shown it in the GUI, so a TTS
        failure is only logged - the response stays visible."""
        self._emit("state", STATE_SPEAKING)
        self._emit("status", "Speaking…")
        try:
            speech.bot_speak(speech.clean_for_speech(text))
        except Exception as error:
            self._emit("activity", ("warn", f"Voice playback failed ({type(error).__name__})"))

    # -- entry points --------------------------------------------------

    def startup_greeting(self):
        """Greet once at launch and warm up the Gemini SDK off the UI thread."""
        if gemini_ai.is_configured():
            self._emit("activity", ("ai", f"Gemini ready · {gemini_ai.model_name()}"))
            gemini_ai.prewarm()
        else:
            self._emit("activity", ("info", "No Gemini key · local commands only"))
        text = greeting()
        self._emit("message", (BOT_NAME, text))
        self._speak(text)
        self._emit("state", STATE_READY)

    def run_interaction(self):
        """Run one listen -> understand -> act -> respond -> speak cycle."""
        self._emit("state", STATE_LISTENING)
        self._emit("status", "Listening…")
        heard = speech.recognize_once()

        if not heard.ok:
            self._emit("state", STATE_ERROR)
            self._emit("activity", ("warn", "Speech not recognised"))
            self._emit("error", (heard.error_title or "Didn't catch that",
                                 heard.error or "Please try again."))
            self._emit("state", STATE_READY)
            return

        self._emit("transcript", heard.text)
        self._emit("state", STATE_PROCESSING)

        kind, target = router.classify(heard.text)
        self._emit("status", _STATUS_BY_KIND.get(kind, "Working…").format(target=target or ""))

        result = router.route(heard.text)
        for kind_text in result.activity:
            self._emit("activity", kind_text)

        if result.response_text:
            self._emit("message", (BOT_NAME, result.response_text))
            self._speak(result.response_text)

        self._emit("state", STATE_READY)
        if result.is_exit:
            self._emit("exit", None)
