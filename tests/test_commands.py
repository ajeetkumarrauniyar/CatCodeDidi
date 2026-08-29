import subprocess

import pytest

import commands


def test_is_father_query():
    assert commands.is_father_query("Who Is Your Father")
    assert commands.is_father_query("tumhare papa kaun hai")
    assert not commands.is_father_query("what is the weather")


def test_command_result_defaults():
    r = commands.CommandResult("s", "l")
    assert r.ok is True


def test_mac_resolve_app(tmp_path, monkeypatch):
    (tmp_path / "Google Chrome.app").mkdir()
    (tmp_path / "Safari.app").mkdir()
    monkeypatch.setattr(commands, "_MAC_APP_DIRS", (str(tmp_path),))
    assert commands._mac_resolve_app("chrome").name == "Google Chrome.app"
    assert commands._mac_resolve_app("Safari").name == "Safari.app"
    assert commands._mac_resolve_app("does-not-exist") is None


def test_run_raises_with_stderr(monkeypatch):
    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom happened")
    monkeypatch.setattr(commands.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="boom happened"):
        commands._run(["whatever"])


def test_handle_open_success(monkeypatch):
    monkeypatch.setattr(commands, "_open_application", lambda name: None)
    r = commands.handle_open_command("Chrome")
    assert r.ok and r.log == "Opened Chrome"


def test_handle_open_failure_is_graceful(monkeypatch):
    def boom(name):
        raise RuntimeError("nope")
    monkeypatch.setattr(commands, "_open_application", boom)
    r = commands.handle_open_command("Ghost")
    assert r.ok is False
    assert "Ghost" in r.log and "nope" in r.log


def test_handle_close_failure_is_graceful(monkeypatch):
    monkeypatch.setattr(commands, "_close_application",
                        lambda n: (_ for _ in ()).throw(RuntimeError("not running")))
    r = commands.handle_close_command("Ghost")
    assert r.ok is False


class _FakeImage:
    def __init__(self, black=False):
        self._black = black

    def getbbox(self):
        return None if self._black else (0, 0, 10, 10)

    def convert(self, _mode):
        return self

    def getextrema(self):
        return (0, 0) if self._black else (0, 255)

    def save(self, path):
        self.saved = path


def test_screenshot_success(monkeypatch, tmp_path):
    monkeypatch.setattr(commands, "SCREENSHOT_DIR", tmp_path / "shots")
    monkeypatch.setattr(commands.pyscreenshot, "grab", lambda: _FakeImage(black=False))
    r = commands.take_screenshot()
    assert r.ok and "Screenshot saved" in r.log


def test_screenshot_black_frame_reports_permission(monkeypatch, tmp_path):
    monkeypatch.setattr(commands, "SCREENSHOT_DIR", tmp_path / "shots")
    monkeypatch.setattr(commands.pyscreenshot, "grab", lambda: _FakeImage(black=True))
    r = commands.take_screenshot()
    assert r.ok is False
    assert "permission" in r.log.lower() or "screenshot" in r.log.lower()


def test_screenshot_exception_is_graceful(monkeypatch, tmp_path):
    monkeypatch.setattr(commands, "SCREENSHOT_DIR", tmp_path / "shots")
    monkeypatch.setattr(commands.pyscreenshot, "grab",
                        lambda: (_ for _ in ()).throw(OSError("x")))
    r = commands.take_screenshot()
    assert r.ok is False
