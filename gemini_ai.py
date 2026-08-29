"""Gemini integration for CatCodeDidi.

Uses the current official Google Gen AI SDK (``google-genai``, the
client-based ``from google import genai`` API). The legacy
``google-generativeai`` package (``genai.configure`` + ``GenerativeModel`` +
``start_chat``) is no longer used.

Design goals for a voice assistant:
- reuse one Client across requests (no per-command re-init);
- stateless single-turn requests -> no conversation-history growth;
- low "thinking level" -> fast responses for short commands;
- every failure raises GeminiError with a short, safe, user-facing message
  (never a stack trace, never the API key).
"""

import os

from dotenv import load_dotenv

load_dotenv()

# gemini-3.5-flash-lite: current GA model, positioned by Google as the
# fastest / most cost-effective Flash-Lite class model for low-latency,
# high-volume conversational use - the right fit for a desktop assistant.
# Override with GEMINI_MODEL without touching this file.
DEFAULT_MODEL = "gemini-3.5-flash-lite"

# Keep this short: a large system prompt adds latency to every request.
SYSTEM_INSTRUCTION = (
    "You are Cat Code Didi, a friendly female desktop voice assistant. "
    "Address yourself as 'Didi', never literally say 'I am a girl'. "
    "English input -> reply in natural English. Hindi / Hinglish input -> "
    "reply in natural Hinglish (Roman script only, never Devanagari). "
    "Keep answers short and conversational - they are read aloud. "
    "Preserve code, commands, filenames, URLs and product names exactly."
)


class GeminiError(RuntimeError):
    """A Gemini configuration, network or API failure with a safe message."""


_client = None
_client_key = None


def is_configured():
    """True if an API key is present (used for a friendly startup notice)."""
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


def model_name():
    return os.environ.get("GEMINI_MODEL", "").strip() or DEFAULT_MODEL


def prewarm():
    """Import the SDK and build the client now (call from a background thread).

    The `google.genai` import is heavy; doing it once at startup keeps the
    first real question from stalling the UI thread.
    """
    if is_configured():
        try:
            _get_client()
        except GeminiError:
            pass


def _require_key():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise GeminiError(
            "Gemini API key not configured. Add GEMINI_API_KEY to your .env "
            "file (get one at https://aistudio.google.com/apikey)."
        )
    return key


def _get_client():
    """Return a cached genai.Client, rebuilding only if the key changed."""
    global _client, _client_key
    key = _require_key()
    if _client is not None and _client_key == key:
        return _client
    try:
        from google import genai
        from google.genai import types
    except ImportError as error:
        raise GeminiError(
            "The 'google-genai' package is missing. Run: "
            "pip install -r requirements.txt"
        ) from error
    _client = genai.Client(
        api_key=key,
        # Bound every request so the assistant can never hang forever.
        http_options=types.HttpOptions(timeout=20_000),  # milliseconds
    )
    _client_key = key
    return _client


def _friendly_error(error):
    """Map an SDK/API exception to a short user-facing message (no secrets)."""
    text = str(error).lower()
    code = getattr(error, "code", None) or getattr(error, "status_code", None)
    if code in (401, 403) or "api key" in text or "permission" in text or "unauthenticated" in text:
        return "Gemini API key galat ya invalid lag rahi hai. .env mein GEMINI_API_KEY check kijiye."
    if code == 404 or "not found" in text or "not supported" in text:
        return f"Model '{model_name()}' available nahi hai. GEMINI_MODEL check kijiye."
    if code == 429 or "quota" in text or "rate limit" in text or "resource_exhausted" in text:
        return "Gemini abhi busy hai (rate limit). Thodi der baad phir try kijiye."
    if "timeout" in text or "timed out" in text or "deadline" in text:
        return "Gemini ne time pe jawab nahi diya. Phir se try kijiye."
    if "connect" in text or "network" in text or "dns" in text or "unavailable" in text:
        return "Gemini se connect nahi ho paya. Internet check kijiye."
    return f"Gemini request fail ho gayi ({type(error).__name__})."


def _generate(prompt, with_thinking):
    from google.genai import types
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        # We never pass tools; disabling AFC skips a check and silences a warning.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    if with_thinking:
        # "low" = minimise latency/cost, good for simple instruction following.
        config.thinking_config = types.ThinkingConfig(thinking_level="low")
    return _get_client().models.generate_content(
        model=model_name(), contents=prompt, config=config,
    )


def ask_gemini(prompt):
    """Send one prompt to Gemini and return the reply text.

    Raises GeminiError (with a short, safe message) on any failure.
    """
    prompt = (prompt or "").strip()
    if not prompt:
        raise GeminiError("Koi sawaal nahi mila.")

    try:
        response = _generate(prompt, with_thinking=True)
    except GeminiError:
        raise
    except Exception as first_error:
        # A non-Gemini-3 model set via GEMINI_MODEL may reject thinking_level;
        # retry once without it before giving up.
        try:
            response = _generate(prompt, with_thinking=False)
        except Exception:
            raise GeminiError(_friendly_error(first_error)) from first_error

    text = (getattr(response, "text", None) or "").strip()
    if not text:
        raise GeminiError("Gemini ne khaali jawab bheja. Thodi der baad phir try kijiye.")
    return text
