import pytest

import gemini_ai


def test_is_configured(no_gemini_key):
    assert gemini_ai.is_configured() is False


def test_is_configured_true(fake_key):
    assert gemini_ai.is_configured() is True


def test_model_name_default(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    assert gemini_ai.model_name() == gemini_ai.DEFAULT_MODEL


def test_model_name_override(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.6-flash")
    assert gemini_ai.model_name() == "gemini-3.6-flash"


def test_ask_gemini_without_key_raises(no_gemini_key):
    with pytest.raises(gemini_ai.GeminiError) as exc:
        gemini_ai.ask_gemini("hello")
    assert "GEMINI_API_KEY" in str(exc.value)


def test_ask_gemini_blank_prompt(fake_key):
    with pytest.raises(gemini_ai.GeminiError):
        gemini_ai.ask_gemini("   ")


@pytest.mark.parametrize("err, needle", [
    (type("E", (Exception,), {"code": 403})(), "key"),
    (Exception("API key not valid"), "key"),
    (type("E", (Exception,), {"code": 404})(), "available nahi"),
    (Exception("RESOURCE_EXHAUSTED: quota"), "rate limit"),
    (Exception("connection timed out"), "time"),
    (Exception("failed to connect: network unreachable"), "connect"),
    (Exception("weird"), "fail"),
])
def test_friendly_error_mapping(err, needle):
    assert needle in gemini_ai._friendly_error(err).lower()


def test_ask_gemini_success(fake_key, monkeypatch):
    class Resp:
        text = "  the answer  "

    class Models:
        def generate_content(self, **kw):
            assert kw["model"] == gemini_ai.DEFAULT_MODEL
            return Resp()

    class Client:
        models = Models()

    monkeypatch.setattr(gemini_ai, "_get_client", lambda: Client())
    assert gemini_ai.ask_gemini("hi") == "the answer"


def test_ask_gemini_empty_response(fake_key, monkeypatch):
    class Resp:
        text = ""

    class Client:
        class models:
            @staticmethod
            def generate_content(**kw):
                return Resp()

    monkeypatch.setattr(gemini_ai, "_get_client", lambda: Client())
    with pytest.raises(gemini_ai.GeminiError, match="khaali"):
        gemini_ai.ask_gemini("hi")


def test_ask_gemini_retries_without_thinking(fake_key, monkeypatch):
    calls = []

    def fake_generate(prompt, with_thinking):
        calls.append(with_thinking)
        if with_thinking:
            raise Exception("thinking_level not supported by this model")
        class R:
            text = "ok"
        return R()

    monkeypatch.setattr(gemini_ai, "_generate", fake_generate)
    assert gemini_ai.ask_gemini("hi") == "ok"
    assert calls == [True, False]


def test_ask_gemini_api_error_becomes_safe_message(fake_key, monkeypatch):
    def fake_generate(prompt, with_thinking):
        raise Exception("401 API key not valid: AIzaSyXXXXSECRET")

    monkeypatch.setattr(gemini_ai, "_generate", fake_generate)
    with pytest.raises(gemini_ai.GeminiError) as exc:
        gemini_ai.ask_gemini("hi")
    assert "AIzaSy" not in str(exc.value)          # never leak the key
    assert "key" in str(exc.value).lower()
