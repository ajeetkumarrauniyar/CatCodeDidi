"""CatCodeDidi entry point.

Runs a small preflight check before touching the GUI so that an unsupported
Python / Tcl-Tk runtime produces a clear message instead of a native crash.
"""

import sys
import textwrap
import platform

# Ensure a valid macOS version tuple is returned
if platform.system() == "Darwin" and not platform.mac_ver()[0]:
    platform.mac_ver = lambda: ("14.0.0", ("", "", ""), "arm64")

MIN_PYTHON = (3, 10)
MIN_TK = (8, 6)


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
    _preflight()
    from gui import main as run_gui
    run_gui()


if __name__ == "__main__":
    main()
