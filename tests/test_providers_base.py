"""Тесты базового интерфейса провайдера и фабрики по имени.

Конкретные SDK здесь не нужны: проверяем контракт ``LLMProvider`` и поведение
реестра/фабрики на фейковой реализации (как и предписано для слоя провайдеров —
тесты без реальных сетевых вызовов).
"""

import pytest

from arena.config import ModelParams, ResolvedModel
from arena.models import MessageRecord
from arena.providers import (
    LLMProvider,
    ProviderError,
    create_provider,
    register_provider,
    registered_providers,
)
from arena.providers import base as base_mod


@pytest.fixture(autouse=True)
def _clean_registry():
    """Изолируем глобальный реестр провайдеров между тестами."""
    saved = dict(base_mod._REGISTRY)
    base_mod._REGISTRY.clear()
    try:
        yield
    finally:
        base_mod._REGISTRY.clear()
        base_mod._REGISTRY.update(saved)


def _model(provider: str = "fake", model_id: str = "fake-1") -> ResolvedModel:
    return ResolvedModel(
        id=model_id,
        provider=provider,
        display_name="Fake",
        params=ModelParams(temperature=0.3, max_tokens=64),
        api_key_env="FAKE_API_KEY",
        api_key="sk-secret-value",
    )


class _FakeProvider(LLMProvider):
    """Минимальная реализация: возвращает echo последнего сообщения + params."""

    def complete(self, messages, params):
        last = messages[-1].content if messages else ""
        return f"echo[{params.temperature}]:{last}"


# --- интерфейс LLMProvider ---------------------------------------------------

def test_provider_is_abstract():
    with pytest.raises(TypeError):
        LLMProvider(_model())  # type: ignore[abstract]


def test_complete_returns_text_and_sees_params():
    provider = _FakeProvider(_model())
    msgs = [
        MessageRecord(role="system", content="rules"),
        MessageRecord(role="user", content="your move"),
    ]
    out = provider.complete(msgs, ModelParams(temperature=0.7, max_tokens=10))
    assert out == "echo[0.7]:your move"


def test_name_comes_from_model_provider():
    assert _FakeProvider(_model(provider="openai")).name == "openai"


def test_repr_hides_api_key():
    text = repr(_FakeProvider(_model()))
    assert "sk-secret-value" not in text
    assert "fake" in text and "fake-1" in text


# --- реестр и фабрика --------------------------------------------------------

def test_register_and_create_by_name():
    register_provider("fake")(_FakeProvider)
    assert registered_providers() == ["fake"]
    provider = create_provider(_model(provider="fake"))
    assert isinstance(provider, _FakeProvider)
    assert provider.model.id == "fake-1"


def test_create_unknown_provider_raises():
    with pytest.raises(ProviderError, match="неизвестный провайдер 'ghost'"):
        create_provider(_model(provider="ghost"))


def test_register_rejects_non_provider():
    with pytest.raises(TypeError, match="ожидался подкласс LLMProvider"):
        register_provider("bad")(int)


def test_duplicate_registration_rejected():
    register_provider("fake")(_FakeProvider)

    class _Other(LLMProvider):
        def complete(self, messages, params):
            return ""

    with pytest.raises(ProviderError, match="уже зарегистрирован"):
        register_provider("fake")(_Other)


def test_idempotent_registration_same_class_ok():
    register_provider("fake")(_FakeProvider)
    # повторная регистрация того же класса не должна падать
    register_provider("fake")(_FakeProvider)
    assert registered_providers() == ["fake"]


def test_create_instantiates_per_call():
    register_provider("fake")(_FakeProvider)
    a = create_provider(_model())
    b = create_provider(_model())
    assert a is not b  # фабрика хранит класс, а не singleton
