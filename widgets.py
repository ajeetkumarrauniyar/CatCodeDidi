"""Custom presentational widgets for the CatCodeDidi GUI.

These hold no assistant logic - they draw state that the window passes in.
"""

import math

import customtkinter as ctk

import theme

_FONTS = {}


def font(size, weight="normal", mono=False):
    """Cache CTkFont instances - building them per widget is measurably slow."""
    key = (size, weight, mono)
    if key not in _FONTS:
        family = theme.mono_family() if mono else theme.ui_family()
        _FONTS[key] = ctk.CTkFont(family=family, size=size, weight=weight)
    return _FONTS[key]


def _blend(color_a, color_b, t):
    """Linear blend between two #rrggbb colours (t = 0 -> a, 1 -> b)."""
    t = max(0.0, min(1.0, t))
    a = tuple(int(color_a[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(color_b[i:i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(a[i] + (b[i] - a[i]) * t):02x}" for i in range(3))


class MicOrb(ctk.CTkCanvas):
    """The voice centrepiece: a glowing core with one animation per state.

    Animation is cheap (a few dozen vector items) and only runs while the
    window ticks it; at rest it draws a single static frame.
    """

    SIZE = 150
    CORE_R = 31

    def __init__(self, master, on_press):
        super().__init__(master, width=self.SIZE, height=self.SIZE,
                         highlightthickness=0, bg=theme.SURFACE)
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
        return self._state in theme.ANIMATED_STATES

    # -- drawing ----------------------------------------------------------

    def render(self, phase):
        """Draw one frame. `phase` grows ~1.0 per second."""
        self.delete("all")
        cx = cy = self.SIZE / 2
        color = theme.STATE_META.get(self._state, (theme.ACCENT, "", ""))[0]
        core_r = self.CORE_R

        if self._state == "Listening...":
            for i in range(3):
                p = (phase * 0.9 + i / 3.0) % 1.0
                r = core_r + p * (self.SIZE / 2 - core_r - 4)
                self._ring(cx, cy, r, _blend(color, theme.SURFACE, p), width=2)
        elif self._state == "Processing...":
            for i in range(3):
                self._ring(cx, cy, core_r + 14 + i * 13,
                           _blend(color, theme.SURFACE, 0.55 + i * 0.15), width=1)
            start = (phase * 300) % 360
            self.create_arc(cx - core_r - 12, cy - core_r - 12,
                            cx + core_r + 12, cy + core_r + 12,
                            start=start, extent=110, style="arc",
                            outline=color, width=3)
            core_r += 2 * math.sin(phase * 6)
        elif self._state == "Speaking...":
            breathe = (math.sin(phase * 3.2) + 1) / 2
            self._ring(cx, cy, core_r + 10 + breathe * 26,
                       _blend(color, theme.SURFACE, 0.35 + breathe * 0.4), width=2)
            core_r += 2.5 * math.sin(phase * 3.2)
        else:  # Ready / Error: static halo
            for i in range(3):
                self._ring(cx, cy, core_r + 10 + i * 12,
                           _blend(color, theme.SURFACE, 0.6 + i * 0.16), width=1)

        # Soft glow behind the core.
        for i in range(6, 0, -1):
            self.create_oval(cx - core_r - i * 2, cy - core_r - i * 2,
                             cx + core_r + i * 2, cy + core_r + i * 2,
                             fill=_blend(theme.SURFACE, color, 0.05 + i * 0.02),
                             outline="")
        # Core.
        glow = 0.16 if (self._hover and self._enabled) else 0.0
        fill = _blend(color, "#ffffff", glow) if self._enabled else theme.ELEVATED
        self.create_oval(cx - core_r, cy - core_r, cx + core_r, cy + core_r,
                         fill=fill, outline="")

        ink = "#ffffff" if self._enabled else theme.MUTED
        if theme.supports_emoji(self):
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


def section_header(master, text):
    return ctk.CTkLabel(
        master, text=text.upper(), anchor="w",
        font=font(theme.SIZE_META, "bold"),
        text_color=theme.MUTED,
    )


class MessageCard(ctk.CTkFrame):
    """One conversation turn. variant: 'user' | 'assistant' | 'error'."""

    _FILL = {"user": theme.SURFACE_2, "assistant": theme.ACCENT_TINT, "error": "#2A1E22"}
    _MARK = {"user": theme.TEXT_2, "assistant": theme.ACCENT_BRIGHT, "error": theme.ERROR}

    def __init__(self, master, speaker, text, variant, timestamp,
                 title=None, wraplength=520):
        super().__init__(master, corner_radius=theme.RADIUS_MD, fg_color=self._FILL[variant])
        self.grid_columnconfigure(0, weight=1)
        mark = self._MARK[variant]
        pad = theme.SPACE_4

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="w", padx=pad, pady=(theme.SPACE_3, 0))
        ctk.CTkLabel(head, text="●", font=font(9), text_color=mark).pack(side="left")
        ctk.CTkLabel(
            head, text=f"  {speaker}",
            font=font(theme.SIZE_LABEL, "bold"),
            text_color=mark,
        ).pack(side="left")

        self._labels = []
        row = 1
        if title:
            title_lbl = ctk.CTkLabel(
                self, text=title, anchor="w", justify="left", wraplength=wraplength,
                font=font(theme.SIZE_BODY, "bold"),
                text_color=theme.TEXT,
            )
            title_lbl.grid(row=row, column=0, sticky="w", padx=pad, pady=(theme.SPACE_2, 0))
            self._labels.append(title_lbl)
            row += 1

        self.body = ctk.CTkLabel(
            self, text=text, anchor="w", justify="left", wraplength=wraplength,
            font=font(theme.SIZE_BODY),
            text_color=theme.TEXT if variant != "error" else theme.TEXT_2,
        )
        self.body.grid(row=row, column=0, sticky="w", padx=pad, pady=(theme.SPACE_1, 0))
        self._labels.append(self.body)
        row += 1

        ctk.CTkLabel(
            self, text=timestamp,
            font=font(theme.SIZE_META), text_color=theme.MUTED,
        ).grid(row=row, column=0, sticky="w", padx=pad, pady=(theme.SPACE_1, theme.SPACE_3))

    def set_wraplength(self, value):
        for label in self._labels:
            label.configure(wraplength=value)


class ActivityRow(ctk.CTkFrame):
    """A single compact icon + text + time line for the activity panel."""

    # All BMP so they render on every Tk build; "shot" is resolved at runtime
    # because the camera emoji is above U+FFFF (see theme.glyph).
    ICONS = {
        "open": "→", "close": "■",
        "ai": "✦", "warn": "▲", "ok": "✓", "info": "·",
    }

    def __init__(self, master, kind, text, timestamp):
        super().__init__(master, fg_color="transparent", height=22)
        self.pack_propagate(False)
        color = theme.ERROR if kind == "warn" else (
            theme.ACCENT_BRIGHT if kind == "ai" else theme.TEXT_2)
        icon = theme.glyph(self, "camera") if kind == "shot" else self.ICONS.get(kind, "·")
        ctk.CTkLabel(
            self, text=icon, width=14,
            font=font(theme.SIZE_META),
            text_color=color,
        ).pack(side="left")
        ctk.CTkLabel(
            self, text=timestamp,
            font=font(theme.SIZE_META),
            text_color=theme.MUTED,
        ).pack(side="right")
        ctk.CTkLabel(
            self, text=text, anchor="w", justify="left",
            font=font(theme.SIZE_META),
            text_color=theme.TEXT_2,
        ).pack(side="left", padx=(6, 0), fill="x")
