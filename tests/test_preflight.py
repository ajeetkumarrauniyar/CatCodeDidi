import sys

import pytest

import main


def test_preflight_passes_on_current_runtime():
    # The interpreter running the tests already imported customtkinter/tkinter,
    # so a healthy runtime must pass without raising.
    main._preflight()


def test_preflight_rejects_old_python(monkeypatch):
    monkeypatch.setattr(main, "MIN_PYTHON", (99, 0))
    with pytest.raises(SystemExit) as exc:
        main._preflight()
    assert exc.value.code == 1


def test_preflight_rejects_old_tk(monkeypatch, capsys):
    monkeypatch.setattr(main, "MIN_TK", (99, 0))
    with pytest.raises(SystemExit):
        main._preflight()
    out = capsys.readouterr().err
    assert "Tcl/Tk" in out and "crashes" in out


def test_fail_helper_formats_and_exits(capsys):
    with pytest.raises(SystemExit) as exc:
        main._fail("Big Problem", ["line one", "", "line two"])
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "Big Problem" in err and "line one" in err
