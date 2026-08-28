# CatCodeDidi

CatCodeDidi is a beginner-friendly, Hindi-speaking **desktop voice assistant**.
Press a microphone button, speak a command, and watch her state, the recognized
command, her reply, and the actions she takes — all in one window.

The project grows in small, understandable phases. This is the polished
cross-platform GUI phase.

---

## Features

- 🎤 **Voice control** — click the mic (or press <kbd>Space</kbd>), speak one command.
- 🗣️ **Hindi text-to-speech** — replies are spoken aloud (gTTS).
- 🖥️ **Open / close desktop apps** by voice (`open Google Chrome`, `close Google Chrome`).
- 📸 **Screenshots** — saved to a `screenshots/` folder and reported in the log.
- 🤖 **Gemini answers** for anything that isn't a built-in command, via the
  official `google-genai` SDK and a fast Flash-Lite model.
- 🙋 **Creator query** — "who is your father".
- 👋 **Exit by voice** — `shutdown`, `bye`, `good night`, …
- 🧵 **Responsive UI** — recognition, Gemini and audio run on a background
  thread, so the window never freezes.
- ⚠️ **Graceful errors** — a missing app, no microphone, or an AI failure shows
  a message in the GUI instead of crashing.

---

## Requirements

| Thing | Version / note |
|---|---|
| Python | 3.10 or newer |
| OS | Windows 10/11, macOS 12+, or a Linux desktop |
| Internet | required — speech recognition and Gemini are online services |
| Microphone | any working input device |
| Gemini API key | only needed for AI answers (see [Gemini configuration](#gemini-configuration)) |

**System-level dependencies** (a `pip install` alone is *not* enough):

| Package | Needs | Windows | macOS | Linux |
|---|---|---|---|---|
| `PyAudio` | PortAudio | bundled in the pip wheel | `brew install portaudio` | `portaudio19-dev` (Debian) / `portaudio-devel` (Fedora) |
| `tkinter` | Tk | bundled with python.org installer | bundled with python.org installer; Homebrew needs `brew install python-tk` | `python3-tk` / `python3-tkinter` / `tk` |
| `playsound3` | an audio backend | bundled (WinMM) | bundled (`afplay`) | GStreamer or `ffmpeg` (usually already present) |
| `pyscreenshot` | a screenshot backend | bundled | bundled | X11: works out of the box; Wayland may need `gnome-screenshot` or `grim` |

---

## Installation

The flow is the same everywhere:

1. Install Python 3.10+
2. Download / clone this project
3. Open a terminal in the project folder
4. Install the system dependency for your OS (table above)
5. Create and activate a virtual environment
6. `pip install -r requirements.txt`
7. `cp .env.example .env` and add your Gemini key (optional, for AI answers)
8. `python main.py`

### Windows (PowerShell)

```powershell
# 1. System deps: nothing extra — the python.org installer includes Tkinter,
#    and the PyAudio wheel includes PortAudio.

# 2. Virtual environment
python -m venv .venv
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
# 1. System deps
brew install portaudio          # for PyAudio
brew install python-tk          # only if you use Homebrew's Python

# 2. Virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# 4. Gemini key (optional — skip for local commands only)
cp .env.example .env
nano .env               # paste your key into GEMINI_API_KEY

# 5. Run
python main.py
```

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
command still works — CatCodeDidi tells you in the activity log that AI answers
are off, and only free-form questions show a "key not configured" message.

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

The CatCodeDidi window opens and greets you. Click **🎤 Speak** (or press
<kbd>Space</kbd> / <kbd>Enter</kbd>) and say one command. The status pill shows
where she is in the cycle:

```
Ready → Listening → Processing → Speaking → Ready
```

The button is disabled while she is busy, so only one interaction runs at a time.

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

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: No module named '_tkinter'` | Install Tk: Homebrew → `brew install python-tk`; Debian → `sudo apt install python3-tk`; Fedora → `sudo dnf install python3-tkinter`. |
| `pip install pyaudio` fails to build | Install PortAudio first (see the table above), then reinstall. On Apple Silicon: `export CFLAGS="-I$(brew --prefix portaudio)/include" LDFLAGS="-L$(brew --prefix portaudio)/lib"`. |
| Status goes to **Error**, "Koi microphone nahi mila" | No input device detected — connect a microphone. |
| "Microphone use nahi ho pa raha" / permission error | Grant microphone permission (Windows: Settings → Privacy → Microphone; macOS: System Settings → Privacy & Security → Microphone; Linux: check PulseAudio/PipeWire). |
| "Samajh nahi aaya" every time | Background noise or an online outage — speak clearly and check your connection. |
| Speech recognition never returns | It now times out after ~8 s of silence and returns to **Ready**. |
| `take a screenshot` fails on Linux | Install `gnome-screenshot` or `grim` (Wayland). |
| "Gemini API key not configured" | No `GEMINI_API_KEY` in `.env`. Copy `.env.example` to `.env` and add your key. Local commands still work without it. |
| "Gemini API key galat ya invalid" | The key is wrong, revoked, or has no Gemini access — regenerate it at <https://aistudio.google.com/apikey>. |
| "Model '…' available nahi hai" | `GEMINI_MODEL` is misspelled or retired. Remove the line to use the default, or set a current model (see [Which model](#which-model-and-why)). |
| "Gemini abhi busy hai (rate limit)" | Free-tier quota hit — wait a minute and try again. |
| No sound on Linux | Ensure GStreamer or `ffmpeg` is installed for `playsound3`. |

---

## Project structure

```
main.py         entry point — launches the GUI
gui.py          Tkinter window (presentation only) + background-thread plumbing
assistant.py    Assistant class — runs one listen → route → respond → speak cycle
router.py       maps recognized text to a response + activity-log lines
commands.py     cross-platform open/close app, screenshot, creator-query check
speech.py       microphone capture, Google recognition, Hindi TTS, playback
personality.py  time-based greeting text
gemini_ai.py    Gemini via the google-genai SDK; one reused client, stateless
                requests, low thinking level; raises GeminiError with safe messages
config.py       BOT_NAME, LANGUAGE
data.py         static command / creator-query data
utils.py        reserved for later phases
```

Data flow:

```
main → gui → assistant → router ─┬─ commands
      (Tk,   (orchestr.)         ├─ gemini_ai
       threads)                  ├─ personality
                                 └─ data
```

The GUI holds no assistant logic; `assistant.py` holds no GUI code.

---

## Cross-platform notes

| Area | Windows | macOS | Linux |
|---|---|---|---|
| Open app | `AppOpener` (Start-menu fuzzy match) | `open -a`, with a fallback scan of `/Applications` for a close name (`Chrome` → `Google Chrome`) | look up an executable on `PATH` and launch it detached |
| Close app | `AppOpener` | `osascript … quit app` | `pkill -i` |
| Screenshot | `pyscreenshot` | `pyscreenshot` | `pyscreenshot` (X11 native; Wayland needs a helper) |
| TTS playback | WinMM | `afplay` | GStreamer / `ffmpeg` via `playsound3` |
| Temp audio file | `tempfile` (created, closed, then written — Windows-safe) | same | same |
| Gemini API | identical everywhere — `google-genai` over HTTPS, no OS-specific code; `.env` via `python-dotenv` |

**Tested on:** macOS 15 (Apple Silicon), Python 3.13, Tk 9.0 — full interaction
cycle, all commands, resize, error paths, and **live Gemini** calls with a real
key (`gemini-3.5-flash-lite`, and error paths for invalid key / bad model).
**Not physically tested:** Windows and Linux. Those code paths are exercised by
`platform.system()` branches and were reviewed statically; verify with the
commands above. Application *names* differ across OSes — use the name as it
appears on your system.

---

## Roadmap

1. **Phase 1 — Refactor & make robust.** ✅
2. **Phase 2 — Desktop GUI, cross-platform polish, modern Gemini SDK.** ✅ *(this phase)*
3. **Phase 3 — AI:** richer conversation, tool use / function calling.
4. **Phase 4 — Search + AI:** retrieval, summarisation, scoped automation.
