# CatCodeDidi Voice Assistant

CatCodeDidi is a beginner-friendly Hindi-speaking desktop voice assistant. This project intentionally grows in small, understandable phases instead of jumping directly to AI.

## Installation

Use Python 3.10 or newer, then install the project dependencies from this folder:

```powershell
pip install -r requirements.txt
```

## Run

```powershell
python main.py
```

Speak one of these commands:

- `open Google Chrome`
- `close Google Chrome`
- `who is your father`
- `shutdown`

## Architecture

The project deliberately uses a flat root layout:

- `main.py`: starts the assistant, listens, and routes commands.
- `speech.py`: microphone input, speech recognition, and Hindi text-to-speech.
- `commands.py`: application open/close commands and creator-query detection.
- `personality.py`: time-based greeting and personality responses.
- `config.py`: configuration constants.
- `data.py`: static command data.
- `utils.py`: reserved generic helpers for later phases.

The current architecture contains no AI, search, browser, or automation modules beyond opening and closing local applications.

## Roadmap

1. **Phase 1 — Refactor and make robust:** preserve the original assistant while learning modules, imports, project structure, and separation of concerns.
2. **Phase 2 — Assistant maxxing without AI:** add search, extraction, parsing, and information retrieval.
3. **Phase 3 — AI:** add a modular AI provider only after the non-AI fundamentals are understood.
4. **Phase 4 — Search plus AI:** combine retrieval, summarisation, and carefully scoped automation.