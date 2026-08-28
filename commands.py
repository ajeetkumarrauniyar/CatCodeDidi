"""Local desktop command handlers.

Handlers do not speak or touch any UI. Each returns a CommandResult so the
caller (console loop or GUI) decides how to present it. Nothing here raises to
the caller: OS differences and missing apps become CommandResult(ok=False).

Platform strategy for opening / closing apps:
- Windows : AppOpener (fuzzy Start-menu match), imported lazily.
- macOS   : `open -a`, with a fallback that scans /Applications for a close
            name match ("Chrome" -> "Google Chrome"); `osascript` to quit.
- Linux   : look up an executable on PATH and launch it detached; `pkill` to
            close. Desktop names vary widely between distros, so this is
            best-effort and failures are reported, not fatal.
"""

import datetime
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pyscreenshot

from data import FATHER_RELATED_QUESTIONS

_SYSTEM = platform.system()

# Screenshots go in a predictable folder next to the project so the user always
# knows where to look; the path is also reported in the activity log.
SCREENSHOT_DIR = Path.cwd() / "screenshots"

_MAC_APP_DIRS = ("/Applications", "/Applications/Utilities",
                 "/System/Applications", str(Path.home() / "Applications"))


@dataclass
class CommandResult:
    """What a command did: text to speak/show, and an activity-log line."""

    speech: str
    log: str
    ok: bool = True


def _run(cmd):
    """Run a subprocess, raising RuntimeError with stderr on failure."""
    done = subprocess.run(cmd, capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError((done.stderr or done.stdout or "command failed").strip())


def _mac_resolve_app(app_name):
    """Return the .app path whose name loosely matches app_name, or None."""
    wanted = app_name.lower().removesuffix(".app").strip()
    installed = {}
    for directory in _MAC_APP_DIRS:
        for path in Path(directory).glob("*.app"):
            installed[path.stem] = path
    for stem, path in installed.items():
        if stem.lower() == wanted:
            return path
    for stem, path in installed.items():
        if wanted in stem.lower():
            return path
    return None


def _open_application(app_name):
    """Open an application on the current platform, raising on failure."""
    if _SYSTEM == "Darwin":
        try:
            _run(["open", "-a", app_name])
        except RuntimeError:
            resolved = _mac_resolve_app(app_name)
            if not resolved:
                raise
            _run(["open", "-a", str(resolved)])
    elif _SYSTEM == "Windows":
        from AppOpener import open as open_application
        open_application(app_name, match_closest=True, throw_error=True)
    else:
        candidates = (app_name, app_name.lower(), app_name.lower().replace(" ", "-"))
        launcher = next((shutil.which(name) for name in candidates if shutil.which(name)), None)
        if not launcher:
            raise RuntimeError(f"No '{app_name}' executable on PATH")
        subprocess.Popen(
            [launcher], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )


def _close_application(app_name):
    """Close an application on the current platform, raising on failure."""
    if _SYSTEM == "Darwin":
        resolved = _mac_resolve_app(app_name)
        target = resolved.stem if resolved else app_name
        _run(["osascript", "-e", f'quit app "{target}"'])
    elif _SYSTEM == "Windows":
        from AppOpener import close as close_application
        close_application(app_name, match_closest=True)
    else:
        # -i: case-insensitive, match against the process name.
        _run(["pkill", "-i", app_name])


def handle_open_command(app_name):
    """Open an application and report the outcome."""
    try:
        _open_application(app_name)
        return CommandResult(
            speech=f"Thik hai Maalik! , Mai {app_name} ko open kar deti hu",
            log=f"Opened {app_name}",
        )
    except Exception as error:
        return CommandResult(
            speech=f"Maalik, {app_name} naam ka koi software hai hi nahi system mai!",
            log=f"Could not open {app_name} ({error})",
            ok=False,
        )


def handle_close_command(app_name):
    """Close an application and report the outcome."""
    try:
        _close_application(app_name)
        return CommandResult(
            speech=f"Maalik, {app_name} Ko Band Kar deti hu !",
            log=f"Closed {app_name}",
        )
    except Exception as error:
        return CommandResult(
            speech=f"Maalik, {app_name} naam ka koi software open nahi hai toh chinta mat kijiye",
            log=f"Close skipped for {app_name} - not running? ({error})",
            ok=False,
        )


def is_father_query(command):
    """Return whether command is a supported creator query."""
    return command.strip().casefold() in FATHER_RELATED_QUESTIONS


def take_screenshot():
    """Grab the screen to a timestamped PNG and report where it was saved."""
    try:
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = SCREENSHOT_DIR / f"screenshot_{timestamp}.png"
        pyscreenshot.grab().save(str(path))
        return CommandResult(
            speech="Screenshot le liya Maalik!",
            log=f"Screenshot captured -> {path}",
        )
    except Exception as error:
        return CommandResult(
            speech="Maalik, screenshot lene mein dikkat aa gayi!",
            log=f"Screenshot failed ({error})",
            ok=False,
        )
