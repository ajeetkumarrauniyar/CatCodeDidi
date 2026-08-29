# CatCodeDidi

CatCodeDidi is a friendly, Hindi-speaking **desktop voice assistant** with a
polished dark interface. Tap the mic (or press <kbd>Space</kbd>), speak a
command, and watch her state, your words, her reply, and the actions she takes.

---

## Features

- 🎤 **Voice Mode / Text Mode** — speak into the animated mic core, or type in
  the composer. Both feed the *same* pipeline, so commands and AI answers
  behave identically either way.
- 🔈 **Mute** — one global toggle in the dock silences spoken replies (and cuts
  off a sentence already playing). Everything else keeps working: recognition,
  typing, commands, Gemini, and every card in the conversation.
- 👂 **Wake word** *(optional)* — say **“Didi”**, **“Cat Code”** or
  **“Cat Code Didi”** to start a command hands-free. Fully offline; see
  [Wake word](#wake-word-optional).
- 🗣️ **Hindi text-to-speech** — replies are spoken aloud (gTTS).
- 🖥️ **Open / close desktop apps** by voice, per-OS (`open Google Chrome`).
- 📸 **Screenshots** — saved to `screenshots/`; permission problems are explained.
- 🤖 **Gemini answers** via the official `google-genai` SDK and a fast Flash-Lite
  model — shown in the conversation and spoken.
- 🙋 **Creator query** · 👋 **Exit by voice** (`shutdown`, `bye`, `good night`).
- 🧵 **Never freezes** — recognition, Gemini and audio run on a background thread.
- ⚠️ **Graceful errors** — a friendly card (what happened / what to do), never a
  traceback.

---

## Requirements

| Thing | Version / note |
|---|---|
| **Python** | **3.10 or newer, linked against Tcl/Tk 8.6+** (see [Python runtime](#python-runtime) — this matters on macOS) |
| OS | Windows 10/11, macOS 12–26, or a Linux desktop |
| Internet | required — speech recognition and Gemini are online services |
| Microphone | any working input device (permission prompt on first use) |
| Gemini API key | only for AI answers — see [Gemini configuration](#gemini-configuration) |

**System-level dependencies** (a `pip install` alone is *not* enough):

| Package | Needs | Windows | macOS | Linux |
|---|---|---|---|---|
| Python + Tk | **Tcl/Tk ≥ 8.6** | python.org installer ✓ | python.org installer ✓ · Homebrew needs `python-tk` | `python3-tk` / `python3-tkinter` / `tk` |
| `PyAudio` | PortAudio | bundled in the pip wheel | `brew install portaudio` | `portaudio19-dev` (Debian) / `portaudio-devel` (Fedora) |
| `playsound3` | an audio backend | bundled (WinMM) | bundled (`afplay`) | GStreamer or `ffmpeg` |
| `pyscreenshot` | a screenshot backend | bundled | Screen Recording permission | X11 ✓ · Wayland needs `gnome-screenshot` / `grim` |

`customtkinter` (the GUI toolkit) is a pure-Python pip install — no system parts.

---

## Python runtime

CatCodeDidi builds its window with Tk. **The Apple "Command Line Tools" Python
(3.9, at `/usr/bin/python3`) ships the obsolete Tcl/Tk 8.5, which aborts the
process on modern macOS** (`Tcl_Panic` in `TkpInit` → SIGABRT). CatCodeDidi
runs a preflight check and prints a clear message instead of crashing, but you
still need a good Python.

**Use one of these** (both bundle Tk 8.6+):

- the installer from **python.org** (3.10+), or
- **Homebrew**: `brew install python@3.13 python-tk@3.13`

**Verify before you build the venv** — all three lines must look right:

```bash
which python3.13        # NOT /usr/bin/python3 and NOT .../CommandLineTools/...
python3.13 --version    # 3.10 or newer
python3.13 -c "import tkinter; print(tkinter.TkVersion)"   # 8.6, 9.0, ... (never 8.5)
```

Then always create the virtual environment with that interpreter (below), and
run CatCodeDidi from inside the activated venv.

---

## Installation

The flow is the same everywhere:

1. Install a good Python (see [Python runtime](#python-runtime))
2. Download / clone this project, open a terminal in the folder
3. Install the system dependencies for your OS (table above)
4. Create and activate a virtual environment **with that Python**
5. `pip install -r requirements.txt`
6. `cp .env.example .env` and add your Gemini key (optional, for AI answers)
7. `python main.py`

### Windows (PowerShell)

```powershell
# 1. Python: install 3.10+ from python.org (includes Tk 8.6+ and the PyAudio wheel bundles PortAudio).

# 2. Virtual environment
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
# If activation is blocked:  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

# 3. Dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# 4. Gemini key (optional — skip for local commands only)
Copy-Item .env.example .env
notepad .env            # paste your key into GEMINI_API_KEY

# 5. Run
python main.py
```

### macOS (Terminal)

```bash
# 1. Python + system deps  (Homebrew shown; or use the python.org installer)
brew install python@3.13 python-tk@3.13 portaudio

# 2. Virtual environment — MUST be built with the Homebrew/python.org Python,
#    never /usr/bin/python3 (that one crashes, see "Python runtime" above)
/opt/homebrew/bin/python3.13 -m venv .venv
source .venv/bin/activate
python -c "import tkinter; print('Tk', tkinter.TkVersion)"   # expect 8.6 / 9.0

# 3. Dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# 4. Gemini key (optional — skip for local commands only)
cp .env.example .env
nano .env               # paste your key into GEMINI_API_KEY

# 5. Run
python main.py
```

> On Apple Silicon these are all native arm64 packages — nothing extra to do.
> The first run pops the macOS **Microphone** prompt; a screenshot command
> may also ask for **Screen Recording** (System Settings → Privacy & Security).

### Linux (Terminal)

Package names differ by distribution — install the equivalents for yours:

```bash
# Debian / Ubuntu / Mint
sudo apt update
sudo apt install python3-venv python3-tk portaudio19-dev

# Fedora
sudo dnf install python3-virtualenv python3-tkinter portaudio-devel

# Arch / Manjaro
sudo pacman -S python tk portaudio
```

Then:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env    # optional: then add your Gemini key
python main.py
```

> On **Wayland**, if `take a screenshot` fails, install `gnome-screenshot`
> (GNOME) or `grim` (wlroots) and try again.

---

## Gemini configuration

AI answers use Google's Gemini API through the official **`google-genai`** SDK
(the modern `from google import genai` client). Without a key, every built-in
command still works — CatCodeDidi notes in the terminal log that AI answers are
off, and only free-form questions show a "key not configured" message.

1. Get a free key from <https://aistudio.google.com/apikey>.
2. Copy `.env.example` to `.env` and paste your key:

   ```bash
   cp .env.example .env          # Windows PowerShell: Copy-Item .env.example .env
   ```

   ```dotenv
   GEMINI_API_KEY=your_api_key_here
   # optional — override the default model:
   GEMINI_MODEL=gemini-3.5-flash-lite
   ```

`.env` is git-ignored — never commit your key. It is loaded automatically at
startup and is never printed, logged, or shown in the GUI.

| Variable | Purpose | Default |
|---|---|---|
| `GEMINI_API_KEY` | your Gemini API key (required for AI answers) | *(none)* |
| `GEMINI_MODEL` | model id sent to Gemini | `gemini-3.5-flash-lite` |

### Which model, and why

The default is **`gemini-3.5-flash-lite`** — currently Google's fastest,
most cost-effective GA model, built for low-latency, high-volume conversational
use. That matches a voice assistant: many short requests where response speed
matters more than deep reasoning. Requests use a **low "thinking level"** so
simple commands ("tell me a joke", "what time is it") are not slowed down by
unnecessary reasoning.

To trade a little latency for more depth, set another current model, e.g.:

```dotenv
GEMINI_MODEL=gemini-3.6-flash      # stronger knowledge / coding
GEMINI_MODEL=gemini-3.7-flash      # most capable Flash
```

No code changes needed. If you pick an older model that doesn't support the
thinking setting, CatCodeDidi automatically retries the request without it.

---

## Running the assistant

```bash
python main.py
```

The window opens and greets you. Tap the **mic core** (or press <kbd>Space</kbd>
/ <kbd>Enter</kbd>) and say one command. The status pill and the mic animation
show where she is:

```
Ready → Listening → Working → Speaking → Ready
```

The mic is disabled while she's busy, so only one interaction runs at a time.
Every reply appears in the conversation the moment it's ready — before it is
spoken — so a slow or failed voice playback never hides the answer.

---

## Wake word (optional)

Hands-free listening is **off by default** and disabled until you install the
engine — it holds the microphone open and downloads a speech model, so it is
opt-in rather than something that starts behind your back.

```bash
pip install -r requirements-wake.txt
```

Then flip **Wake word** in the dock. The first switch-on downloads a ~40 MB
model into `~/.cache/vosk`; after that it is entirely offline. Say:

| Phrase | |
|---|---|
| “Cat Code Didi” | primary |
| “Didi” | short form |
| “Cat Code” | short form |

CatCodeDidi wakes, listens for your command, answers, and goes back to
waiting for the wake word. If the window is hidden, a wake word brings it
back first — see [Hiding and quitting](#hiding-and-quitting).

**How it works.** [Vosk](https://alphacephei.com/vosk/) (Apache-2.0) runs a
*grammar-restricted* recogniser: the decoder is given only the wake phrases
plus `[unk]`, so it is choosing between four options rather than transcribing
everything you say. **No audio leaves your machine** for wake detection —
Gemini and Google Web Speech are used only for a command you actually asked
for.

Measured on this machine (Apple Silicon, small en-us model): **~3.4 % of one
CPU core** and ~95 MB RSS while listening, with no false wakes over 20 s of
ambient room noise.

Notes:

- Wake listening pauses in **Text Mode** (the mic is not the input there) and
  while a command is being handled, so only one thing ever owns the microphone.
- **Muting does not stop wake detection** — mute silences CatCodeDidi's voice,
  it does not close her ears.
- The manual mic button keeps working exactly as before, with or without the
  wake word.

---

## Hiding and quitting

| Action | What happens |
|---|---|
| Close button, **wake word on** | The window hides; CatCodeDidi keeps listening in the background |
| Close button, **wake word off** | CatCodeDidi quits — nothing would be listening, so a hidden window would be unreachable |
| **Quit** in the header, or <kbd>Cmd/Ctrl</kbd>+<kbd>Q</kbd> | Always quits, whatever else is going on |
| Say a wake word while hidden | The window comes back and goes straight into listening |

**Wake detection stops when you quit.** It is a thread inside CatCodeDidi, not
a background service — once the process exits nothing is listening, and
nothing here pretends otherwise.

While hidden, the window stops repainting entirely; only the wake listener
keeps working.

**No menu-bar / tray icon**, deliberately. `pystray` is the usual choice, but
its `run()` must own the main thread — which Tk's `mainloop()` already does —
and its documented macOS workaround (`run_detached`) requires handing it the
`NSApplication` of the toolkit you are integrating with, which Tkinter does
not expose. Making that work would mean reaching into Tk's internals through
PyObjC and pulling in four extra packages. Hide/restore via the wake word plus
an always-visible Quit button gives the same control without that risk.

---

## Voice commands

| Say | What happens |
|---|---|
| `open Google Chrome` | launches the app (fuzzy-matched to installed apps) |
| `close Google Chrome` | quits the app |
| `take a screenshot` | saves a PNG to `screenshots/` and reports the path |
| `who is your father` | creator reply |
| `shutdown` / `bye` / `good night` / `good bye` | closes the assistant |
| anything else | sent to Gemini; the answer is shown and spoken |

---

## macOS permissions

CatCodeDidi asks for permission only when a feature needs it:

| Permission | When | If denied |
|---|---|---|
| **Microphone** | first voice command | error card: "Microphone access needed" → System Settings › Privacy & Security › Microphone → enable your terminal |
| **Screen Recording** | `take a screenshot` | error card explaining the same path for Screen Recording |

Grant them to the app you launch CatCodeDidi *from* (Terminal, iTerm, VS Code…).
No Accessibility/Automation permission is required — app launch uses `open`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| **App aborts / "Abort trap: 6" / `Tcl_Panic` in `TkpInit`** | You're on the Apple CLT Python 3.9 (Tk 8.5). Install python.org or Homebrew Python + `python-tk`, rebuild the venv. See [Python runtime](#python-runtime). |
| **"Unsupported Python runtime" / "Outdated Tcl/Tk"** on launch | Same cause — the preflight caught it. Follow the message. |
| `ModuleNotFoundError: No module named '_tkinter'` | Install Tk: `brew install python-tk@3.13` / `sudo apt install python3-tk` / `sudo dnf install python3-tkinter`. |
| `ModuleNotFoundError: customtkinter` | `pip install -r requirements.txt` inside the activated venv. |
| `pip install pyaudio` fails to build | Install PortAudio first, then reinstall. Apple Silicon: `export CFLAGS="-I$(brew --prefix portaudio)/include" LDFLAGS="-L$(brew --prefix portaudio)/lib"`. |
| Error card: **"No microphone found"** | Connect an input device. |
| Error card: **"Microphone access needed"** | Grant Microphone permission (see [macOS permissions](#macos-permissions); Windows: Settings › Privacy › Microphone; Linux: check PulseAudio/PipeWire). |
| Error card: **"Didn't catch that"** every time | Background noise or an outage — speak clearly, check your connection. |
| Nothing happens after ~8 s of speaking | It times out on silence and returns to **Ready** — tap again. |
| Screenshot card: **"permission chahiye"** (macOS) / fails (Linux) | Enable Screen Recording (macOS) or install `gnome-screenshot` / `grim` (Wayland). |
| "Gemini API key not configured" | Add `GEMINI_API_KEY` to `.env` (copy from `.env.example`). Local commands work without it. |
| "Gemini API key galat ya invalid" | Regenerate the key at <https://aistudio.google.com/apikey>. |
| "Model '…' available nahi hai" | Fix or remove `GEMINI_MODEL` (see [Which model](#which-model-and-why)). |
| "Gemini abhi busy hai (rate limit)" | Free-tier quota — wait a minute. |
| No TTS sound on Linux | Install GStreamer or `ffmpeg` for `playsound3`. |

---

## Project structure

```
main.py         entry point — macOS platform patch, runtime preflight, launch
gui.py          THE ENTIRE GUI, one file: design tokens, custom widgets
                (MicOrb, MuteToggle, MessageCard, Tooltip), the window and
                every event handler. Holds no assistant logic — it calls the
                services below. Sections: GUI CONFIGURATION · DESIGN TOKENS ·
                WIDGET HELPERS · CUSTOM WIDGETS · MAIN APPLICATION CLASS ·
                APPLICATION ENTRY POINT
assistant.py    Assistant — runs one listen → understand → act → respond → speak cycle
router.py       classify() (cheap peek) + route() (executes); returns response + activity
commands.py     per-OS open/close app, screenshot (permission-aware), creator check
speech.py       mic capture, Google recognition, Hindi TTS, interruptible
                playback, and the single-owner microphone guard
wakeword.py     optional offline wake word (Vosk, grammar-restricted)
personality.py  time-based greeting text
gemini_ai.py    google-genai SDK: one reused client, stateless requests, low thinking
config.py       BOT_NAME, LANGUAGE
data.py         static command / creator-query data
utils.py        reserved for later phases
```

Data flow. All user-interface code lives in `gui.py`; no service module
imports it, and there are no import cycles (both verified by the test suite):

```
main → gui ──queue──► assistant ──► router ─┬─ commands   (open/close/screenshot)
     (CustomTk,      (orchestration)         ├─ gemini_ai  (AI)
      threads)                               ├─ personality
                                             └─ data
       speech.py  ◄── mic / recognition / TTS
```

---

## Cross-platform notes

| Area | Windows | macOS | Linux |
|---|---|---|---|
| GUI | CustomTkinter on Tk 8.6+ — HiDPI scaling is automatic on all three |
| Emoji | probed at startup; Tk builds that can't show characters above U+FFFF get BMP glyphs and a vector-drawn mic instead |
| Open app | `AppOpener` (Start-menu fuzzy match) | `open -a` + a fallback scan of `/Applications` (`Chrome` → `Google Chrome`) | `PATH` lookup over the spoken name and its normalisations (`Google Chrome` → `google-chrome`), launched detached |
| Close app | `AppOpener` | `osascript … quit app` on the resolved bundle name | `pkill -i` over the same normalisations |
| Screenshot | `pyscreenshot` | `pyscreenshot` + black-frame check for denied Screen Recording | `pyscreenshot` (X11 native; Wayland needs a helper) |
| TTS playback | WinMM | `afplay` | GStreamer / `ffmpeg` via `playsound3` |
| Temp audio file | `tempfile` via `pathlib` — created, closed, *then* written, because Windows locks open handles |
| Screenshot folder | `screenshots/` beside the project, not the current working directory |
| Gemini API | identical everywhere — `google-genai` over HTTPS, no OS-specific code |

**Actually run:** macOS 26 (Apple Silicon), Homebrew Python 3.13, Tk 9.0 —
full interaction cycle, every command, live Gemini (`gemini-3.5-flash-lite`),
error cards, resize, keyboard trigger, clean shutdown, the preflight guard on a
simulated old Tk, and the whole UI rendered with emoji support forced off.

**Verified by test, not by running the OS:** the Windows and Linux branches are
pinned by `tests/test_cross_platform.py`, which mocks `platform.system()` and
asserts the exact commands issued (`AppOpener` calls on Windows, `PATH` lookup
and `pkill` normalisations on Linux), plus the path, temp-file and glyph rules
above. Real Windows/Linux hardware has **not** been used — please report
anything that differs.

Application *names* differ per OS — say the name as it appears on your system.

---

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

~225 tests covering command routing, per-OS command handlers (Windows and
Linux branches included), speech-error paths, the Gemini wrapper (mapping,
retries, "never leak the key"), time-based greeting, the `main.py` runtime
preflight, the assistant event sequence, the shared Voice/Text pipeline, the
mute control, wake-word matching and microphone ownership, colour/theme
helpers, and end-to-end GUI smoke tests.

- GUI tests are marked `gui` and skip themselves when no Tk display is available.
- `live` (real Gemini API) and `audio` (real sound, real Vosk decode) are
  **excluded from the default run** — they depend on external services, and a
  rate limit or a flaky network should not make `pytest` non-deterministic.
  Run them deliberately: `pytest -m live`, `pytest -m audio`.

---

## Roadmap

1. **Phase 1 — Refactor & make robust.** ✅
2. **Phase 2 — Desktop GUI, cross-platform reliability, modern Gemini SDK,
   premium redesign.** ✅ *(this phase)*
3. **Phase 3 — AI:** richer conversation, tool use / function calling.
4. **Phase 4 — Search + AI:** retrieval, summarisation, scoped automation.
