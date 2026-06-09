"""Кросс-провайдерные тесты транспортного контракта на моках.

Каждый провайдер (OpenAI/Anthropic/Gemini) уже покрыт своим набором мок-тестов
со спецификой SDK (system-реплики, маппинг ролей, content-блоки). Здесь —
*единый* набор, который прогоняет один и тот же контракт ``LLMProvider`` через
**все** зарегистрированные реализации, подтверждая, что они образуют
согласованное семейство за фабрикой ``create_provider``:

- ``complete`` возвращает сырой текст ответа модели;
- сбой SDK/транспорта оборачивается в ``ProviderError`` с маскированием ключа;
- пустой ответ модели → ``ProviderError``;
- клиент SDK создаётся лениво и кэшируется (один экземпляр на провайдер);
- ключ не утекает в ``repr``.

Назначение блока — поймать расхождение будущей реализации с контрактом
(например, провайдер, забывший замаскировать ключ или обернуть ошибку), а не
дублировать проверки специфики, которые живут в ``test_providers_<name>.py``.
"""

from types import SimpleNamespace

import anthropic
import openai
import pytest
from google import genai

from arena.config import ModelParams, ResolvedModel
from arena.models import MessageRecord
from arena.providers import (
    AnthropicProvider,
    GeminiProvider,
    OpenAIProvider,
    ProviderError,
    create_provider,
    registered_providers,
)

API_KEY = "secret-key-value-123"


# --- адаптеры под SDK каждого провайдера -------------------------------------
#
# У всех трёх SDK разная форма клиента и ответа, поэтому единый контрактный тест
# параметризуется «делом» (Case): как собрать ``ResolvedModel``, как подменить
# конструктор клиента фейком и как слепить нормальный/пустой ответ под конкретный
# SDK. Сам фейк-клиент у всех одинаков по поведению (фиксирует ключ/вызовы,
# отдаёт ответ или бросает ошибку) — различается лишь точкой вызова create.


def _model(provider: str, model_id: str) -> ResolvedModel:
    return ResolvedModel(
        id=model_id,
        provider=provider,
        display_name=model_id,
        params=ModelParams(temperature=0.2, max_tokens=1024),
        api_key_env=f"{provider.upper()}_API_KEY",
        api_key=API_KEY,
    )


def _make_fake_client(call_attr_path):
    """Сконструировать класс фейк-клиента, вешающий ``_call`` по пути SDK.

    ``call_attr_path`` — например ``("chat", "completions", "create")``:
    клиент выставляет вложенные ``SimpleNamespace`` так, что итоговый атрибут —
    наш перехватчик, фиксирующий вызовы и отдающий ответ/ошибку.
    """

    class _FakeClient:
        def __init__(self, api_key, captured, response=None, error=None):
            captured["api_key"] = api_key
            captured["ctor_calls"] = captured.get("ctor_calls", 0) + 1
            self._captured = captured
            self._response = response
            self._error = error
            # Собрать цепочку атрибутов до метода-перехватчика.
            node = self
            for attr in call_attr_path[:-1]:
                child = SimpleNamespace()
                setattr(node, attr, child)
                node = child
            setattr(node, call_attr_path[-1], self._call)

        def _call(self, **kwargs):
            self._captured["call_kwargs"] = kwargs
            self._captured["call_count"] = self._captured.get("call_count", 0) + 1
            if self._error is not None:
                raise self._error
            return self._response

    return _FakeClient


class _Case:
    """Описание одного провайдера для параметризации контрактных тестов."""

    def __init__(
        self,
        name,
        provider_cls,
        model_id,
        sdk_module,
        client_attr,
        call_attr_path,
        ok_response,
        empty_response,
    ):
        self.name = name
        self.provider_cls = provider_cls
        self.model_id = model_id
        self._sdk_module = sdk_module
        self._client_attr = client_attr
        self._fake_cls = _make_fake_client(call_attr_path)
        self._ok_response = ok_response
        self._empty_response = empty_response

    def model(self):
        return _model(self.name, self.model_id)

    def provider(self):
        return self.provider_cls(self.model())

    def install(self, monkeypatch, captured, response=None, error=None):
        fake_cls = self._fake_cls

        def factory(api_key):
            return fake_cls(api_key, captured, response=response, error=error)

        monkeypatch.setattr(self._sdk_module, self._client_attr, factory)

    def ok_response(self, text):
        return self._ok_response(text)

    def empty_response(self):
        return self._empty_response()


CASES = [
    _Case(
        name="openai",
        provider_cls=OpenAIProvider,
        model_id="gpt-4o",
        sdk_module=openai,
        client_attr="OpenAI",
        call_attr_path=("chat", "completions", "create"),
        ok_response=lambda text: SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=text))]
        ),
        # content=None → пустой ответ для OpenAI.
        empty_response=lambda: SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=None))]
        ),
    ),
    _Case(
        name="anthropic",
        provider_cls=AnthropicProvider,
        model_id="claude-opus-4-8",
        sdk_module=anthropic,
        client_attr="Anthropic",
        call_attr_path=("messages", "create"),
        ok_response=lambda text: SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)]
        ),
        # нет text-блоков → пустой ответ для Anthropic.
        empty_response=lambda: SimpleNamespace(content=[]),
    ),
    _Case(
        name="gemini",
        provider_cls=GeminiProvider,
        model_id="gemini-2.5-pro",
        sdk_module=genai,
        client_attr="Client",
        call_attr_path=("models", "generate_content"),
        ok_response=lambda text: SimpleNamespace(text=text),
        # text="" → пустой ответ для Gemini.
        empty_response=lambda: SimpleNamespace(text=""),
    ),
]

CASE_IDS = [c.name for c in CASES]


def _msgs():
    return [
        MessageRecord(role="system", content="rules"),
        MessageRecord(role="user", content="your move"),
    ]


# --- единый контракт всех провайдеров ----------------------------------------


def test_all_known_providers_registered():
    """Все три провайдера зарегистрированы (их модули импортированы в __init__)."""
    assert set(registered_providers()) == {"openai", "anthropic", "gemini"}


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_factory_builds_matching_provider(case):
    provider = create_provider(case.model())
    assert isinstance(provider, case.provider_cls)
    assert provider.name == case.name


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_complete_returns_raw_text(case, monkeypatch):
    captured: dict = {}
    case.install(monkeypatch, captured, response=case.ok_response("Nf3 is best"))
    provider = case.provider()

    out = provider.complete(_msgs(), provider.model.params)

    assert out == "Nf3 is best"
    assert captured["call_count"] == 1


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_sdk_error_wrapped_and_key_masked(case, monkeypatch):
    captured: dict = {}
    # Текст исключения SDK содержит ключ — он не должен утечь в ProviderError.
    err = RuntimeError(f"401 unauthorized api_key={API_KEY}")
    case.install(monkeypatch, captured, error=err)
    provider = case.provider()

    with pytest.raises(ProviderError) as ei:
        provider.complete(_msgs(), provider.model.params)

    msg = str(ei.value)
    assert API_KEY not in msg
    assert "***" in msg
    assert case.model_id in msg


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_empty_response_raises(case, monkeypatch):
    captured: dict = {}
    case.install(monkeypatch, captured, response=case.empty_response())
    provider = case.provider()

    with pytest.raises(ProviderError, match="пустой ответ"):
        provider.complete(_msgs(), provider.model.params)


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_client_created_lazily_and_cached(case, monkeypatch):
    captured: dict = {}
    case.install(monkeypatch, captured, response=case.ok_response("ok"))
    provider = case.provider()

    # До первого complete клиент SDK ещё не создан.
    assert "ctor_calls" not in captured

    provider.complete(_msgs(), provider.model.params)
    provider.complete(_msgs(), provider.model.params)

    assert captured["api_key"] == API_KEY
    assert captured["ctor_calls"] == 1  # клиент закэширован между вызовами
    assert captured["call_count"] == 2


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_repr_never_leaks_key(case):
    text = repr(case.provider())
    assert API_KEY not in text
    assert case.name in text and case.model_id in text
