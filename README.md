# CatCodeDidi

CatCodeDidi is a friendly, Hindi-speaking voice assistant. Speak a command and
she opens apps, takes screenshots, or answers with Gemini — replying out loud
in Hinglish.

---

## Features

- 🎤 **Voice commands** — speech in, spoken reply out.
- 👂 **Wake word** *(optional)* — say **“Didi”**, **“Cat Code”** or
  **“Cat Code Didi”** hands-free. Fully offline; see [Wake word](#wake-word-optional).
- 🖥️ **Open / close desktop apps** by voice, on Windows, macOS and Linux.
- 📸 **Screenshots** — saved to `screenshots/`; permission problems are explained.
- 🤖 **Gemini answers** through the official `google-genai` SDK and a fast
  Flash-Lite model.
- 🔈 **Mute** — silence spoken replies (and cut off a sentence already playing)
  without disabling anything else.
- ⚠️ **Friendly errors** — every failure becomes a "what happened / what to do"
  message, never a traceback.

---

## Requirements

| Thing | Note |
|---|---|
| **Python** | 3.10 or newer |
| OS | Windows 10/11, macOS 12+, or a Linux desktop |
| Internet | speech recognition and Gemini are online services |
| Microphone | any working input device |
| Gemini API key | only for AI answers — see [Gemini configuration](#gemini-configuration) |

**System dependencies** (a `pip install` alone is *not* enough):

| Package | Needs | Windows | macOS | Linux |
|---|---|---|---|---|
| `PyAudio` | PortAudio | bundled in the wheel | `brew install portaudio` | `portaudio19-dev` / `portaudio-devel` |
| `playsound3` | an audio backend | bundled (WinMM) | bundled (`afplay`) | GStreamer or `ffmpeg` |
| `pyscreenshot` | a screenshot backend | bundled | Screen Recording permission | X11 ✓ · Wayland needs `gnome-screenshot` / `grim` |

---

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env               # then add your Gemini key
python main.py
```

Install the system dependency for your platform first:

```bash
brew install portaudio                                   # macOS
sudo apt install python3-venv portaudio19-dev            # Debian / Ubuntu
sudo dnf install python3-virtualenv portaudio-devel      # Fedora
sudo pacman -S python portaudio                          # Arch
```

---

## Gemini configuration

AI answers go through the official **`google-genai`** SDK (the modern
`from google import genai` client). Without a key every built-in command still
works; only free-form questions report that the key is missing.

1. Get a free key from <https://aistudio.google.com/apikey>.
2. Copy `.env.example` to `.env` and paste it in:

   ```dotenv
   GEMINI_API_KEY=your_api_key_here
   GEMINI_MODEL=gemini-3.5-flash-lite    # optional override
   ```

`.env` is git-ignored. The key is never printed, logged, or included in an
error message.

| Variable | Purpose | Default |
|---|---|---|
| `GEMINI_API_KEY` | your Gemini API key | *(none)* |
| `GEMINI_MODEL` | model id sent to Gemini | `gemini-3.5-flash-lite` |

### Which model, and why

The default is **`gemini-3.5-flash-lite`** — Google's fastest, most
cost-effective GA model, built for low-latency, high-volume conversational use.
That matches a voice assistant: many short requests where speed matters more
than depth. Requests use a **low thinking level** so simple commands are not
slowed by unnecessary reasoning.

For more depth set another current model — `gemini-3.6-flash` or
`gemini-3.7-flash` — with no code change. If a model rejects the thinking
setting, the request is retried once without it.

---

## Voice commands

| Say | What happens |
|---|---|
| `open Google Chrome` | launches the app (fuzzy-matched to what is installed) |
| `close Google Chrome` | quits the app |
| `take a screenshot` | saves a PNG to `screenshots/` and reports the path |
| `who is your father` | creator reply |
| `shutdown` / `bye` / `good night` | exits |
| anything else | answered by Gemini |

---

## Wake word (optional)

```bash
pip install -r requirements-wake.txt
```

Say **“Cat Code Didi”**, **“Didi”** or **“Cat Code”**. The first use downloads
a ~40 MB model into `~/.cache/vosk`; after that it is entirely offline.

**How it works.** [Vosk](https://alphacephei.com/vosk/) (Apache-2.0) runs a
*grammar-restricted* recogniser: the decoder is given only the wake phrases
plus `[unk]`, so it chooses between four options rather than transcribing
everything. **No audio leaves your machine** for wake detection — Gemini and
Google Web Speech only ever see a command you actually asked for.

Grammar mode maps every utterance onto the nearest allowed phrase, so
"what is the weather today" decodes as `[unk] didi`. A wake is therefore
accepted only when the decoded text is *exactly* a wake phrase. Measured over
three wake phrases and six negatives: all three accepted, all six rejected.

Measured while listening (Apple Silicon, small en-us model): **~3.4 % of one
CPU core**, ~95 MB RSS, no false wakes over 20 s of ambient noise.

Only one component ever holds the microphone: the wake listener releases it
before a command is captured and takes it back afterwards.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `pip install pyaudio` fails to build | Install PortAudio first, then reinstall. Apple Silicon: `export CFLAGS="-I$(brew --prefix portaudio)/include" LDFLAGS="-L$(brew --prefix portaudio)/lib"` |
| "Koi microphone nahi mila" | No input device — connect a microphone. |
| Microphone permission error | Windows: Settings → Privacy → Microphone. macOS: System Settings → Privacy & Security → Microphone. Linux: check PulseAudio / PipeWire. |
| Recognition never returns | It times out after ~8 s of silence. |
| Screenshot fails on Linux | Install `gnome-screenshot` or `grim` (Wayland). |
| Screenshot is blank on macOS | Grant Screen Recording permission. |
| "Gemini API key not configured" | Copy `.env.example` to `.env` and add your key. |
| "Model '…' available nahi hai" | `GEMINI_MODEL` is misspelled or retired. |
| No sound on Linux | Install GStreamer or `ffmpeg` for `playsound3`. |

---

## Project structure

```
main.py         entry point — console assistant loop
assistant.py    Assistant — one listen → understand → act → respond → speak cycle
router.py       classify() (cheap peek) + route() (executes)
commands.py     per-OS open/close app, screenshot, creator check
speech.py       mic capture, recognition, Hindi TTS, interruptible playback,
                and the single-owner microphone guard
wakeword.py     optional offline wake word (Vosk, grammar-restricted)
gemini_ai.py    google-genai SDK: one reused client, stateless requests
personality.py  time-based greeting
config.py       BOT_NAME, LANGUAGE
data.py         static command / creator-query data
utils.py        reserved for later phases
```

Every input method funnels into one pipeline, so a command behaves the same
however it arrived:

```
speech ─┐
        ├─► Assistant.process_user_input ─► classify ─► command | Gemini
typing ─┘                                        └─► display + speak
```

There is exactly one `router.route()` call site and one `ask_gemini()` call
site in the project — no parallel AI path can drift.

---

## Cross-platform notes

| Area | Windows | macOS | Linux |
|---|---|---|---|
| Open app | `AppOpener` | `open -a` + a scan of `/Applications` (`Chrome` → `Google Chrome`) | `PATH` lookup over the spoken name and its normalisations, launched detached |
| Close app | `AppOpener` | `osascript … quit app` | `pkill -i` over the same normalisations |
| Screenshot | `pyscreenshot` | + black-frame check for denied Screen Recording | X11 native; Wayland needs a helper |
| TTS playback | WinMM | `afplay` | GStreamer / `ffmpeg` |
| Temp audio | created, closed, *then* written — Windows locks open handles |
| Gemini | identical everywhere: HTTPS, no OS-specific code |

**Actually run:** macOS 26 (Apple Silicon), Python 3.13.
**Verified by test, not by running the OS:** the Windows and Linux branches are
pinned by `tests/test_cross_platform.py`, which mocks `platform.system()` and
asserts the exact commands issued. Real Windows/Linux hardware has not been
used — please report anything that differs.

---

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

~190 tests covering command routing, per-OS command handlers, speech-error
paths, the Gemini wrapper (error mapping, retries, "never leak the key"), the
time-based greeting, the assistant event sequence, the shared input pipeline,
the mute control, wake-word matching and microphone ownership.

`live` (real Gemini API) and `audio` (real sound, real Vosk decode) are
**excluded from the default run** — they depend on external services, and a
rate limit or flaky network should not make `pytest` non-deterministic. Run
them deliberately: `pytest -m live`, `pytest -m audio`.

---

## Roadmap

1. **Phase 1 — Refactor and make robust.** ✅
2. **Phase 2 — Cross-platform services, modern Gemini SDK, wake word.** ✅
3. **Phase 3 — AI:** richer conversation, tool use / function calling.
4. **Phase 4 — Search plus AI:** retrieval, summarisation, scoped automation.
