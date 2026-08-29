import gui


def test_blend_endpoints():
    assert gui._blend("#000000", "#ffffff", 0) == "#000000"
    assert gui._blend("#000000", "#ffffff", 1) == "#ffffff"


def test_blend_midpoint():
    mid = gui._blend("#000000", "#ffffff", 0.5)
    # ~#7f7f7f / #808080
    assert mid[1:3] == mid[3:5] == mid[5:7]
    assert 0x7d <= int(mid[1:3], 16) <= 0x82


def test_blend_clamps():
    assert gui._blend("#102030", "#405060", -5) == "#102030"
    assert gui._blend("#102030", "#405060", 5) == "#405060"


def test_theme_state_meta_covers_all_states():
    for state in ("Ready", "Listening...", "Processing...", "Speaking...", "Error"):
        color, glyph, word = gui.STATE_META[state]
        assert color.startswith("#") and glyph and word


def test_theme_font_helpers_do_not_crash():
    assert isinstance(gui.ui_family(), str)
    assert isinstance(gui.mono_family(), str)


def test_spacing_scale_is_ascending():
    scale = [gui.SPACE_1, gui.SPACE_2, gui.SPACE_3,
             gui.SPACE_4, gui.SPACE_5, gui.SPACE_6]
    assert scale == sorted(scale)
