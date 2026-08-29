"""CatCodeDidi entry point - console assistant.

Bootstraps logging and runs the assistant loop on the terminal. All the work
happens in the service layer; this file only wires it up and prints what comes
back.

    main.py  ->  assistant  ->  router  ->  commands | gemini_ai
                     |                          |
                   speech                  personality / data

`Assistant` reports progress through an `emit(kind, payload)` callback rather
than printing directly, so the very same pipeline can be driven by any front
end without touching the services.
"""

import logging
import sys

from assistant import Assistant, STATE_LISTENING
from config import BOT_NAME

MIN_PYTHON = (3, 10)

log = logging.getLogger("catcodedidi")


def _render(kind, payload):
    """Turn one assistant event into terminal output."""
    if kind == "transcript":
        print(f"\nYou\n  {payload}")
    elif kind == "message":
        speaker, text = payload
        print(f"\n{speaker}\n  {text}")
    elif kind == "error":
        title, body = payload
        print(f"\n{title}\n  {body}")
    elif kind == "activity":
        level, text = payload
        log.warning("%s", text) if level == "warn" else log.info("%s", text)
    elif kind == "state" and payload == STATE_LISTENING:
        print("\nListening...")


def _check_python():
    if sys.version_info < MIN_PYTHON:
        raise SystemExit(
            f"CatCodeDidi needs Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer; "
            f"this is {sys.version.split()[0]} at {sys.executable}"
        )


def main():
    """Greet once, then listen and respond until the user says goodbye."""
    _check_python()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )

    finished = []
    def emit(kind, payload):
        _render(kind, payload)
        if kind == "exit":
            finished.append(True)

    assistant = Assistant(emit)
    print(f"{BOT_NAME} - press Ctrl-C to quit\n")
    assistant.startup_greeting()

    try:
        while not finished:
            assistant.run_interaction()
    except KeyboardInterrupt:
        print("\nGoodbye!")


if __name__ == "__main__":
    main()
