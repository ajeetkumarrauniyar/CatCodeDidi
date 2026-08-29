import theme
import widgets


def test_blend_endpoints():
    assert widgets._blend("#000000", "#ffffff", 0) == "#000000"
    assert widgets._blend("#000000", "#ffffff", 1) == "#ffffff"


def test_blend_midpoint():
    mid = widgets._blend("#000000", "#ffffff", 0.5)
    # ~#7f7f7f / #808080
    assert mid[1:3] == mid[3:5] == mid[5:7]
    assert 0x7d <= int(mid[1:3], 16) <= 0x82


def test_blend_clamps():
    assert widgets._blend("#102030", "#405060", -5) == "#102030"
    assert widgets._blend("#102030", "#405060", 5) == "#405060"


def test_theme_state_meta_covers_all_states():
    for state in ("Ready", "Listening...", "Processing...", "Speaking...", "Error"):
        color, glyph, word = theme.STATE_META[state]
        assert color.startswith("#") and glyph and word


def test_theme_font_helpers_do_not_crash():
    assert isinstance(theme.ui_family(), str)
    assert isinstance(theme.mono_family(), str)


def test_spacing_scale_is_ascending():
    scale = [theme.SPACE_1, theme.SPACE_2, theme.SPACE_3,
             theme.SPACE_4, theme.SPACE_5, theme.SPACE_6]
    assert scale == sorted(scale)
