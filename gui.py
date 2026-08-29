"""CatCodeDidi desktop GUI (CustomTkinter presentation layer).

Holds no assistant logic. Each interaction runs on a background thread; the
worker reports progress through a thread-safe queue that is drained on the Tk
main thread, so the window never blocks while listening, recognising, calling
Gemini or speaking.

Assistant -> GUI events (all via the queue):
    ("state",      "Ready" | "Listening..." | ... )
    ("status",     "short caption shown in the interaction dock")
    ("transcript", "what the user said")
    ("message",    (speaker, text))
    ("error",      (title, body))
    ("activity",   (kind, text))          kind: open|close|shot|ai|warn|ok|info
    ("exit",       None)

"activity" events are diagnostics (which app opened, where a screenshot went,
why Gemini failed). They are no longer shown in the window - anything the user
needs to act on arrives as an "error" card instead - but they are still logged,
so `python main.py` remains debuggable.
"""

import datetime
import logging
import queue
import threading

import customtkinter as ctk

import theme
from assistant import STATE_ERROR, STATE_READY, Assistant
from config import BOT_NAME
from widgets import MessageCard, MicOrb, section_header

TAGLINE = "Personal voice assistant"

MODE_VOICE = "Voice Mode"
MODE_TEXT = "Text Mode"

# Idle caption + hint per mode, so the dock always says what to do next.
_MODE_PROMPTS = {
    MODE_VOICE: ("Tap the mic and speak", "or press Space"),
    MODE_TEXT: ("Type your message", "press Enter to send"),
}

log = logging.getLogger("catcodedidi")


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
        self._mode = MODE_VOICE

        ctk.set_appearance_mode("dark")
        root.title(BOT_NAME)
        root.configure(fg_color=theme.BG)
        root.geometry("900x900")
        root.minsize(720, 680)
        root.protocol("WM_DELETE_WINDOW", self._shutdown)

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
        ctk.CTkLabel(
            dot, text=theme.glyph(dot, "cat"), font=("", 22),
        ).place(relx=0.5, rely=0.5, anchor="center")

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
        self.orb.grid(row=1, column=0, pady=(theme.SPACE_2, theme.SPACE_4))

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

    def _build_dock(self):
        """The interaction dock: everything the user acts through.

        Today it grounds the layout with the live status line and the keyboard
        hint. `self.controls` is the row the Voice / Text mode switch, the text
        field and the mute control drop into next - laid out as a three-column
        strip (leading | flexible middle | trailing) so those can be added
        without moving anything else.
        """
        dock = ctk.CTkFrame(self.root, corner_radius=theme.RADIUS_LG,
                            fg_color=theme.SURFACE)
        dock.grid(row=3, column=0, sticky="ew", padx=self._pad(),
                  pady=(theme.SPACE_2, theme.SPACE_5))
        dock.grid_columnconfigure(0, weight=1)
        self.dock = dock

        self.caption = ctk.CTkLabel(
            dock, text="Tap the mic and speak", height=22,
            font=ctk.CTkFont(family=theme.ui_family(), size=theme.SIZE_MIC),
            text_color=theme.TEXT_2,
        )
        self.caption.grid(row=0, column=0, pady=(theme.SPACE_4, 0))

        self.hint = ctk.CTkLabel(
            dock, text="or press Space", height=14,
            font=ctk.CTkFont(family=theme.ui_family(), size=theme.SIZE_META),
            text_color=theme.MUTED,
        )
        self.hint.grid(row=1, column=0, pady=(0, theme.SPACE_4))

        self.controls = ctk.CTkFrame(dock, fg_color="transparent", height=0)
        self.controls.grid(row=2, column=0, sticky="ew",
                           padx=theme.SPACE_4, pady=(0, theme.SPACE_4))
        self.controls.grid_columnconfigure(0, weight=1)

        self._build_mode_switch()
        self._build_text_input()
        self._apply_mode()

    def _build_mode_switch(self):
        """Segmented control: the input method, and nothing else, changes."""
        self.mode_switch = ctk.CTkSegmentedButton(
            self.controls, values=[MODE_VOICE, MODE_TEXT],
            command=self._on_mode_change,
            font=ctk.CTkFont(family=theme.ui_family(), size=theme.SIZE_LABEL,
                             weight="bold"),
            height=34, corner_radius=theme.RADIUS_SM, border_width=2,
            fg_color=theme.SURFACE_2,
            selected_color=theme.ACCENT, selected_hover_color=theme.ACCENT_BRIGHT,
            unselected_color=theme.SURFACE_2, unselected_hover_color=theme.ELEVATED,
            text_color=theme.TEXT,
        )
        self.mode_switch.set(self._mode)
        self.mode_switch.grid(row=0, column=0, pady=(0, theme.SPACE_3))

    def _build_text_input(self):
        """The composer, shown only in Text Mode."""
        self.text_row = ctk.CTkFrame(self.controls, fg_color="transparent")
        self.text_row.grid(row=1, column=0, sticky="ew")
        self.text_row.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkEntry(
            self.text_row, placeholder_text="Ask CatCodeDidi anything…",
            font=ctk.CTkFont(family=theme.ui_family(), size=theme.SIZE_BODY),
            height=44, corner_radius=theme.RADIUS_MD, border_width=1,
            fg_color=theme.SURFACE_2, border_color=theme.BORDER,
            text_color=theme.TEXT, placeholder_text_color=theme.MUTED,
        )
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, theme.SPACE_2))
        self.entry.bind("<Return>", self._submit_text)

        self.send_button = ctk.CTkButton(
            self.text_row, text="Send", width=88, height=44,
            font=ctk.CTkFont(family=theme.ui_family(), size=theme.SIZE_LABEL,
                             weight="bold"),
            corner_radius=theme.RADIUS_MD,
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_BRIGHT,
            text_color="#ffffff", command=self._submit_text,
        )
        self.send_button.grid(row=0, column=1)

    # ------------------------------------------------------------------- modes

    def _on_mode_change(self, value):
        if value != self._mode:
            self._mode = value
            self._apply_mode()

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
        if self._state == STATE_READY:
            self._set_idle_caption()

    def _set_idle_caption(self):
        caption, hint = _MODE_PROMPTS[self._mode]
        self.caption.configure(text=caption, text_color=theme.TEXT_2)
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

    # ------------------------------------------------------------------ states

    def _set_state(self, state):
        self._state = state
        color, glyph, word = theme.STATE_META.get(state, (theme.TEXT_2, "●", state))
        self.pill_dot.configure(text=glyph, text_color=color)
        self.pill_text.configure(text=word)
        self.orb.set_state(state)
        if state == STATE_READY:
            self._set_idle_caption()
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
            # Diagnostics only - kept out of the window, kept in the log.
            kind, text = payload
            log.warning("%s", text) if kind == "warn" else log.info("%s", text)
        elif event_type == "exit":
            log.info("Shutting down")
            self.root.after(1100, self._shutdown)
        elif event_type == "_done":
            self._sync_controls()
            if self._mode == MODE_TEXT:
                self.entry.focus_set()

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
