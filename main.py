"""CatCodeDidi entry point.

Does three things and nothing else: apply platform compatibility fixes, check
that the Python / Tcl-Tk runtime can actually build a window, and hand over to
the GUI. No interface code lives here - that is all in gui.py.

    main.py  ->  gui.py  ->  assistant / router / commands / speech /
                             gemini_ai / wakeword / personality / data

The compatibility patch runs at import time, before anything pulls in
CustomTkinter (which imports darkdetect, which parses the macOS version).
Importing this module is therefore enough to make the GUI safe to import -
that is how the test suite does it too.
"""

import logging
import platform
import subprocess
import sys
import textwrap

MIN_PYTHON = (3, 10)
MIN_TK = (8, 6)


def _macos_product_version():
    """Ask macOS for its version, the same way the OS reports it itself."""
    try:
        out = subprocess.run(["sw_vers", "-productVersion"],
                             capture_output=True, text=True, timeout=5)
        version = out.stdout.strip()
    except Exception:
        return None
    # Must be something int() can parse, or we have not fixed anything.
    return version if version[:1].isdigit() else None


def patch_macos_version():
    """Guarantee platform.mac_ver() reports a parseable version.

    On some macOS + Python combinations mac_ver() returns ('', ('', '', ''), '').
    darkdetect - pulled in by CustomTkinter - does int() on the major component
    and dies with `ValueError: invalid literal for int() with base 10: ''`,
    which reads as a CustomTkinter import failure rather than a platform quirk.

    The real version comes from `sw_vers`; nothing about the machine is
    hardcoded, and the architecture is read from platform.machine(). Only if
    sw_vers is unavailable do we fall back to a generic, parseable value - the
    goal is a number the parser accepts, not a lie about the OS.
    """
    if platform.system() != "Darwin":
        return False
    try:
        if platform.mac_ver()[0]:
            return False                      # already fine, leave it alone
    except Exception:
        pass

    version = _macos_product_version() or "10.16"
    machine = platform.machine() or ""
    platform.mac_ver = lambda *_args, **_kwargs: (version, ("", "", ""), machine)
    return True


_PATCHED = patch_macos_version()


def _fail(title, lines):
    bar = "─" * 66
    body = "\n".join(textwrap.fill(line, 66) if line else "" for line in lines)
    print(f"\n{bar}\n  {title}\n{bar}\n{body}\n{bar}\n", file=sys.stderr)
    raise SystemExit(1)


def _preflight():
    if sys.version_info < MIN_PYTHON:
        _fail("Unsupported Python runtime", [
            f"CatCodeDidi needs Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer.",
            f"You are running Python {sys.version.split()[0]} from:",
            f"  {sys.executable}",
            "",
            "The Apple Command Line Tools Python (3.9) ships the obsolete "
            "Tcl/Tk 8.5, which aborts on modern macOS. Install a current "
            "Python from python.org, or via Homebrew:",
            "  brew install python@3.13 python-tk@3.13",
            "Then recreate the virtual environment with that interpreter "
            "(see README.md → macOS setup).",
        ])

    try:
        import tkinter
    except Exception as error:  # pragma: no cover - environment specific
        _fail("Tkinter is not available", [
            f"Python could not import tkinter: {error}",
            "",
            "Install the Tk package for your platform:",
            "  macOS (Homebrew):  brew install python-tk@3.13",
            "  Debian/Ubuntu:     sudo apt install python3-tk",
            "  Fedora:            sudo dnf install python3-tkinter",
        ])

    tk_version = tuple(int(p) for p in str(tkinter.TkVersion).split("."))
    if tk_version < MIN_TK:
        _fail("Outdated Tcl/Tk runtime", [
            f"This Python is linked against Tcl/Tk {tkinter.TkVersion}, which "
            "crashes during window creation on current macOS.",
            f"  Interpreter: {sys.executable}",
            "",
            "Use a Python that bundles Tk 8.6+ (python.org installer) or, on "
            "Homebrew, install 'python-tk@3.13' and rebuild the virtual "
            "environment. Verify with:",
            '  python3 -c "import tkinter; print(tkinter.TkVersion)"',
        ])

    try:
        import importlib.util
        if importlib.util.find_spec("customtkinter") is None:
            raise ImportError
    except Exception:
        _fail("Missing dependency", [
            "The 'customtkinter' package is not installed.",
            "Install project dependencies into your virtual environment:",
            "  pip install -r requirements.txt",
        ])


def main():
    """Bootstrap, then launch the GUI."""
    _preflight()
    # Diagnostics (apps opened, screenshot paths, Gemini failures) go here
    # rather than into the window; anything the user must act on is shown
    # as an error card in the conversation.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    if _PATCHED:
        logging.getLogger("catcodedidi").info(
            "Applied macOS platform.mac_ver() compatibility patch")

    from gui import main as run_gui       # imported last: pulls in CustomTkinter
    run_gui()


if __name__ == "__main__":
    main()
