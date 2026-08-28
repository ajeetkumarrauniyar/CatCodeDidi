"""Tkinter desktop GUI for CatCodeDidi.

The GUI is a thin presentation layer. It owns no assistant logic: it runs each
interaction on a background thread and receives progress events through a
thread-safe queue that is drained on the Tk main loop, so the window stays
responsive while listening, recognizing, calling Gemini or speaking.
"""

import platform
import queue
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import scrolledtext

from assistant import (
    STATE_ERROR,
    STATE_LISTENING,
    STATE_PROCESSING,
    STATE_READY,
    STATE_SPEAKING,
    Assistant,
)
from config import BOT_NAME

TAGLINE = "Hindi-speaking desktop voice assistant"
PAD = 18

# Light theme palette (slate / indigo). Every colour is defined here so the
# look can be tuned in one place.
COL_BG = "#f1f5f9"
COL_SURFACE = "#ffffff"
COL_BORDER = "#e2e8f0"
COL_TEXT = "#1e293b"
COL_MUTED = "#64748b"
COL_ACCENT = "#4f46e5"
COL_ACCENT_HOVER = "#4338ca"
COL_ACCENT_ACTIVE = "#3730a3"
COL_DISABLED_BG = "#a3accb"
COL_DISABLED_FG = "#f8fafc"
COL_USER = "#0f766e"

# Each state carries a colour AND a glyph + word, so the state is never
# communicated by colour alone.
STATE_STYLE = {
    STATE_READY: ("#16a34a", "●", "Ready"),
    STATE_LISTENING: ("#2563eb", "🎙", "Listening"),
    STATE_PROCESSING: ("#d97706", "⏳", "Processing"),
    STATE_SPEAKING: ("#7c3aed", "🔊", "Speaking"),
    STATE_ERROR: ("#dc2626", "⚠", "Error"),
}
_ANIMATED_STATES = {STATE_LISTENING, STATE_PROCESSING, STATE_SPEAKING}


def _pick_font(candidates, fallback):
    available = set(tkfont.families())
    for name in candidates:
        if name in available:
            return name
    return fallback


def _fonts():
    """Return (ui_family, mono_family) that look native on this platform."""
    system = platform.system()
    if system == "Windows":
        ui = _pick_font(["Segoe UI"], "TkDefaultFont")
        mono = _pick_font(["Cascadia Mono", "Consolas"], "TkFixedFont")
    elif system == "Darwin":
        ui = _pick_font(["SF Pro Text", "Helvetica Neue"], "TkDefaultFont")
        mono = _pick_font(["Menlo", "SF Mono"], "TkFixedFont")
    else:
        ui = _pick_font(["Ubuntu", "Cantarell", "Noto Sans", "DejaVu Sans"], "TkDefaultFont")
        mono = _pick_font(["Ubuntu Mono", "DejaVu Sans Mono", "Noto Sans Mono"], "TkFixedFont")
    return ui, mono


class _Tooltip:
    """Minimal hover tooltip for a single widget."""

    def __init__(self, widget, text, font):
        self._widget = widget
        self._text = text
        self._font = font
        self._tip = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")

    def _show(self, _event=None):
        if self._tip or self._widget["state"] == "disabled":
            return
        x = self._widget.winfo_rootx() + 20
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 8
        self._tip = tk.Toplevel(self._widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self._tip, text=self._text, font=self._font, bg="#0f172a", fg="white",
            padx=8, pady=4,
        ).pack()

    def _hide(self, _event=None):
        if self._tip:
            self._tip.destroy()
            self._tip = None


class CatCodeDidiGUI:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.assistant = Assistant(self._emit)
        self._worker = None
        self._alive = True
        self._state = STATE_READY
        self._anim_step = 0

        ui_family, mono_family = _fonts()
        self.f_title = tkfont.Font(family=ui_family, size=19, weight="bold")
        self.f_tag = tkfont.Font(family=ui_family, size=11)
        self.f_body = tkfont.Font(family=ui_family, size=12)
        self.f_body_bold = tkfont.Font(family=ui_family, size=12, weight="bold")
        self.f_small = tkfont.Font(family=ui_family, size=10)
        self.f_button = tkfont.Font(family=ui_family, size=15, weight="bold")
        self.f_status = tkfont.Font(family=ui_family, size=12, weight="bold")
        self.f_mono = tkfont.Font(family=mono_family, size=10)

        root.title(BOT_NAME)
        root.geometry("720x680")
        root.minsize(560, 560)
        root.configure(bg=COL_BG)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        root.columnconfigure(0, weight=1)
        root.rowconfigure(3, weight=3, minsize=150)  # conversation
        root.rowconfigure(4, weight=2, minsize=120)  # activity log

        self._build_header()
        self._build_status()
        self._build_mic_button()
        self._build_conversation()
        self._build_activity()
        self._bind_keys()

        self._set_state(STATE_READY)
        self._append(self.conversation, f"{BOT_NAME} is starting up...\n\n", "meta")
        self._drain_events()
        self._animate_status()
        self._run_in_background(self.assistant.startup_greeting)

    # ---------- layout ----------

    def _build_header(self):
        header = tk.Frame(self.root, bg=COL_BG)
        header.grid(row=0, column=0, sticky="ew", padx=PAD, pady=(PAD, 8))

        avatar = tk.Canvas(header, width=52, height=52, bg=COL_BG,
                           highlightthickness=0)
        avatar.create_oval(2, 2, 50, 50, fill=COL_ACCENT, outline="")
        avatar.create_text(26, 28, text="🐱", font=("", 22))
        avatar.pack(side="left")

        titles = tk.Frame(header, bg=COL_BG)
        titles.pack(side="left", padx=14)
        tk.Label(titles, text=BOT_NAME, font=self.f_title, bg=COL_BG,
                 fg=COL_TEXT).pack(anchor="w")
        tk.Label(titles, text=TAGLINE, font=self.f_tag, bg=COL_BG,
                 fg=COL_MUTED).pack(anchor="w")

    def _build_status(self):
        wrap = tk.Frame(self.root, bg=COL_BG)
        wrap.grid(row=1, column=0, sticky="ew", padx=PAD, pady=4)

        self.status_chip = tk.Frame(wrap, bg=COL_SURFACE, highlightthickness=1,
                                    highlightbackground=COL_BORDER)
        self.status_chip.pack(side="left")
        self.status_dot = tk.Label(self.status_chip, text="●", font=self.f_status,
                                   bg=COL_SURFACE)
        self.status_dot.pack(side="left", padx=(12, 6), pady=6)
        self.status_text = tk.Label(self.status_chip, text=STATE_READY,
                                    font=self.f_status, bg=COL_SURFACE, fg=COL_TEXT)
        self.status_text.pack(side="left", padx=(0, 14), pady=6)

        self.hint = tk.Label(wrap, text="Press Space or click the button to talk",
                             font=self.f_small, bg=COL_BG, fg=COL_MUTED)
        self.hint.pack(side="right")

    def _build_mic_button(self):
        wrap = tk.Frame(self.root, bg=COL_BG)
        wrap.grid(row=2, column=0, pady=(10, 6))
        self.mic_button = tk.Button(
            wrap, text="🎤   Speak", font=self.f_button,
            bg=COL_ACCENT, fg="white",
            activebackground=COL_ACCENT_ACTIVE, activeforeground="white",
            disabledforeground=COL_DISABLED_FG,
            relief="flat", bd=0, highlightthickness=0, cursor="hand2",
            padx=34, pady=14, command=self._on_mic_click,
        )
        self.mic_button.pack()
        self.mic_button.bind("<Enter>", self._on_hover_in, add="+")
        self.mic_button.bind("<Leave>", self._on_hover_out, add="+")
        _Tooltip(self.mic_button, "Start one voice interaction (Space)", self.f_small)

    def _build_conversation(self):
        frame = self._card("Conversation", row=3)
        self.conversation = scrolledtext.ScrolledText(
            frame, wrap="word", font=self.f_body, bg=COL_SURFACE, fg=COL_TEXT,
            relief="flat", bd=0, padx=14, pady=12, state="disabled", height=9,
            highlightthickness=0, spacing1=2, spacing3=4,
        )
        self.conversation.pack(fill="both", expand=True, padx=1, pady=1)
        self.conversation.tag_configure(
            "user_name", foreground=COL_USER, font=self.f_body_bold,
            spacing1=10, lmargin1=4, lmargin2=4,
        )
        self.conversation.tag_configure(
            "didi_name", foreground=COL_ACCENT, font=self.f_body_bold,
            spacing1=10, lmargin1=4, lmargin2=4,
        )
        self.conversation.tag_configure("msg", lmargin1=16, lmargin2=16, spacing3=6)
        self.conversation.tag_configure(
            "meta", foreground=COL_MUTED, font=self.f_small, justify="center",
        )

    def _build_activity(self):
        frame = self._card("Activity log", row=4)
        self.activity = scrolledtext.ScrolledText(
            frame, wrap="word", font=self.f_mono, bg=COL_SURFACE, fg=COL_MUTED,
            relief="flat", bd=0, padx=14, pady=10, state="disabled",
            highlightthickness=0, height=6,
        )
        self.activity.pack(fill="both", expand=True, padx=1, pady=1)

    def _card(self, title, row):
        """A titled surface panel that grows with the window."""
        outer = tk.Frame(self.root, bg=COL_BG)
        outer.grid(row=row, column=0, sticky="nsew", padx=PAD,
                   pady=(6, PAD if row == 4 else 6))
        tk.Label(outer, text=title.upper(), font=self.f_small, bg=COL_BG,
                 fg=COL_MUTED).pack(anchor="w", pady=(0, 4))
        inner = tk.Frame(outer, bg=COL_BORDER)
        inner.pack(fill="both", expand=True)
        return inner

    def _bind_keys(self):
        self.root.bind("<space>", self._on_key_trigger)
        self.root.bind("<Return>", self._on_key_trigger)
        self.mic_button.focus_set()

    # ---------- state + animation ----------

    def _set_state(self, state):
        self._state = state
        color, glyph, word = STATE_STYLE.get(state, ("#555", "●", state))
        self.status_dot.configure(text=glyph, fg=color)
        self.status_text.configure(text=word, fg=COL_TEXT)
        self.status_chip.configure(highlightbackground=color)
        busy = state in _ANIMATED_STATES
        if not busy:
            self.mic_button.configure(text="🎤   Speak")

    def _animate_status(self):
        """Subtle trailing dots on the status word while the assistant is busy."""
        if not self._alive:
            return
        if self._state in _ANIMATED_STATES:
            self._anim_step = (self._anim_step + 1) % 4
            _, _, word = STATE_STYLE[self._state]
            self.status_text.configure(text=word + "." * self._anim_step)
        self.root.after(400, self._animate_status)

    # ---------- button feedback ----------

    def _on_hover_in(self, _event):
        if self.mic_button["state"] != "disabled":
            self.mic_button.configure(bg=COL_ACCENT_HOVER)

    def _on_hover_out(self, _event):
        if self.mic_button["state"] != "disabled":
            self.mic_button.configure(bg=COL_ACCENT)

    # ---------- text helpers ----------

    def _append(self, widget, text, *tags):
        widget.configure(state="normal")
        widget.insert("end", text, tags or ())
        widget.see("end")
        widget.configure(state="disabled")

    @staticmethod
    def _log_icon(text):
        low = text.lower()
        if "opened" in low:
            return "▶"
        if "closed" in low or "close skipped" in low:
            return "⏹"
        if "screenshot" in low:
            return "📸"
        if "gemini" in low:
            return "💬"
        if "fail" in low or "error" in low or "could not" in low:
            return "⚠"
        if "exit" in low or "shutting" in low:
            return "⏻"
        return "•"

    # ---------- worker plumbing ----------

    def _emit(self, event_type, payload):
        """Called from the worker thread; hand the event to the UI thread."""
        self.events.put((event_type, payload))

    def _run_in_background(self, target):
        if self._worker and self._worker.is_alive():
            return
        self.mic_button.configure(state="disabled", cursor="arrow", bg=COL_DISABLED_BG)

        def wrapper():
            try:
                target()
            except Exception as error:  # keep the GUI alive no matter what
                self._emit("log", f"Unexpected error ({error})")
                self._emit("state", STATE_ERROR)
            finally:
                self._emit("_worker_done", None)

        self._worker = threading.Thread(target=wrapper, daemon=True)
        self._worker.start()

    def _busy(self):
        return bool(self._worker and self._worker.is_alive())

    def _on_mic_click(self):
        if not self._busy():
            self._run_in_background(self.assistant.run_interaction)

    def _on_key_trigger(self, _event):
        if not self._busy():
            self._on_mic_click()
        return "break"

    def _drain_events(self):
        if not self._alive:
            return
        try:
            while True:
                event_type, payload = self.events.get_nowait()
                self._handle_event(event_type, payload)
        except queue.Empty:
            pass
        self.root.after(80, self._drain_events)

    def _handle_event(self, event_type, payload):
        if event_type == "state":
            self._set_state(payload)
        elif event_type == "transcript":
            self._append(self.conversation, "You\n", "user_name")
            self._append(self.conversation, f"{payload}\n", "msg")
        elif event_type == "message":
            speaker, text = payload
            self._append(self.conversation, f"{speaker}\n", "didi_name")
            self._append(self.conversation, f"{text}\n", "msg")
        elif event_type == "log":
            self._append(self.activity, f"{self._log_icon(payload)}  {payload}\n")
        elif event_type == "exit":
            self._append(self.activity, "⏻  Shutting down...\n")
            self.root.after(1200, self._on_close)
        elif event_type == "_worker_done":
            self.mic_button.configure(state="normal", cursor="hand2", bg=COL_ACCENT)
            self.mic_button.focus_set()

    # ---------- shutdown ----------

    def _on_close(self):
        self._alive = False
        try:
            self.root.destroy()
        except tk.TclError:
            pass


def main():
    root = tk.Tk()
    CatCodeDidiGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
