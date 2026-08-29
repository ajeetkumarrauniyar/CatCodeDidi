"""CatCodeDidi visual design system.

One place for every colour, font and spacing value used by the GUI. Nothing
else in the project should hard-code a hex value or a font name.

Direction: a calm dark "midnight" interface with a single warm violet accent.
State is always shown with an icon + word as well as colour, so the UI stays
readable for colour-blind users and in bright rooms.
"""

import platform
import tkinter.font as tkfont

# --------------------------------------------------------------------------
# Colour tokens
# --------------------------------------------------------------------------

# Layered surfaces, darkest -> lightest.
BG = "#0E0F13"          # window background
SURFACE = "#16181F"     # primary cards / panels
SURFACE_2 = "#1E2129"   # inset areas, user message bubbles
ELEVATED = "#272B36"    # hover / pressed / active chips
BORDER = "#2C313D"      # hairline separators and outlines

# Text, most prominent -> least.
TEXT = "#F3F4F7"        # primary content
TEXT_2 = "#AAB0BE"      # secondary content, role labels
MUTED = "#6C7382"       # timestamps, hints, metadata

# Accent (used sparingly: the mic core, focus, assistant bubble).
ACCENT = "#7C6CF0"
ACCENT_BRIGHT = "#9C8FFF"
ACCENT_TINT = "#211E3A"  # low-chroma accent fill behind assistant messages

# State colours. Each is paired with a glyph + label in STATE_META below.
READY = "#37D399"
LISTENING = "#5FA8FF"
PROCESSING = "#F5B544"
SPEAKING = "#A78BFA"
ERROR = "#F2777A"

SUCCESS = READY
WARNING = PROCESSING

# State -> (colour, glyph, default label). Glyph is text, never colour-only.
STATE_META = {
    "Ready": (READY, "●", "Ready"),
    "Listening...": (LISTENING, "◉", "Listening"),
    "Processing...": (PROCESSING, "◐", "Working"),
    "Speaking...": (SPEAKING, "◈", "Speaking"),
    "Error": (ERROR, "▲", "Needs attention"),
}
ANIMATED_STATES = {"Listening...", "Processing...", "Speaking..."}

# --------------------------------------------------------------------------
# Spacing + radius scale (keep layouts on these steps)
# --------------------------------------------------------------------------

SPACE_1, SPACE_2, SPACE_3, SPACE_4, SPACE_5, SPACE_6 = 4, 8, 12, 16, 24, 32
RADIUS_SM, RADIUS_MD, RADIUS_LG, RADIUS_PILL = 8, 12, 18, 999

# --------------------------------------------------------------------------
# Typography
# --------------------------------------------------------------------------

_UI_STACK = {
    "Darwin": ["SF Pro Display", "SF Pro Text", "Helvetica Neue"],
    "Windows": ["Segoe UI Variable Text", "Segoe UI"],
}.get(platform.system(), ["Inter", "Ubuntu", "Cantarell", "Noto Sans", "DejaVu Sans"])

_MONO_STACK = {
    "Darwin": ["SF Mono", "Menlo"],
    "Windows": ["Cascadia Mono", "Consolas"],
}.get(platform.system(), ["JetBrains Mono", "Ubuntu Mono", "DejaVu Sans Mono"])

# Type scale: a small, deliberate set of sizes.
SIZE_DISPLAY = 28   # assistant identity
SIZE_TITLE = 15     # section headers
SIZE_BODY = 14      # conversation text
SIZE_LABEL = 12     # role labels, buttons
SIZE_META = 11      # timestamps, hints
SIZE_MIC = 15       # mic core caption


def _resolve(stack, fallback):
    try:
        available = set(tkfont.families())
    except Exception:
        return fallback
    return next((name for name in stack if name in available), fallback)


def ui_family():
    return _resolve(_UI_STACK, "TkDefaultFont")


def mono_family():
    return _resolve(_MONO_STACK, "TkFixedFont")
