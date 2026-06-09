"""Тесты провайдера Anthropic на моках транспорта (без реальных сетевых вызовов).

Клиент SDK (``anthropic.Anthropic``) подменяется фейком, который фиксирует
переданные аргументы и отдаёт заранее заданный ответ/ошибку. Проверяем:
вынос system-реплик в параметр ``system`` с ``cache_control`` (prompt caching,
D-017), трансляцию остального диалога и ``ModelParams`` в Messages API, сборку
текста из content-блоков, ленивое кэширование клиента, обёртку ошибок в
``ProviderError`` и маскирование ключа.
"""

from types import SimpleNamespace

import anthropic
import pytest

from arena.config import ModelParams, ResolvedModel
from arena.models import MessageRecord
from arena.providers import (
    AnthropicProvider,
    ProviderError,
    create_provider,
    registered_providers,
)

API_KEY = "sk-ant-secret-value-123"


def _model(model_id: str = "claude-opus-4-8") -> ResolvedModel:
    return ResolvedModel(
        id=model_id,
        provider="anthropic",
        display_name="Claude Opus 4.8",
        params=ModelParams(temperature=0.2, max_tokens=1024),
        api_key_env="ANTHROPIC_API_KEY",
        api_key=API_KEY,
    )


def _response(*texts):
    """Фейковый ответ Messages API: список ``text``-блоков с заданным текстом."""
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=t) for t in texts]
    )


class _FakeClient:
    def __init__(self, api_key, captured, response=None, error=None):
        captured["api_key"] = api_key
        captured["ctor_calls"] = captured.get("ctor_calls", 0) + 1
        self._captured = captured
        self._response = response
        self._error = error
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self._captured["create_kwargs"] = kwargs
        self._captured["create_calls"] = self._captured.get("create_calls", 0) + 1
        if self._error is not None:
            raise self._error
        return self._response


def _install_fake(monkeypatch, captured, response=None, error=None):
    def factory(api_key):
        return _FakeClient(api_key, captured, response=response, error=error)

    monkeypatch.setattr(anthropic, "Anthropic", factory)


def _msgs():
    return [
        MessageRecord(role="system", content="rules"),
        MessageRecord(role="user", content="your move"),
    ]


# --- регистрация / фабрика ---------------------------------------------------

def test_registered_under_anthropic():
    assert "anthropic" in registered_providers()


def test_create_via_factory_returns_anthropic_provider():
    provider = create_provider(_model())
    assert isinstance(provider, AnthropicProvider)
    assert provider.name == "anthropic"


# --- complete: трансляция, system и извлечение текста ------------------------

def test_complete_returns_text_and_passes_params(monkeypatch):
    captured: dict = {}
    _install_fake(monkeypatch, captured, response=_response("Nf3 is best"))
    provider = AnthropicProvider(_model("claude-opus-4-8"))

    out = provider.complete(_msgs(), ModelParams(temperature=0.7, max_tokens=42))

    assert out == "Nf3 is best"
    kwargs = captured["create_kwargs"]
    assert kwargs["model"] == "claude-opus-4-8"
    assert kwargs["temperature"] == 0.7
    assert kwargs["max_tokens"] == 42
    # system-реплика ушла в отдельный параметр, в messages — только не-system.
    assert kwargs["messages"] == [{"role": "user", "content": "your move"}]


def test_complete_omits_temperature_when_none(monkeypatch):
    captured: dict = {}
    _install_fake(monkeypatch, captured, response=_response("ok"))
    provider = AnthropicProvider(_model("claude-opus-4-8"))

    provider.complete(_msgs(), ModelParams(temperature=None, max_tokens=42))

    kwargs = captured["create_kwargs"]
    assert "temperature" not in kwargs  # None → параметр не передаётся (модель его отвергает)
    assert kwargs["max_tokens"] == 42


def test_system_prefix_cached(monkeypatch):
    captured: dict = {}
    _install_fake(monkeypatch, captured, response=_response("ok"))
    provider = AnthropicProvider(_model())

    provider.complete(_msgs(), provider.model.params)

    system = captured["create_kwargs"]["system"]
    assert system == [
        {
            "type": "text",
            "text": "rules",
            "cache_control": {"type": "ephemeral"},
        }
    ]


def test_multiple_system_messages_joined(monkeypatch):
    captured: dict = {}
    _install_fake(monkeypatch, captured, response=_response("ok"))
    provider = AnthropicProvider(_model())

    msgs = [
        MessageRecord(role="system", content="rules"),
        MessageRecord(role="system", content="format"),
        MessageRecord(role="user", content="go"),
    ]
    provider.complete(msgs, provider.model.params)

    assert captured["create_kwargs"]["system"][0]["text"] == "rules\n\nformat"


def test_no_system_param_when_no_system_messages(monkeypatch):
    captured: dict = {}
    _install_fake(monkeypatch, captured, response=_response("ok"))
    provider = AnthropicProvider(_model())

    provider.complete([MessageRecord(role="user", content="go")], provider.model.params)

    assert "system" not in captured["create_kwargs"]


def test_multiple_text_blocks_concatenated(monkeypatch):
    captured: dict = {}
    _install_fake(monkeypatch, captured, response=_response("Nf3", " then O-O"))
    provider = AnthropicProvider(_model())

    out = provider.complete(_msgs(), provider.model.params)

    assert out == "Nf3 then O-O"


def test_client_created_with_api_key_lazily_and_cached(monkeypatch):
    captured: dict = {}
    _install_fake(monkeypatch, captured, response=_response("ok"))
    provider = AnthropicProvider(_model())

    # До первого complete клиент ещё не создан.
    assert "ctor_calls" not in captured

    provider.complete(_msgs(), provider.model.params)
    provider.complete(_msgs(), provider.model.params)

    assert captured["api_key"] == API_KEY
    assert captured["ctor_calls"] == 1  # клиент закэширован
    assert captured["create_calls"] == 2


# --- ошибки ------------------------------------------------------------------

def test_sdk_error_wrapped_and_key_masked(monkeypatch):
    captured: dict = {}
    # Текст исключения SDK содержит ключ — он не должен утечь.
    err = RuntimeError(f"401 invalid x-api-key={API_KEY}")
    _install_fake(monkeypatch, captured, error=err)
    provider = AnthropicProvider(_model())

    with pytest.raises(ProviderError) as ei:
        provider.complete(_msgs(), provider.model.params)

    msg = str(ei.value)
    assert API_KEY not in msg
    assert "***" in msg
    assert "claude-opus-4-8" in msg


def test_empty_content_raises(monkeypatch):
    captured: dict = {}
    _install_fake(monkeypatch, captured, response=_response())  # нет блоков
    provider = AnthropicProvider(_model())

    with pytest.raises(ProviderError, match="пустой ответ"):
        provider.complete(_msgs(), provider.model.params)


def test_unexpected_shape_raises(monkeypatch):
    captured: dict = {}
    # content не итерируется → неожиданная форма ответа.
    _install_fake(monkeypatch, captured, response=SimpleNamespace(content=None))
    provider = AnthropicProvider(_model())

    with pytest.raises(ProviderError, match="неожиданная форма ответа"):
        provider.complete(_msgs(), provider.model.params)


# --- секреты -----------------------------------------------------------------

def test_repr_hides_key():
    text = repr(AnthropicProvider(_model()))
    assert API_KEY not in text
    assert "anthropic" in text and "claude-opus-4-8" in text
