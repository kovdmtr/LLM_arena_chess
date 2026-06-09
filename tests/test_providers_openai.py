"""Тесты провайдера OpenAI на моках транспорта (без реальных сетевых вызовов).

Клиент SDK (``openai.OpenAI``) подменяется фейком, который фиксирует переданные
аргументы и отдаёт заранее заданный ответ/ошибку. Проверяем: трансляцию
``MessageRecord``/``ModelParams`` в вызов Chat Completions, извлечение текста,
ленивое кэширование клиента, обёртку ошибок в ``ProviderError`` и маскирование
ключа.
"""

from types import SimpleNamespace

import openai
import pytest

from arena.config import ModelParams, ResolvedModel
from arena.models import MessageRecord
from arena.providers import (
    OpenAIProvider,
    ProviderError,
    create_provider,
    registered_providers,
)

API_KEY = "sk-secret-value-123"


def _model(model_id: str = "gpt-4o") -> ResolvedModel:
    return ResolvedModel(
        id=model_id,
        provider="openai",
        display_name="GPT-4o",
        params=ModelParams(temperature=0.2, max_tokens=1024),
        api_key_env="OPENAI_API_KEY",
        api_key=API_KEY,
    )


def _response(content):
    """Фейковый ответ Chat Completions с заданным ``content``."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


class _FakeClient:
    def __init__(self, api_key, captured, response=None, error=None):
        captured["api_key"] = api_key
        captured["ctor_calls"] = captured.get("ctor_calls", 0) + 1
        self._captured = captured
        self._response = response
        self._error = error
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    def _create(self, **kwargs):
        self._captured["create_kwargs"] = kwargs
        self._captured["create_calls"] = self._captured.get("create_calls", 0) + 1
        if self._error is not None:
            raise self._error
        return self._response


def _install_fake(monkeypatch, captured, response=None, error=None):
    def factory(api_key):
        return _FakeClient(api_key, captured, response=response, error=error)

    monkeypatch.setattr(openai, "OpenAI", factory)


def _msgs():
    return [
        MessageRecord(role="system", content="rules"),
        MessageRecord(role="user", content="your move"),
    ]


# --- регистрация / фабрика ---------------------------------------------------

def test_registered_under_openai():
    assert "openai" in registered_providers()


def test_create_via_factory_returns_openai_provider():
    provider = create_provider(_model())
    assert isinstance(provider, OpenAIProvider)
    assert provider.name == "openai"


# --- complete: трансляция и извлечение текста --------------------------------

def test_complete_returns_text_and_passes_params(monkeypatch):
    captured: dict = {}
    _install_fake(monkeypatch, captured, response=_response("Nf3 is best"))
    provider = OpenAIProvider(_model("gpt-4o"))

    out = provider.complete(_msgs(), ModelParams(temperature=0.7, max_tokens=42))

    assert out == "Nf3 is best"
    kwargs = captured["create_kwargs"]
    assert kwargs["model"] == "gpt-4o"
    assert kwargs["temperature"] == 0.7
    assert kwargs["max_tokens"] == 42
    assert kwargs["messages"] == [
        {"role": "system", "content": "rules"},
        {"role": "user", "content": "your move"},
    ]


def test_client_created_with_api_key_lazily_and_cached(monkeypatch):
    captured: dict = {}
    _install_fake(monkeypatch, captured, response=_response("ok"))
    provider = OpenAIProvider(_model())

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
    err = RuntimeError(f"401 invalid api_key={API_KEY}")
    _install_fake(monkeypatch, captured, error=err)
    provider = OpenAIProvider(_model())

    with pytest.raises(ProviderError) as ei:
        provider.complete(_msgs(), provider.model.params)

    msg = str(ei.value)
    assert API_KEY not in msg
    assert "***" in msg
    assert "gpt-4o" in msg


def test_none_content_raises(monkeypatch):
    captured: dict = {}
    _install_fake(monkeypatch, captured, response=_response(None))
    provider = OpenAIProvider(_model())

    with pytest.raises(ProviderError, match="пустой ответ"):
        provider.complete(_msgs(), provider.model.params)


def test_unexpected_shape_raises(monkeypatch):
    captured: dict = {}
    _install_fake(monkeypatch, captured, response=SimpleNamespace(choices=[]))
    provider = OpenAIProvider(_model())

    with pytest.raises(ProviderError, match="неожиданная форма ответа"):
        provider.complete(_msgs(), provider.model.params)


# --- секреты -----------------------------------------------------------------

def test_repr_hides_key():
    text = repr(OpenAIProvider(_model()))
    assert API_KEY not in text
    assert "openai" in text and "gpt-4o" in text
