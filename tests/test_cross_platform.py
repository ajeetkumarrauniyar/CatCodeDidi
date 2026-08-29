"""Cross-platform verification.

Only macOS can be *run* here, so these tests pin the Windows and Linux code
paths by mocking `_SYSTEM` and asserting the exact commands / calls issued.
"""

import sys
import types

import pytest

import commands
import theme


@pytest.fixture
def spy(monkeypatch):
    """Capture every subprocess / AppOpener call instead of running it."""
    calls = []
    monkeypatch.setattr(commands, "_run", lambda cmd: calls.append(tuple(cmd)))
    monkeypatch.setattr(commands.subprocess, "Popen",
                        lambda cmd, **kw: calls.append(("Popen", tuple(cmd), kw)))
    fake = types.ModuleType("AppOpener")
    fake.open = lambda n, **kw: calls.append(("AppOpener.open", n, kw))
    fake.close = lambda n, **kw: calls.append(("AppOpener.close", n, kw))
    monkeypatch.setitem(sys.modules, "AppOpener", fake)
    return calls


def _as(monkeypatch, osname):
    monkeypatch.setattr(commands, "_SYSTEM", osname)


# --------------------------------------------------------------- macOS

def test_macos_open_uses_open_dash_a(monkeypatch, spy):
    _as(monkeypatch, "Darwin")
    commands._open_application("Google Chrome")
    assert spy == [("open", "-a", "Google Chrome")]


def test_macos_open_falls_back_to_resolved_bundle(monkeypatch, tmp_path):
    _as(monkeypatch, "Darwin")
    (tmp_path / "Google Chrome.app").mkdir()
    monkeypatch.setattr(commands, "_MAC_APP_DIRS", (str(tmp_path),))
    seen = []

    def flaky(cmd):
        seen.append(tuple(cmd))
        if cmd[-1] == "Chrome":          # the literal spoken name fails
            raise RuntimeError("Unable to find application")

    monkeypatch.setattr(commands, "_run", flaky)
    commands._open_application("Chrome")
    assert seen[0] == ("open", "-a", "Chrome")
    assert seen[1][2].endswith("Google Chrome.app")


def test_macos_close_uses_osascript(monkeypatch, spy):
    _as(monkeypatch, "Darwin")
    monkeypatch.setattr(commands, "_mac_resolve_app", lambda n: None)
    commands._close_application("Safari")
    assert spy == [("osascript", "-e", 'quit app "Safari"')]


# ------------------------------------------------------------- Windows

def test_windows_open_delegates_to_appopener(monkeypatch, spy):
    _as(monkeypatch, "Windows")
    commands._open_application("Google Chrome")
    assert spy == [("AppOpener.open", "Google Chrome",
                    {"match_closest": True, "throw_error": True})]


def test_windows_close_delegates_to_appopener(monkeypatch, spy):
    _as(monkeypatch, "Windows")
    commands._close_application("Google Chrome")
    assert spy == [("AppOpener.close", "Google Chrome", {"match_closest": True})]


def test_windows_never_shells_out(monkeypatch, spy):
    """A console subprocess would flash a cmd window on a GUI app."""
    _as(monkeypatch, "Windows")
    commands._open_application("Notepad")
    commands._close_application("Notepad")
    assert not any(isinstance(c, tuple) and c and c[0] in ("open", "osascript", "pkill")
                   for c in spy)


# --------------------------------------------------------------- Linux

def test_linux_candidates_include_binary_form():
    got = commands._linux_candidates("Google Chrome")
    assert "google-chrome" in got      # the real Linux binary name
    assert "googlechrome" in got
    assert got[0] == "Google Chrome"   # spoken form tried first


def test_linux_open_finds_hyphenated_binary(monkeypatch, spy):
    _as(monkeypatch, "Linux")
    monkeypatch.setattr(commands.shutil, "which",
                        lambda n: "/usr/bin/google-chrome" if n == "google-chrome" else None)
    commands._open_application("Google Chrome")
    assert spy[0][0] == "Popen"
    assert spy[0][1] == ("/usr/bin/google-chrome",)
    assert spy[0][2]["start_new_session"] is True      # survives parent exit


def test_linux_open_raises_when_not_on_path(monkeypatch, spy):
    _as(monkeypatch, "Linux")
    monkeypatch.setattr(commands.shutil, "which", lambda n: None)
    with pytest.raises(RuntimeError, match="on PATH"):
        commands._open_application("Nonesuch")


def test_linux_close_retries_normalised_names(monkeypatch):
    """Regression: `pkill -i "Google Chrome"` can never match - pkill compares
    against the process name, which has no spaces or capitals."""
    _as(monkeypatch, "Linux")
    tried = []

    def only_hyphenated(cmd):
        tried.append(cmd[-1])
        if cmd[-1] != "google-chrome":
            raise RuntimeError("no process found")

    monkeypatch.setattr(commands, "_run", only_hyphenated)
    commands._close_application("Google Chrome")
    assert "google-chrome" in tried


def test_linux_close_raises_when_nothing_matches(monkeypatch):
    _as(monkeypatch, "Linux")
    monkeypatch.setattr(commands, "_run",
                        lambda cmd: (_ for _ in ()).throw(RuntimeError("none")))
    with pytest.raises(RuntimeError, match="No running process"):
        commands._close_application("Ghost")


# ------------------------------------------------------- paths & files

def test_screenshot_dir_is_anchored_to_project_not_cwd():
    """Launching from Finder/Explorer or another folder must not scatter
    screenshots into whatever cwd happened to be set."""
    from pathlib import Path
    assert commands.SCREENSHOT_DIR.parent == Path(commands.__file__).resolve().parent
    assert commands.SCREENSHOT_DIR.name == "screenshots"


def test_mac_resolve_app_tolerates_missing_directories(monkeypatch):
    """~/Applications does not exist on every machine."""
    monkeypatch.setattr(commands, "_MAC_APP_DIRS", ("/no/such/dir", "/also/missing"))
    assert commands._mac_resolve_app("Anything") is None


def test_tempfile_is_closed_before_writing(monkeypatch):
    """Windows keeps an exclusive lock on open handles, so gTTS must not be
    handed a file object that is still open."""
    import speech
    events = []

    class Handle:
        name = str(__import__("pathlib").Path(__file__).parent / "x.mp3")

        def close(self):
            events.append("closed")

    monkeypatch.setattr(speech.tempfile, "NamedTemporaryFile", lambda **kw: Handle())
    monkeypatch.setattr(speech, "gTTS",
                        lambda **kw: type("T", (), {"save": lambda s, p: events.append("saved")})())
    monkeypatch.setattr(speech, "play_audio", lambda p: events.append("played"))
    speech.bot_speak("hello")
    assert events.index("closed") < events.index("saved")


# ------------------------------------------------------------- glyphs

def test_every_static_icon_is_bmp():
    """Tcl < 8.6.10 raises TclError on characters above U+FFFF, which would
    abort widget construction on older Linux/Windows Tk builds."""
    for state, (_color, glyph, _word) in theme.STATE_META.items():
        for ch in glyph:
            assert ord(ch) <= 0xFFFF, f"{state} glyph {glyph!r} is not BMP"


def test_glyph_falls_back_to_bmp_when_tk_cannot_show_emoji(monkeypatch):
    monkeypatch.setattr(theme, "supports_emoji", lambda widget: False)
    for key in theme._GLYPHS:
        for ch in theme.glyph(None, key):
            assert ord(ch) <= 0xFFFF


def test_glyph_uses_emoji_when_supported(monkeypatch):
    monkeypatch.setattr(theme, "supports_emoji", lambda widget: True)
    assert theme.glyph(None, "cat") == "\U0001F431"


def test_supports_emoji_returns_false_on_narrow_tcl(monkeypatch):
    monkeypatch.setattr(theme, "_ASTRAL_OK", None)

    class NarrowTk:
        class tk:
            @staticmethod
            def call(*args):
                raise Exception("character U+1f431 is above the range allowed by Tcl")

    assert theme.supports_emoji(NarrowTk()) is False
    monkeypatch.setattr(theme, "_ASTRAL_OK", None)


# --------------------------------------------------- platform neutrality

def test_gemini_module_has_no_platform_branches():
    import inspect
    import gemini_ai
    src = inspect.getsource(gemini_ai)
    for token in ("platform.system", "sys.platform", "Darwin", "win32"):
        assert token not in src


@pytest.mark.parametrize("osname", ["Darwin", "Windows", "Linux", "FreeBSD", "Haiku"])
def test_permission_hint_exists_for_every_platform(osname):
    """Even an unknown OS must get actionable advice, not an empty string."""
    import speech
    hint = speech.mic_permission_help(osname)
    assert hint and hint.strip().endswith(".")


def test_permission_hints_are_platform_specific():
    import speech
    assert "System Settings" in speech.mic_permission_help("Darwin")
    assert "Privacy & security" in speech.mic_permission_help("Windows")
    assert "PipeWire" in speech.mic_permission_help("Linux")
