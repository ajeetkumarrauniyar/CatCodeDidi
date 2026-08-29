
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


# --------------------------------------------- macOS compatibility patch

def test_patch_is_a_noop_off_macos(monkeypatch):
    monkeypatch.setattr(main.platform, "system", lambda: "Linux")
    called = []
    monkeypatch.setattr(main.platform, "mac_ver",
                        lambda: called.append(1) or ("", ("", "", ""), ""))
    assert main.patch_macos_version() is False


def test_patch_leaves_a_working_mac_ver_alone(monkeypatch):
    monkeypatch.setattr(main.platform, "system", lambda: "Darwin")
    original = ("15.1", ("", "", ""), "arm64")
    monkeypatch.setattr(main.platform, "mac_ver", lambda: original)
    assert main.patch_macos_version() is False
    assert main.platform.mac_ver() == original      # untouched


def test_patch_repairs_an_empty_mac_ver(monkeypatch):
    """The reported crash: darkdetect does int('') and dies."""
    monkeypatch.setattr(main.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(main.platform, "mac_ver", lambda: ("", ("", "", ""), ""))
    monkeypatch.setattr(main.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(main, "_macos_product_version", lambda: "15.3.1")

    assert main.patch_macos_version() is True
    version, _, machine = main.platform.mac_ver()
    assert version == "15.3.1"                      # the real version, queried
    assert machine == "arm64"                       # read, not hardcoded
    int(version.split(".")[0])                      # what darkdetect does


def test_patch_falls_back_when_sw_vers_is_unavailable(monkeypatch):
    monkeypatch.setattr(main.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(main.platform, "mac_ver", lambda: ("", ("", "", ""), ""))
    monkeypatch.setattr(main.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(main, "_macos_product_version", lambda: None)

    assert main.patch_macos_version() is True
    version = main.platform.mac_ver()[0]
    assert version and int(version.split(".")[0]) >= 10   # parseable, not empty


def test_product_version_rejects_garbage(monkeypatch):
    """Never install a value that would fail to parse anyway."""
    class Result:
        stdout = "command not found\n"
    monkeypatch.setattr(main.subprocess, "run", lambda *a, **k: Result())
    assert main._macos_product_version() is None


def test_product_version_survives_a_missing_sw_vers(monkeypatch):
    monkeypatch.setattr(main.subprocess, "run",
                        lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError))
    assert main._macos_product_version() is None
