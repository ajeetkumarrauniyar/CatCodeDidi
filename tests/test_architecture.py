"""The GUI lives in exactly one file, and the services never depend on it."""

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODULES = sorted(p for p in ROOT.glob("*.py") if p.stem != "__init__")
LOCAL = {p.stem for p in MODULES}

# Everything that is not the interface.
SERVICES = {"assistant", "router", "commands", "speech", "gemini_ai",
            "personality", "wakeword", "config", "data", "utils"}


def _imports(path):
    deps = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            deps |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            deps.add(node.module.split(".")[0])
    return deps


@pytest.mark.parametrize("module", sorted(SERVICES))
def test_no_service_imports_the_gui(module):
    path = ROOT / f"{module}.py"
    if not path.exists():
        pytest.skip(f"{module} not present")
    assert "gui" not in _imports(path), f"{module}.py must not depend on the GUI"


@pytest.mark.parametrize("module", sorted(SERVICES))
def test_no_service_imports_a_gui_toolkit(module):
    """Widgets, colours and fonts belong in gui.py, nowhere else."""
    path = ROOT / f"{module}.py"
    if not path.exists():
        pytest.skip(f"{module} not present")
    toolkits = {"customtkinter", "tkinter", "darkdetect"}
    assert not (_imports(path) & toolkits), f"{module}.py imports a GUI toolkit"


def test_gui_toolkit_is_imported_in_exactly_one_place():
    users = [p.stem for p in MODULES if "customtkinter" in _imports(p)]
    assert users == ["gui"], f"CustomTkinter imported by {users}"


def test_there_are_no_import_cycles():
    edges = {p.stem: _imports(p) & LOCAL for p in MODULES}

    def walk(node, seen):
        for dep in sorted(edges.get(node, ())):
            if dep in seen:
                return seen + [dep]
            found = walk(dep, seen + [dep])
            if found:
                return found
        return None

    cycles = [c for module in edges if (c := walk(module, [module]))]
    assert not cycles, f"import cycle: {cycles}"


def test_main_stays_a_thin_entry_point():
    """main.py bootstraps and launches; it must not grow UI code."""
    source = (ROOT / "main.py").read_text()
    assert "customtkinter" not in _imports(ROOT / "main.py")
    for widgetish in ("CTkFrame", "CTkLabel", "CTkButton", "grid(", "pack("):
        assert widgetish not in source, f"main.py contains UI code: {widgetish}"


def test_old_gui_modules_are_gone():
    for stale in ("theme.py", "widgets.py"):
        assert not (ROOT / stale).exists(), f"{stale} should be merged into gui.py"


def test_gui_exposes_what_the_old_modules_did():
    """Consolidation must not have dropped anything."""
    import gui
    for name in ("BG", "SURFACE", "TEXT", "ACCENT", "STATE_META", "ANIMATED_STATES",
                 "SPACE_1", "RADIUS_MD", "SIZE_BODY", "ui_family", "mono_family",
                 "glyph", "supports_emoji", "font", "_blend",
                 "MicOrb", "MuteToggle", "MessageCard", "Tooltip", "section_header",
                 "CatCodeDidiGUI", "main"):
        assert hasattr(gui, name), f"gui.{name} went missing in the merge"
