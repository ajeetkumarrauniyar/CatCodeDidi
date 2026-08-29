"""Command router: turn recognised text into a response + activity entries.

`classify()` is a cheap, side-effect-free peek used by the GUI to show a
"what am I doing" caption. `route()` actually performs the action.
Neither speaks nor touches the GUI.
"""

from dataclasses import dataclass, field

from commands import (
    handle_close_command,
    handle_open_command,
    is_father_query,
    take_screenshot,
)
from data import exit_commands
from gemini_ai import GeminiError, ask_gemini

FATHER_ANSWER = "Mere Papa Anant Hai!"
EXIT_REPLY = "Good Bye, Maalik!, Sulululu"


@dataclass
class RouteResult:
    user_text: str
    response_text: str = ""
    activity: list = field(default_factory=list)   # list of (kind, text)
    is_exit: bool = False


def classify(said):
    """Return (kind, target) without doing anything. kind is one of:
    open | close | screenshot | creator | exit | ai."""
    words = said.split()
    if not words:
        return "ai", None
    if is_father_query(said):
        return "creator", None
    if said.strip().lower() in exit_commands:
        return "exit", None
    verb = words[0].lower()
    if len(words) > 1 and verb in ("open", "close"):
        return verb, " ".join(words[1:])
    if "screenshot" in (w.lower() for w in words):
        return "screenshot", None
    return "ai", None


def route(said):
    """Route recognised speech to the right handler and return a RouteResult."""
    result = RouteResult(user_text=said)
    kind, target = classify(said)

    if kind == "creator":
        result.response_text = FATHER_ANSWER
        result.activity.append(("ok", "Answered a question about the creator"))
        return result

    if kind == "exit":
        result.response_text = EXIT_REPLY
        result.is_exit = True
        result.activity.append(("info", "Exit command received"))
        return result

    if kind in ("open", "close"):
        handler = handle_open_command if kind == "open" else handle_close_command
        command_result = handler(target)
        result.response_text = command_result.speech
        result.activity.append(
            (kind if command_result.ok else "warn", command_result.log)
        )
        return result

    if kind == "screenshot":
        command_result = take_screenshot()
        result.response_text = command_result.speech
        result.activity.append(
            ("shot" if command_result.ok else "warn", command_result.log)
        )
        return result

    # Everything else -> Gemini.
    result.activity.append(("ai", "Asked Gemini"))
    try:
        result.response_text = ask_gemini(said)
        result.activity.append(("ai", "Gemini replied"))
    except GeminiError as error:
        result.response_text = str(error)          # short, safe, no secrets
        result.activity.append(("warn", f"Gemini unavailable — {error}"))
    except Exception as error:
        result.response_text = "Maalik, Gemini se abhi baat nahi ho pa rahi."
        result.activity.append(("warn", f"Gemini error ({type(error).__name__})"))
    return result
