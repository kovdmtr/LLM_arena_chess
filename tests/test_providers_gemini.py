"""Тесты провайдера Gemini на моках транспорта (без реальных сетевых вызовов).

Клиент SDK (``google.genai.Client``) подменяется фейком, который фиксирует
переданные аргументы и отдаёт заранее заданный ответ/ошибку. Проверяем:
вынос system-реплик в ``system_instruction`` (D-018), маппинг роли
``assistant`` → ``model`` в ``contents``, трансляцию ``ModelParams`` в
``GenerateContentConfig`` (``max_tokens`` → ``max_output_tokens``), извлечение
``response.text``, ленивое кэширование клиента, обёртку ошибок в
``ProviderError`` и маскирование ключа.
"""

from types import SimpleNamespace

import pytest
from google import genai

from arena.config import ModelParams, ResolvedModel
from arena.models import MessageRecord
from arena.providers import (
    GeminiProvider,
    ProviderError,
    create_provider,
    registered_providers,
)

API_KEY = "AIza-secret-value-123"


def _model(model_id: str = "gemini-2.5-pro") -> ResolvedModel:
    return ResolvedModel(
        id=model_id,
        provider="gemini",
        display_name="Gemini 2.5 Pro",
        params=ModelParams(temperature=0.2, max_tokens=1024),
        api_key_env="GEMINI_API_KEY",
        api_key=API_KEY,
    )


def _response(text):
    """Фейковый ответ generate_content: объект со свойством ``text``."""
    return SimpleNamespace(text=text)


class _RaisingResponse:
    """Ответ, у которого доступ к ``text`` падает (неожиданная форма)."""

    @property
    def text(self):
        raise ValueError("no parts in candidate")


class _FakeClient:
    def __init__(self, api_key, captured, response=None, error=None):
        captured["api_key"] = api_key
        captured["ctor_calls"] = captured.get("ctor_calls", 0) + 1
        self._captured = captured
        self._response = response
        self._error = error
        self.models = SimpleNamespace(generate_content=self._generate)

    def _generate(self, **kwargs):
        self._captured["gen_kwargs"] = kwargs
        self._captured["gen_calls"] = self._captured.get("gen_calls", 0) + 1
        if self._error is not None:
            raise self._error
        return self._response


def _install_fake(monkeypatch, captured, response=None, error=None):
    def factory(api_key):
        return _FakeClient(api_key, captured, response=response, error=error)

    monkeypatch.setattr(genai, "Client", factory)


def _msgs():
    return [
        MessageRecord(role="system", content="rules"),
        MessageRecord(role="user", content="your move"),
    ]


# --- регистрация / фабрика ---------------------------------------------------

def test_registered_under_gemini():
    assert "gemini" in registered_providers()


def test_create_via_factory_returns_gemini_provider():
    provider = create_provider(_model())
    assert isinstance(provider, GeminiProvider)
    assert provider.name == "gemini"


# --- complete: трансляция, system и извлечение текста ------------------------

def test_complete_returns_text_and_passes_params(monkeypatch):
    captured: dict = {}
    _install_fake(monkeypatch, captured, response=_response("Nf3 is best"))
    provider = GeminiProvider(_model("gemini-2.5-pro"))

    out = provider.complete(_msgs(), ModelParams(temperature=0.7, max_tokens=42))

    assert out == "Nf3 is best"
    kwargs = captured["gen_kwargs"]
    assert kwargs["model"] == "gemini-2.5-pro"
    config = kwargs["config"]
    assert config.temperature == 0.7
    assert config.max_output_tokens == 42
    # system-реплика ушла в system_instruction, в contents — только не-system.
    assert config.system_instruction == "rules"
    assert kwargs["contents"] == [
        {"role": "user", "parts": [{"text": "your move"}]}
    ]


def test_assistant_role_mapped_to_model(monkeypatch):
    captured: dict = {}
    _install_fake(monkeypatch, captured, response=_response("ok"))
    provider = GeminiProvider(_model())

    msgs = [
        MessageRecord(role="system", content="rules"),
        MessageRecord(role="user", content="move 1?"),
        MessageRecord(role="assistant", content="e4"),
        MessageRecord(role="user", content="move 2?"),
    ]
    provider.complete(msgs, provider.model.params)

    assert captured["gen_kwargs"]["contents"] == [
        {"role": "user", "parts": [{"text": "move 1?"}]},
        {"role": "model", "parts": [{"text": "e4"}]},
        {"role": "user", "parts": [{"text": "move 2?"}]},
    ]


def test_multiple_system_messages_joined(monkeypatch):
    captured: dict = {}
    _install_fake(monkeypatch, captured, response=_response("ok"))
    provider = GeminiProvider(_model())

    msgs = [
        MessageRecord(role="system", content="rules"),
        MessageRecord(role="system", content="format"),
        MessageRecord(role="user", content="go"),
    ]
    provider.complete(msgs, provider.model.params)

    assert captured["gen_kwargs"]["config"].system_instruction == "rules\n\nformat"


def test_no_system_instruction_when_no_system_messages(monkeypatch):
    captured: dict = {}
    _install_fake(monkeypatch, captured, response=_response("ok"))
    provider = GeminiProvider(_model())

    provider.complete(
        [MessageRecord(role="user", content="go")], provider.model.params
    )

    assert captured["gen_kwargs"]["config"].system_instruction is None


def test_client_created_with_api_key_lazily_and_cached(monkeypatch):
    captured: dict = {}
    _install_fake(monkeypatch, captured, response=_response("ok"))
    provider = GeminiProvider(_model())

    # До первого complete клиент ещё не создан.
    assert "ctor_calls" not in captured

    provider.complete(_msgs(), provider.model.params)
    provider.complete(_msgs(), provider.model.params)

    assert captured["api_key"] == API_KEY
    assert captured["ctor_calls"] == 1  # клиент закэширован
    assert captured["gen_calls"] == 2


# --- ошибки ------------------------------------------------------------------

def test_sdk_error_wrapped_and_key_masked(monkeypatch):
    captured: dict = {}
    # Текст исключения SDK содержит ключ — он не должен утечь.
    err = RuntimeError(f"403 invalid key={API_KEY}")
    _install_fake(monkeypatch, captured, error=err)
    provider = GeminiProvider(_model())

    with pytest.raises(ProviderError) as ei:
        provider.complete(_msgs(), provider.model.params)

    msg = str(ei.value)
    assert API_KEY not in msg
    assert "***" in msg
    assert "gemini-2.5-pro" in msg


def test_empty_text_raises(monkeypatch):
    captured: dict = {}
    _install_fake(monkeypatch, captured, response=_response(""))
    provider = GeminiProvider(_model())

    with pytest.raises(ProviderError, match="пустой ответ"):
        provider.complete(_msgs(), provider.model.params)


def test_none_text_raises(monkeypatch):
    captured: dict = {}
    _install_fake(monkeypatch, captured, response=_response(None))
    provider = GeminiProvider(_model())

    with pytest.raises(ProviderError, match="пустой ответ"):
        provider.complete(_msgs(), provider.model.params)


def test_unexpected_shape_raises(monkeypatch):
    captured: dict = {}
    _install_fake(monkeypatch, captured, response=_RaisingResponse())
    provider = GeminiProvider(_model())

    with pytest.raises(ProviderError, match="неожиданная форма ответа"):
        provider.complete(_msgs(), provider.model.params)


# --- секреты -----------------------------------------------------------------

def test_repr_hides_key():
    text = repr(GeminiProvider(_model()))
    assert API_KEY not in text
    assert "gemini" in text and "gemini-2.5-pro" in text
