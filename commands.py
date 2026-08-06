"""Local desktop command handlers."""

from AppOpener import close as close_application
from AppOpener import open as open_application
from data import FATHER_RELATED_QUESTIONS
from speech import bot_speak


def handle_open_command(app_name):
    """Open an application and report the outcome."""
    try:
        open_application(app_name, match_closest=True, throw_error=True)
        bot_speak(f"Thik hai Maalik! , Mai {app_name} ko open kar deti hu")
    except Exception:
        bot_speak(f"Maalik, {app_name} naam ka koi software hai hi nahi system mai!")


def handle_close_command(app_name):
    """Close an application and report the outcome."""
    try:
        close_application(app_name, match_closest=True)
        bot_speak(f"Maalik, {app_name} Ko Band Kar deti hu !")
    except Exception:
        bot_speak(f"Maalik, {app_name} naam ka koi software open nahi hai toh chinta mat kijiye")


def is_father_query(command):
    """Return whether command is a supported creator query."""
    return command.strip().casefold() in FATHER_RELATED_QUESTIONS