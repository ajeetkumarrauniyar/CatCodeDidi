"""CatCodeDidi desktop GUI (CustomTkinter presentation layer).

Holds no assistant logic. Each interaction runs on a background thread; the
worker reports progress through a thread-safe queue that is drained on the Tk
main thread, so the window never blocks while listening, recognising, calling
Gemini or speaking.

Assistant -> GUI events (all via the queue):
    ("state",      "Ready" | "Listening..." | ... )
    ("status",     "short caption under the mic")
    ("transcript", "what the user said")
    ("message",    (speaker, text))
    ("error",      (title, body))
    ("activity",   (kind, text))          kind: open|close|shot|ai|warn|ok|info
    ("exit",       None)
"""

import datetime
import queue
import threading

import customtkinter as ctk

import theme
from assistant import STATE_ERROR, STATE_READY, Assistant
from config import BOT_NAME
from widgets import ActivityRow, MessageCard, MicOrb, section_header

TAGLINE = "Personal voice assistant"
MAX_ACTIVITY_ROWS = 4


def _now():
    return datetime.datetime.now().strftime("%H:%M")


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

        ctk.set_appearance_mode("dark")
        root.title(BOT_NAME)
        root.configure(fg_color=theme.BG)
        root.geometry("900x900")
        root.minsize(720, 680)
        root.protocol("WM_DELETE_WINDOW", self._shutdown)

        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(2, weight=1, minsize=220)

        self._build_header()
        self._build_voice_core()
        self._build_conversation()
        self._build_activity()

        root.bind("<space>", self._key_trigger)
        root.bind("<Return>", self._key_trigger)

        self._empty_state()
        self._drain_events()
        self._tick()
        self._run(self.assistant.startup_greeting)

    # ---------------------------------------------------------------- layout

    def _pad(self):
        return theme.SPACE_5

    def _build_header(self):
        bar = ctk.CTkFrame(self.root, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=self._pad(), pady=(theme.SPACE_5, theme.SPACE_3))

        dot = ctk.CTkFrame(bar, width=46, height=46, corner_radius=theme.RADIUS_PILL,
                           fg_color=theme.ACCENT)
        dot.grid(row=0, column=0, rowspan=2)
        dot.grid_propagate(False)
        ctk.CTkLabel(dot, text="\U0001F431", font=("", 22)).place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            bar, text=BOT_NAME,
            font=ctk.CTkFont(family=theme.ui_family(), size=theme.SIZE_DISPLAY, weight="bold"),
            text_color=theme.TEXT,
        ).grid(row=0, column=1, sticky="sw", padx=theme.SPACE_3)
        ctk.CTkLabel(
            bar, text=TAGLINE,
            font=ctk.CTkFont(family=theme.ui_family(), size=theme.SIZE_META),
            text_color=theme.MUTED,
        ).grid(row=1, column=1, sticky="nw", padx=theme.SPACE_3)

    def _build_voice_core(self):
        card = ctk.CTkFrame(self.root, corner_radius=theme.RADIUS_LG, fg_color=theme.SURFACE)
        card.grid(row=1, column=0, sticky="ew", padx=self._pad(), pady=theme.SPACE_2)
        card.grid_columnconfigure(0, weight=1)

        # Status pill
        self.pill = ctk.CTkFrame(card, corner_radius=theme.RADIUS_PILL, fg_color=theme.SURFACE_2)
        self.pill.grid(row=0, column=0, pady=(theme.SPACE_3, 0))
        self.pill_dot = ctk.CTkLabel(
            self.pill, text="●", font=ctk.CTkFont(size=theme.SIZE_LABEL, weight="bold"),
            text_color=theme.READY,
        )
        self.pill_dot.pack(side="left", padx=(theme.SPACE_3, theme.SPACE_1), pady=theme.SPACE_1)
        self.pill_text = ctk.CTkLabel(
            self.pill, text="Ready",
            font=ctk.CTkFont(family=theme.ui_family(), size=theme.SIZE_LABEL, weight="bold"),
            text_color=theme.TEXT,
        )
        self.pill_text.pack(side="left", padx=(0, theme.SPACE_3), pady=theme.SPACE_1)

        self.orb = MicOrb(card, on_press=self._trigger)
        self.orb.grid(row=1, column=0, pady=(theme.SPACE_2, 0))

        self.caption = ctk.CTkLabel(
            card, text="Tap the mic and speak", height=22,
            font=ctk.CTkFont(family=theme.ui_family(), size=theme.SIZE_MIC),
            text_color=theme.TEXT_2,
        )
        self.caption.grid(row=2, column=0, pady=(theme.SPACE_1, 0))
        self.hint = ctk.CTkLabel(
            card, text="or press Space", height=14,
            font=ctk.CTkFont(family=theme.ui_family(), size=theme.SIZE_META),
            text_color=theme.MUTED,
        )
        self.hint.grid(row=3, column=0, pady=(0, theme.SPACE_4))

    def _build_conversation(self):
        wrap = ctk.CTkFrame(self.root, fg_color="transparent")
        wrap.grid(row=2, column=0, sticky="nsew", padx=self._pad(), pady=theme.SPACE_2)
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(1, weight=1)

        section_header(wrap, "Conversation").grid(row=0, column=0, sticky="w", pady=(0, theme.SPACE_1))
        self.convo = ctk.CTkScrollableFrame(wrap, corner_radius=theme.RADIUS_MD,
                                            fg_color=theme.SURFACE)
        self.convo.grid(row=1, column=0, sticky="nsew")
        self.convo.grid_columnconfigure(0, weight=1)
        self.convo.bind("<Configure>", self._on_convo_resize)

    def _build_activity(self):
        wrap = ctk.CTkFrame(self.root, fg_color="transparent")
        wrap.grid(row=3, column=0, sticky="ew", padx=self._pad(), pady=(theme.SPACE_2, theme.SPACE_5))
        wrap.grid_columnconfigure(0, weight=1)

        section_header(wrap, "Activity").grid(row=0, column=0, sticky="w", pady=(0, theme.SPACE_1))
        self.activity = ctk.CTkFrame(wrap, corner_radius=theme.RADIUS_MD, fg_color=theme.SURFACE)
        self.activity.grid(row=1, column=0, sticky="ew")
        self.activity.grid_columnconfigure(0, weight=1)
        self._activity_rows = []

    # ------------------------------------------------------------- conversation

    def _empty_state(self):
        self._empty = ctk.CTkLabel(
            self.convo,
            text="Say a command and it appears here.\n"
                 "Try  “open Google Chrome”,  “take a screenshot”,  or ask a question.",
            justify="center",
            font=ctk.CTkFont(family=theme.ui_family(), size=theme.SIZE_BODY),
            text_color=theme.MUTED,
        )
        self._empty.grid(row=0, column=0, pady=theme.SPACE_6, padx=theme.SPACE_4)

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
        card.grid(row=len(self._cards), column=0, sticky="ew", pady=theme.SPACE_1, padx=theme.SPACE_1)
        self._cards.append(card)
        self.root.after(20, self._scroll_convo_end)

    def _scroll_convo_end(self):
        try:
            self.convo._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def _add_activity(self, kind, text):
        row = ActivityRow(self.activity, kind, text, _now())
        row.grid(row=len(self._activity_rows), column=0, sticky="ew",
                 padx=theme.SPACE_3, pady=2)
        self._activity_rows.append(row)
        while len(self._activity_rows) > MAX_ACTIVITY_ROWS:
            self._activity_rows.pop(0).destroy()
            for i, r in enumerate(self._activity_rows):
                r.grid_configure(row=i)

    # ------------------------------------------------------------------ states

    def _set_state(self, state):
        self._state = state
        color, glyph, word = theme.STATE_META.get(state, (theme.TEXT_2, "●", state))
        self.pill_dot.configure(text=glyph, text_color=color)
        self.pill_text.configure(text=word)
        self.orb.set_state(state)
        if state == STATE_READY:
            self.caption.configure(text="Tap the mic and speak", text_color=theme.TEXT_2)
        elif state == STATE_ERROR:
            self.caption.configure(text="Something needs your attention", text_color=theme.ERROR)

    def _tick(self):
        if not self._alive:
            return
        if self._state in theme.ANIMATED_STATES:
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
        self.orb.set_enabled(False)

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
        if not self._busy():
            self._run(self.assistant.run_interaction)

    def _key_trigger(self, _event):
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
            self.caption.configure(text=payload, text_color=theme.TEXT_2)
        elif event_type == "transcript":
            self._add_card("You", payload, "user")
        elif event_type == "message":
            speaker, text = payload
            self._add_card(speaker, text, "assistant")
        elif event_type == "error":
            title, body = payload
            self._add_card(BOT_NAME, body, "error", title=title)
        elif event_type == "activity":
            kind, text = payload
            self._add_activity(kind, text)
        elif event_type == "exit":
            self._add_activity("info", "Shutting down")
            self.root.after(1100, self._shutdown)
        elif event_type == "_done":
            self.orb.set_enabled(True)

    # -------------------------------------------------------------- shutdown

    def _shutdown(self):
        if not self._alive:
            return
        self._alive = False
        try:
            self.root.destroy()
        except Exception:
            pass


def main():
    root = ctk.CTk()
    CatCodeDidiGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
