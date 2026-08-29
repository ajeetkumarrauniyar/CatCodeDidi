"""CatCodeDidi - the entire graphical layer, in one file.

Everything the user sees or clicks lives here: the design tokens, the custom
widgets, the window, and the event handling that drives them. Nothing here
knows how to open an app, recognise speech, talk to Gemini or read the clock -
that stays in the service modules and is only *called* from here.

    main.py  ->  gui.py  ->  assistant / router / commands / speech /
                             gemini_ai / wakeword / personality / data

Threading contract: every blocking action runs on a worker thread and reports
progress by putting an event on `self.events`. That queue is drained by
`_drain_events` on the Tk main thread, which is the only place widgets are
touched. Background threads never call into Tk directly.

Assistant -> GUI events:
    ("state",      "Ready" | "Listening..." | ...)
    ("status",     "short caption shown in the interaction dock")
    ("transcript", "what the user said")
    ("message",    (speaker, text))
    ("error",      (title, body))
    ("activity",   (kind, text))     diagnostics - logged, not shown
    ("wake",       None)             a wake phrase was heard
    ("wake_status", message)
    ("exit",       None)

Run it with `python main.py`: the entry point applies the macOS platform
compatibility patch and the Python/Tk preflight check before this module -
and therefore CustomTkinter - is ever imported.
"""

import datetime
import logging
import math
import platform
import queue
import threading
import tkinter.font as tkfont

import customtkinter as ctk

import speech
import wakeword
from assistant import STATE_ERROR, STATE_READY, Assistant
from config import BOT_NAME


# ==========================================================================
# GUI CONFIGURATION
# ==========================================================================

log = logging.getLogger("catcodedidi")

TAGLINE = "Personal voice assistant"

MODE_VOICE = "Voice Mode"
MODE_TEXT = "Text Mode"

# Idle caption + hint per mode, so the dock always says what to do next.
_MODE_PROMPTS = {
    MODE_VOICE: ("Tap the mic and speak", "or press Space"),
    MODE_TEXT: ("Type your message", "press Enter to send"),
}


def _now():
    return datetime.datetime.now().strftime("%H:%M")


# ==========================================================================
# DESIGN TOKENS
# ==========================================================================

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


# --------------------------------------------------------------------------
# Glyphs
# --------------------------------------------------------------------------
# Tcl/Tk before 8.6.10 stores strings as UCS-2 and raises
#   TclError: character U+1f431 is above the range (U+0000-U+FFFF)
# for any emoji, which would abort widget construction on older Linux and
# Windows Tk builds. Probe once, then fall back to Basic-Multilingual-Plane
# glyphs that render on every Tk. Every other symbol in the UI is already BMP.

_ASTRAL_OK = None

# key -> (preferred emoji, BMP fallback)
_GLYPHS = {
    "cat": ("\U0001F431", "CD"),
}


def supports_emoji(widget):
    """Whether this Tk build can hold characters above U+FFFF."""
    global _ASTRAL_OK
    if _ASTRAL_OK is None:
        try:
            widget.tk.call("string", "length", "\U0001F431")
            _ASTRAL_OK = True
        except Exception:
            _ASTRAL_OK = False
    return _ASTRAL_OK


def glyph(widget, key):
    """The emoji for `key`, or a BMP stand-in on Tk builds that can't show it."""
    emoji, fallback = _GLYPHS[key]
    return emoji if supports_emoji(widget) else fallback

# ==========================================================================
# WIDGET HELPERS
# ==========================================================================

_FONTS = {}


def font(size, weight="normal", mono=False):
    """Cache CTkFont instances - building them per widget is measurably slow."""
    key = (size, weight, mono)
    if key not in _FONTS:
        family = mono_family() if mono else ui_family()
        _FONTS[key] = ctk.CTkFont(family=family, size=size, weight=weight)
    return _FONTS[key]


def _blend(color_a, color_b, t):
    """Linear blend between two #rrggbb colours (t = 0 -> a, 1 -> b)."""
    t = max(0.0, min(1.0, t))
    a = tuple(int(color_a[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(color_b[i:i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(a[i] + (b[i] - a[i]) * t):02x}" for i in range(3))

# ==========================================================================
# CUSTOM WIDGETS
# ==========================================================================

class MicOrb(ctk.CTkCanvas):
    """The voice centrepiece: a glowing core with one animation per state.

    Animation is cheap (a few dozen vector items) and only runs while the
    window ticks it; at rest it draws a single static frame.
    """

    SIZE = 150
    CORE_R = 31

    def __init__(self, master, on_press):
        super().__init__(master, width=self.SIZE, height=self.SIZE,
                         highlightthickness=0, bg=SURFACE)
        self._on_press = on_press
        self._state = "Ready"
        self._hover = False
        self._enabled = True
        self.configure(cursor="hand2")
        self.bind("<Button-1>", self._click)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.render(0.0)

    # -- interaction --------------------------------------------------------

    def _click(self, _event):
        if self._enabled:
            self._on_press()

    def _enter(self, _event):
        self._hover = True
        if not self._is_animated():
            self.render(0.0)

    def _leave(self, _event):
        self._hover = False
        if not self._is_animated():
            self.render(0.0)

    def set_enabled(self, enabled):
        self._enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")

    def set_state(self, state):
        self._state = state
        if not self._is_animated():
            self.render(0.0)

    def _is_animated(self):
        return self._state in ANIMATED_STATES

    # -- drawing ----------------------------------------------------------

    def render(self, phase):
        """Draw one frame. `phase` grows ~1.0 per second."""
        self.delete("all")
        cx = cy = self.SIZE / 2
        color = STATE_META.get(self._state, (ACCENT, "", ""))[0]
        core_r = self.CORE_R

        if self._state == "Listening...":
            for i in range(3):
                p = (phase * 0.9 + i / 3.0) % 1.0
                r = core_r + p * (self.SIZE / 2 - core_r - 4)
                self._ring(cx, cy, r, _blend(color, SURFACE, p), width=2)
        elif self._state == "Processing...":
            for i in range(3):
                self._ring(cx, cy, core_r + 14 + i * 13,
                           _blend(color, SURFACE, 0.55 + i * 0.15), width=1)
            start = (phase * 300) % 360
            self.create_arc(cx - core_r - 12, cy - core_r - 12,
                            cx + core_r + 12, cy + core_r + 12,
                            start=start, extent=110, style="arc",
                            outline=color, width=3)
            core_r += 2 * math.sin(phase * 6)
        elif self._state == "Speaking...":
            breathe = (math.sin(phase * 3.2) + 1) / 2
            self._ring(cx, cy, core_r + 10 + breathe * 26,
                       _blend(color, SURFACE, 0.35 + breathe * 0.4), width=2)
            core_r += 2.5 * math.sin(phase * 3.2)
        else:  # Ready / Error: static halo
            for i in range(3):
                self._ring(cx, cy, core_r + 10 + i * 12,
                           _blend(color, SURFACE, 0.6 + i * 0.16), width=1)

        # Soft glow behind the core.
        for i in range(6, 0, -1):
            self.create_oval(cx - core_r - i * 2, cy - core_r - i * 2,
                             cx + core_r + i * 2, cy + core_r + i * 2,
                             fill=_blend(SURFACE, color, 0.05 + i * 0.02),
                             outline="")
        # Core.
        glow = 0.16 if (self._hover and self._enabled) else 0.0
        fill = _blend(color, "#ffffff", glow) if self._enabled else ELEVATED
        self.create_oval(cx - core_r, cy - core_r, cx + core_r, cy + core_r,
                         fill=fill, outline="")

        ink = "#ffffff" if self._enabled else MUTED
        if supports_emoji(self):
            self.create_text(cx, cy, text="\U0001F3A4", font=("", 22), fill=ink)
        else:
            # No microphone glyph exists in the BMP, so draw one instead of
            # showing a Tk "missing character" box on older Tcl builds.
            self._draw_mic(cx, cy, ink)

    def _draw_mic(self, cx, cy, color):
        """A simple vector microphone: capsule head, cradle, stem and base."""
        w, top, h = 6, cy - 13, 16
        self.create_oval(cx - w, top, cx + w, top + h, fill=color, outline="")
        self.create_arc(cx - w - 4, top + h - 9, cx + w + 4, top + h + 7,
                        start=180, extent=180, style="arc", outline=color, width=2)
        self.create_line(cx, top + h + 7, cx, top + h + 12, fill=color, width=2)
        self.create_line(cx - 5, top + h + 12, cx + 5, top + h + 12, fill=color, width=2)

    def _ring(self, cx, cy, r, color, width):
        self.create_oval(cx - r, cy - r, cx + r, cy + r, outline=color, width=width)


class Tooltip:
    """A small dark tooltip shown while the pointer rests on a widget."""

    def __init__(self, widget, text):
        self._widget = widget
        self._text = text
        self._tip = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def set_text(self, text):
        self._text = text
        if self._tip:                     # refresh while it is on screen
            self._hide()
            self._show()

    def _show(self, _event=None):
        if self._tip or not self._widget.winfo_ismapped():
            return
        x = self._widget.winfo_rootx() + self._widget.winfo_width() // 2 - 60
        y = self._widget.winfo_rooty() - 34
        self._tip = ctk.CTkToplevel(self._widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self._tip.attributes("-topmost", True)
        ctk.CTkLabel(
            self._tip, text=self._text, font=font(SIZE_META),
            fg_color=ELEVATED, text_color=TEXT,
            corner_radius=RADIUS_SM, padx=10, pady=4,
        ).pack()

    def _hide(self, _event=None):
        if self._tip:
            self._tip.destroy()
            self._tip = None


class MuteToggle(ctk.CTkCanvas):
    """Speaker on / off, drawn as vectors.

    No microphone-or-speaker glyph exists in the Basic Multilingual Plane and
    emoji are unavailable on older Tcl builds, so the icon is drawn - the same
    approach MicOrb uses. State is shown by the icon shape (waves vs cross) as
    well as colour, so it is never colour-alone.
    """

    SIZE = 38

    def __init__(self, master, on_toggle, muted=False):
        super().__init__(master, width=self.SIZE, height=self.SIZE,
                         highlightthickness=0, bg=SURFACE)
        self._on_toggle = on_toggle
        self._muted = muted
        self._hover = False
        self.configure(cursor="hand2")
        self.bind("<Button-1>", self._click)
        self.bind("<Enter>", self._enter, add="+")
        self.bind("<Leave>", self._leave, add="+")
        self.tooltip = Tooltip(self, self._tooltip_text())
        self._render()

    # -- state ---------------------------------------------------------

    @property
    def muted(self):
        return self._muted

    def set_muted(self, muted):
        self._muted = bool(muted)
        self.tooltip.set_text(self._tooltip_text())
        self._render()

    def _tooltip_text(self):
        return "Unmute CatCodeDidi" if self._muted else "Mute CatCodeDidi"

    # -- interaction ---------------------------------------------------

    def _click(self, _event):
        self.set_muted(not self._muted)
        self._on_toggle(self._muted)

    def _enter(self, _event):
        self._hover = True
        self._render()

    def _leave(self, _event):
        self._hover = False
        self._render()

    # -- drawing -------------------------------------------------------

    def _render(self):
        self.delete("all")
        cx = cy = self.SIZE / 2
        color = ERROR if self._muted else TEXT_2
        if self._hover:
            self.create_oval(2, 2, self.SIZE - 2, self.SIZE - 2,
                             fill=ELEVATED, outline="")
            color = TEXT if not self._muted else ERROR

        # Speaker: a neck and a cone, as one polygon.
        self.create_polygon(
            cx - 10, cy - 3, cx - 6, cy - 3, cx - 1, cy - 8,
            cx - 1, cy + 8, cx - 6, cy + 3, cx - 10, cy + 3,
            fill=color, outline="",
        )
        if self._muted:
            # A cross where the waves would be - the shape carries the state.
            for dx in (1, -1):
                self.create_line(cx + 3, cy - 5 * dx, cx + 11, cy + 5 * dx,
                                 fill=color, width=2, capstyle="round")
        else:
            for i, spread in enumerate((5, 9)):
                self.create_arc(cx - spread, cy - spread - 1,
                                cx + spread + 2, cy + spread + 1,
                                start=-52, extent=104, style="arc",
                                outline=color, width=2)


def section_header(master, text):
    return ctk.CTkLabel(
        master, text=text.upper(), anchor="w",
        font=font(SIZE_META, "bold"),
        text_color=MUTED,
    )


class MessageCard(ctk.CTkFrame):
    """One conversation turn. variant: 'user' | 'assistant' | 'error'."""

    _FILL = {"user": SURFACE_2, "assistant": ACCENT_TINT, "error": "#2A1E22"}
    _MARK = {"user": TEXT_2, "assistant": ACCENT_BRIGHT, "error": ERROR}

    def __init__(self, master, speaker, text, variant, timestamp,
                 title=None, wraplength=520):
        super().__init__(master, corner_radius=RADIUS_MD, fg_color=self._FILL[variant])
        self.grid_columnconfigure(0, weight=1)
        mark = self._MARK[variant]
        pad = SPACE_4

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="w", padx=pad, pady=(SPACE_3, 0))
        ctk.CTkLabel(head, text="●", font=font(9), text_color=mark).pack(side="left")
        ctk.CTkLabel(
            head, text=f"  {speaker}",
            font=font(SIZE_LABEL, "bold"),
            text_color=mark,
        ).pack(side="left")

        self._labels = []
        row = 1
        if title:
            title_lbl = ctk.CTkLabel(
                self, text=title, anchor="w", justify="left", wraplength=wraplength,
                font=font(SIZE_BODY, "bold"),
                text_color=TEXT,
            )
            title_lbl.grid(row=row, column=0, sticky="w", padx=pad, pady=(SPACE_2, 0))
            self._labels.append(title_lbl)
            row += 1

        self.body = ctk.CTkLabel(
            self, text=text, anchor="w", justify="left", wraplength=wraplength,
            font=font(SIZE_BODY),
            text_color=TEXT if variant != "error" else TEXT_2,
        )
        self.body.grid(row=row, column=0, sticky="w", padx=pad, pady=(SPACE_1, 0))
        self._labels.append(self.body)
        row += 1

        ctk.CTkLabel(
            self, text=timestamp,
            font=font(SIZE_META), text_color=MUTED,
        ).grid(row=row, column=0, sticky="w", padx=pad, pady=(SPACE_1, SPACE_3))

    def set_wraplength(self, value):
        for label in self._labels:
            label.configure(wraplength=value)

# ==========================================================================
# MAIN APPLICATION CLASS
# ==========================================================================

class CatCodeDidiGUI:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.assistant = Assistant(self._emit)
        self._worker = None
        self._alive = True
        self._phase = 0.0
        self._state = STATE_READY
        self._cards = []
        self._resize_job = None
        self._mode = MODE_VOICE
        self._wake_enabled = False
        self._hidden = False
        self.detector = wakeword.WakeWordDetector(
            on_wake=lambda: self.events.put(("wake", None)),
            on_status=self._on_wake_status,
        )

        ctk.set_appearance_mode("dark")
        root.title(BOT_NAME)
        root.configure(fg_color=BG)
        root.geometry("900x900")
        root.minsize(720, 680)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        root.grid_columnconfigure(0, weight=1)
        # The conversation is the hero and the only row that grows; the header,
        # voice core and interaction dock keep their natural height.
        root.grid_rowconfigure(2, weight=1, minsize=240)

        self._build_header()
        self._build_voice_core()
        self._build_conversation()
        self._build_dock()

        root.bind("<space>", self._key_trigger)
        root.bind("<Return>", self._key_trigger)
        for shortcut in ("<Command-q>", "<Control-q>"):
            root.bind(shortcut, lambda _event: self._shutdown())

        self._empty_state()
        self._drain_events()
        self._tick()
        self._run(self.assistant.startup_greeting)

    # ---------------------------------------------------------------- layout

    def _pad(self):
        return SPACE_5

    def _build_header(self):
        bar = ctk.CTkFrame(self.root, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=self._pad(), pady=(SPACE_5, SPACE_3))

        dot = ctk.CTkFrame(bar, width=46, height=46, corner_radius=RADIUS_PILL,
                           fg_color=ACCENT)
        dot.grid(row=0, column=0, rowspan=2)
        dot.grid_propagate(False)
        ctk.CTkLabel(
            dot, text=glyph(dot, "cat"), font=("", 22),
        ).place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            bar, text=BOT_NAME,
            font=ctk.CTkFont(family=ui_family(), size=SIZE_DISPLAY, weight="bold"),
            text_color=TEXT,
        ).grid(row=0, column=1, sticky="sw", padx=SPACE_3)
        ctk.CTkLabel(
            bar, text=TAGLINE,
            font=ctk.CTkFont(family=ui_family(), size=SIZE_META),
            text_color=MUTED,
        ).grid(row=1, column=1, sticky="nw", padx=SPACE_3)

        # Quitting must always be one obvious click away, never only a
        # side effect of the close button.
        bar.grid_columnconfigure(2, weight=1)
        self.quit_button = ctk.CTkButton(
            bar, text="Quit", width=64, height=30,
            font=ctk.CTkFont(family=ui_family(), size=SIZE_META),
            corner_radius=RADIUS_SM,
            fg_color=SURFACE, hover_color=ELEVATED,
            text_color=TEXT_2, command=self._shutdown,
        )
        self.quit_button.grid(row=0, column=3, rowspan=2, sticky="e")

    def _build_voice_core(self):
        card = ctk.CTkFrame(self.root, corner_radius=RADIUS_LG, fg_color=SURFACE)
        card.grid(row=1, column=0, sticky="ew", padx=self._pad(), pady=SPACE_2)
        card.grid_columnconfigure(0, weight=1)

        # Status pill
        self.pill = ctk.CTkFrame(card, corner_radius=RADIUS_PILL, fg_color=SURFACE_2)
        self.pill.grid(row=0, column=0, pady=(SPACE_3, 0))
        self.pill_dot = ctk.CTkLabel(
            self.pill, text="●", font=ctk.CTkFont(size=SIZE_LABEL, weight="bold"),
            text_color=READY,
        )
        self.pill_dot.pack(side="left", padx=(SPACE_3, SPACE_1), pady=SPACE_1)
        self.pill_text = ctk.CTkLabel(
            self.pill, text="Ready",
            font=ctk.CTkFont(family=ui_family(), size=SIZE_LABEL, weight="bold"),
            text_color=TEXT,
        )
        self.pill_text.pack(side="left", padx=(0, SPACE_3), pady=SPACE_1)

        self.orb = MicOrb(card, on_press=self._trigger)
        self.orb.grid(row=1, column=0, pady=(SPACE_2, SPACE_4))

    def _build_conversation(self):
        wrap = ctk.CTkFrame(self.root, fg_color="transparent")
        wrap.grid(row=2, column=0, sticky="nsew", padx=self._pad(), pady=SPACE_2)
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(1, weight=1)

        section_header(wrap, "Conversation").grid(row=0, column=0, sticky="w", pady=(0, SPACE_1))
        self.convo = ctk.CTkScrollableFrame(wrap, corner_radius=RADIUS_MD,
                                            fg_color=SURFACE)
        self.convo.grid(row=1, column=0, sticky="nsew")
        self.convo.grid_columnconfigure(0, weight=1)
        self.convo.bind("<Configure>", self._on_convo_resize)

    def _build_dock(self):
        """The interaction dock: everything the user acts through.

        Top to bottom: the live status line, the keyboard hint, then the
        controls strip - a three-column layout holding the centred Voice /
        Text mode switch and the trailing mute toggle, with the composer
        underneath it in Text Mode.
        """
        dock = ctk.CTkFrame(self.root, corner_radius=RADIUS_LG,
                            fg_color=SURFACE)
        dock.grid(row=3, column=0, sticky="ew", padx=self._pad(),
                  pady=(SPACE_2, SPACE_5))
        dock.grid_columnconfigure(0, weight=1)
        self.dock = dock

        self.caption = ctk.CTkLabel(
            dock, text="Tap the mic and speak", height=22,
            font=ctk.CTkFont(family=ui_family(), size=SIZE_MIC),
            text_color=TEXT_2,
        )
        self.caption.grid(row=0, column=0, pady=(SPACE_4, 0))

        self.hint = ctk.CTkLabel(
            dock, text="or press Space", height=14,
            font=ctk.CTkFont(family=ui_family(), size=SIZE_META),
            text_color=MUTED,
        )
        self.hint.grid(row=1, column=0, pady=(0, SPACE_4))

        self.controls = ctk.CTkFrame(dock, fg_color="transparent", height=0)
        self.controls.grid(row=2, column=0, sticky="ew",
                           padx=SPACE_4, pady=(0, SPACE_4))
        # leading spacer | centred mode switch | trailing mute
        self.controls.grid_columnconfigure(0, weight=1)
        self.controls.grid_columnconfigure(2, weight=1)

        self._build_wake_switch()
        self._build_mode_switch()
        self._build_mute_toggle()
        self._build_text_input()
        self._apply_mode()

    def _build_mode_switch(self):
        """Segmented control: the input method, and nothing else, changes."""
        self.mode_switch = ctk.CTkSegmentedButton(
            self.controls, values=[MODE_VOICE, MODE_TEXT],
            command=self._on_mode_change,
            font=ctk.CTkFont(family=ui_family(), size=SIZE_LABEL,
                             weight="bold"),
            height=34, corner_radius=RADIUS_SM, border_width=2,
            fg_color=SURFACE_2,
            selected_color=ACCENT, selected_hover_color=ACCENT_BRIGHT,
            unselected_color=SURFACE_2, unselected_hover_color=ELEVATED,
            text_color=TEXT,
        )
        self.mode_switch.set(self._mode)
        self.mode_switch.grid(row=0, column=1, pady=(0, SPACE_3))

    def _build_mute_toggle(self):
        """One global audio control, present in both modes."""
        self.mute_button = MuteToggle(
            self.controls, on_toggle=self._on_mute_toggle,
            muted=self.assistant.muted,
        )
        self.mute_button.grid(row=0, column=2, sticky="e", pady=(0, SPACE_3))

    def _build_wake_switch(self):
        """Hands-free listening. Off by default: it holds the microphone open,
        and the engine downloads a model the first time it is switched on."""
        self.wake_switch = ctk.CTkSwitch(
            self.controls, text="Wake word", command=self._on_wake_switch,
            font=ctk.CTkFont(family=ui_family(), size=SIZE_META),
            text_color=TEXT_2, progress_color=ACCENT,
            fg_color=ELEVATED, button_color=TEXT_2,
            button_hover_color=TEXT, width=40, height=20,
            switch_width=38, switch_height=18,
        )
        self.wake_switch.deselect()
        self.wake_switch.grid(row=0, column=0, sticky="w", pady=(0, SPACE_3))
        if not wakeword.is_available():
            self.wake_switch.configure(state="disabled", text="Wake word n/a")

    def _build_text_input(self):
        """The composer, shown only in Text Mode."""
        self.text_row = ctk.CTkFrame(self.controls, fg_color="transparent")
        self.text_row.grid(row=1, column=0, columnspan=3, sticky="ew")
        self.text_row.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkEntry(
            self.text_row, placeholder_text="Ask CatCodeDidi anything…",
            font=ctk.CTkFont(family=ui_family(), size=SIZE_BODY),
            height=44, corner_radius=RADIUS_MD, border_width=1,
            fg_color=SURFACE_2, border_color=BORDER,
            text_color=TEXT, placeholder_text_color=MUTED,
        )
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, SPACE_2))
        self.entry.bind("<Return>", self._submit_text)

        self.send_button = ctk.CTkButton(
            self.text_row, text="Send", width=88, height=44,
            font=ctk.CTkFont(family=ui_family(), size=SIZE_LABEL,
                             weight="bold"),
            corner_radius=RADIUS_MD,
            fg_color=ACCENT, hover_color=ACCENT_BRIGHT,
            text_color="#ffffff", command=self._submit_text,
        )
        self.send_button.grid(row=0, column=1)

    # ------------------------------------------------------------------- modes

    def _on_mode_change(self, value):
        if value != self._mode:
            self._mode = value
            self._apply_mode()

    # ------------------------------------------------------------- wake word

    def _on_wake_switch(self):
        """Turn hands-free listening on or off."""
        if self.wake_switch.get():
            self.detector.start()
            self._wake_enabled = True
        else:
            self.detector.pause()
            self._wake_enabled = False
        self._hidden = False
        if self._state == STATE_READY:
            self._set_idle_caption()

    def _sync_wake(self):
        """Hold the wake listener paused unless it may safely own the mic.

        It listens only when enabled, in Voice Mode, and while nothing else is
        recording - so the wake listener and the command listener can never
        both hold the microphone.
        """
        should_listen = (
            self._wake_enabled
            and self._mode == MODE_VOICE
            and not self._busy()
        )
        if should_listen:
            self.detector.resume()
        else:
            self.detector.pause()

    def _on_wake_detected(self):
        """A wake phrase landed.

        Runs on the Tk thread: the detector only puts an event on the queue,
        which _drain_events picks up, so the window is never touched from the
        audio thread.
        """
        if self._busy() or self._mode != MODE_VOICE:
            self._sync_wake()
            return
        if self._hidden:
            self.show()
        log.info("Wake word accepted - listening for a command")
        self._run(self.assistant.run_interaction)

    def _on_wake_status(self, message):
        self.events.put(("wake_status", message))

    def _on_mute_toggle(self, muted):
        """Flip the one central audio state.

        Only spoken output is affected - recognition, the composer, routing,
        Gemini and every card in the conversation carry on untouched. Muting
        while CatCodeDidi is mid-sentence also cuts that clip short, so the
        control does what the user just asked for rather than only applying
        from the next response.
        """
        self.assistant.muted = muted
        if muted:
            speech.stop_audio()
        log.info("Assistant audio %s", "muted" if muted else "unmuted")

    def _apply_mode(self):
        """Show the input method for the current mode.

        Widgets are hidden and shown, never destroyed and rebuilt. The mic orb
        is withdrawn in Text Mode - it is not the input method there, so
        leaving it would both confuse and steal ~200px from the conversation.
        The status pill stays in both modes.
        """
        if self._mode == MODE_TEXT:
            self.orb.grid_remove()
            self.text_row.grid()
            self.entry.focus_set()
        else:
            self.orb.grid()
            self.text_row.grid_remove()
        self._sync_controls()
        self._sync_wake()
        if self._state == STATE_READY:
            self._set_idle_caption()

    def _set_idle_caption(self):
        caption, hint = _MODE_PROMPTS[self._mode]
        if self._mode == MODE_VOICE and self._wake_enabled:
            caption, hint = "Say “Didi” to wake me", "or tap the mic"
        self.caption.configure(text=caption, text_color=TEXT_2)
        self.hint.configure(text=hint)

    def _sync_controls(self):
        """Enable exactly the input that the current mode + busy state allow."""
        busy = self._busy()
        voice = self._mode == MODE_VOICE
        self.orb.set_enabled(voice and not busy)
        state = "normal" if (not voice and not busy) else "disabled"
        self.entry.configure(state=state)
        self.send_button.configure(state=state)

    def _submit_text(self, _event=None):
        if self._busy() or self._mode != MODE_TEXT:
            return "break"
        text = self.entry.get().strip()
        if not text:
            return "break"
        self.entry.delete(0, "end")
        self._run(lambda: self.assistant.submit_text(text))
        return "break"

    # ------------------------------------------------------------- conversation

    def _empty_state(self):
        self._empty = ctk.CTkLabel(
            self.convo,
            text="Say a command and it appears here.\n"
                 "Try  “open Google Chrome”,  “take a screenshot”,  or ask a question.",
            justify="center",
            font=ctk.CTkFont(family=ui_family(), size=SIZE_BODY),
            text_color=MUTED,
        )
        self._empty.grid(row=0, column=0, pady=SPACE_6, padx=SPACE_4)

    def _wraplength(self):
        width = self.convo.winfo_width()
        return max(280, width - 90)

    def _on_convo_resize(self, _event):
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(120, self._apply_wraplength)

    def _apply_wraplength(self):
        self._resize_job = None
        value = self._wraplength()
        for card in self._cards:
            card.set_wraplength(value)

    def _add_card(self, speaker, text, variant, title=None):
        if self._empty is not None:
            self._empty.destroy()
            self._empty = None
        card = MessageCard(self.convo, speaker, text, variant, _now(),
                           title=title, wraplength=self._wraplength())
        card.grid(row=len(self._cards), column=0, sticky="ew", pady=SPACE_1, padx=SPACE_1)
        self._cards.append(card)
        self.root.after(20, self._scroll_convo_end)

    def _scroll_convo_end(self):
        try:
            self.convo._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    # ------------------------------------------------------------------ states

    def _set_state(self, state):
        self._state = state
        color, glyph, word = STATE_META.get(state, (TEXT_2, "●", state))
        self.pill_dot.configure(text=glyph, text_color=color)
        self.pill_text.configure(text=word)
        self.orb.set_state(state)
        if state == STATE_READY:
            self._set_idle_caption()
        elif state == STATE_ERROR:
            self.caption.configure(text="Something needs your attention", text_color=ERROR)

    def _tick(self):
        if not self._alive:
            return
        if self._hidden:
            # Nothing to draw for a withdrawn window; just idle cheaply.
            delay = 250
        elif self._state in ANIMATED_STATES:
            self._phase += 0.033
            self.orb.render(self._phase)
            delay = 33
        else:
            delay = 200
        self.root.after(delay, self._tick)

    # ---------------------------------------------------------------- worker

    def _emit(self, event_type, payload):
        self.events.put((event_type, payload))

    def _run(self, target):
        if self._worker and self._worker.is_alive():
            return
        # Hand the microphone over before the command listener wants it.
        self.detector.pause()
        self.orb.set_enabled(False)
        self.entry.configure(state="disabled")
        self.send_button.configure(state="disabled")

        def wrapper():
            try:
                target()
            except Exception as error:  # never let the worker take down the UI
                self._emit("error", ("Unexpected problem",
                                     "CatCodeDidi hit an internal error and stopped this "
                                     "request. Please try again."))
                self._emit("activity", ("warn", f"Internal error ({type(error).__name__})"))
                self._emit("state", STATE_ERROR)
            finally:
                self._emit("_done", None)

        self._worker = threading.Thread(target=wrapper, daemon=True)
        self._worker.start()

    def _busy(self):
        return bool(self._worker and self._worker.is_alive())

    def _trigger(self):
        """Start a voice interaction. Only Voice Mode listens."""
        if not self._busy() and self._mode == MODE_VOICE:
            self._run(self.assistant.run_interaction)

    def _key_trigger(self, _event):
        """Space / Enter on the window.

        The mode decides, which is what keeps Space from hijacking typing: in
        Text Mode this never starts the mic, it just puts the caret in the
        composer (the Entry's own class binding has already inserted the
        character by the time this runs). In Voice Mode the composer is
        disabled, so there is nothing to steal a keystroke from.
        """
        if self._mode == MODE_TEXT:
            self.entry.focus_set()
            return "break"
        self._trigger()
        return "break"

    def _drain_events(self):
        if not self._alive:
            return
        try:
            while True:
                self._handle(*self.events.get_nowait())
        except queue.Empty:
            pass
        self.root.after(60, self._drain_events)

    def _handle(self, event_type, payload):
        if event_type == "state":
            self._set_state(payload)
        elif event_type == "status":
            self.caption.configure(text=payload, text_color=TEXT_2)
        elif event_type == "transcript":
            self._add_card("You", payload, "user")
        elif event_type == "message":
            speaker, text = payload
            self._add_card(speaker, text, "assistant")
        elif event_type == "error":
            title, body = payload
            self._add_card(BOT_NAME, body, "error", title=title)
        elif event_type == "activity":
            # Diagnostics only - kept out of the window, kept in the log.
            kind, text = payload
            log.warning("%s", text) if kind == "warn" else log.info("%s", text)
        elif event_type == "exit":
            log.info("Shutting down")
            self.root.after(1100, self._shutdown)
        elif event_type == "wake":
            self._on_wake_detected()
        elif event_type == "wake_status":
            log.info("Wake word: %s", payload)
            if payload == "ready" and self._state == STATE_READY:
                self._set_idle_caption()
            elif payload != "ready":
                self.caption.configure(text=payload, text_color=TEXT_2)
        elif event_type == "_done":
            self._sync_controls()
            self._sync_wake()          # hands the mic back to the listener
            if self._mode == MODE_TEXT:
                self.entry.focus_set()

    # ------------------------------------------------------ hide / show / quit

    def _on_close(self):
        """The window's close button.

        Hiding to the background is only offered when the wake listener is
        actually running - with no tray icon (see wakeword/README for why),
        a hidden window with nothing listening would be unreachable. So when
        wake detection is off, closing quits, which is what the button
        normally means.
        """
        if self._wake_enabled and self.detector.running:
            self.hide()
        else:
            self._shutdown()

    def hide(self):
        """Withdraw the window but keep the assistant (and its ears) alive."""
        if self._hidden or not self._alive:
            return
        self._hidden = True
        self.root.withdraw()
        self._sync_wake()
        log.info('CatCodeDidi is hidden - say a wake word to bring her back, '
                 'or quit from the log with Ctrl-C')

    def show(self):
        """Bring the window back. Must run on the Tk thread."""
        if not self._alive:
            return
        self._hidden = False
        self.root.deiconify()
        self.root.lift()
        try:
            self.root.focus_force()
        except Exception:
            pass

    # -------------------------------------------------------------- shutdown

    def _shutdown(self):
        if not self._alive:
            return
        self._alive = False
        log.info("Quitting - wake word detection stops with the process")
        self.detector.stop()
        try:
            self.root.destroy()
        except Exception:
            pass


# ==========================================================================
# APPLICATION ENTRY POINT
# ==========================================================================


def main():
    """Build the window and hand control to Tk. Called by main.py."""
    root = ctk.CTk()
    CatCodeDidiGUI(root)
    root.mainloop()


if __name__ == "__main__":
    # Importing this module already pulled in CustomTkinter, so the macOS
    # platform patch in main.py would be too late to help. Refuse rather than
    # offer an entry point that silently skips the compatibility fixes.
    raise SystemExit(
        "Run CatCodeDidi with:  python main.py\n"
        "(main.py applies the macOS platform patch and the Python/Tk "
        "preflight check before the GUI is imported.)"
    )
