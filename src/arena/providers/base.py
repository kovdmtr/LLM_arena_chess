"""Базовый интерфейс LLM-провайдера и фабрика по имени провайдера.

Каждый провайдер (OpenAI/Anthropic/Gemini) реализует единый контракт
``LLMProvider.complete(messages, params) -> str``: принимает историю диалога и
параметры генерации, возвращает **сырой текст** ответа модели. Разбор текста в
``LLMResponse`` (D-007) и проверка легальности хода — задача вышестоящих слоёв,
а не провайдера.

Конкретные реализации регистрируются под именем провайдера декоратором
``register_provider``; ``create_provider`` строит экземпляр по ``ResolvedModel``
(имя провайдера + ключ + параметры). Это разрывает зависимость фабрики от
конкретных SDK: реализации подключаются в своих модулях (следующие задачи Phase 2),
а ядро фабрики о них ничего не знает.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import TypeVar

from arena.config import ResolvedModel
from arena.config.settings import ModelParams
from arena.models import MessageRecord


class ProviderError(RuntimeError):
    """Ошибка уровня провайдера.

    Покрывает как сбои транспорта/SDK у конкретной реализации, так и ошибки
    фабрики (неизвестный/незарегистрированный провайдер).
    """


class LLMProvider(ABC):
    """Единый интерфейс к LLM-провайдеру.

    Реализация инкапсулирует SDK конкретного провайдера и его API-ключ
    (через ``ResolvedModel``). ``complete`` переводит историю диалога в вызов
    модели и возвращает сырой текст; формат ответа (D-007) и легальность хода
    здесь не проверяются.

    Ключ не логируется и не попадает в ``repr`` — он живёт только внутри
    ``ResolvedModel`` (``api_key`` исключён из сериализации, D-003).
    """

    def __init__(self, model: ResolvedModel) -> None:
        self.model = model

    @property
    def name(self) -> str:
        """Имя провайдера, как в каталоге (``openai`` / ``anthropic`` / ``gemini``)."""
        return self.model.provider

    @abstractmethod
    def complete(
        self, messages: Sequence[MessageRecord], params: ModelParams
    ) -> str:
        """Вызвать модель на истории ``messages`` и вернуть сырой текст ответа.

        ``messages`` — диалог в порядке от старых к новым (system/user/assistant);
        ``params`` — параметры генерации (температура, лимит токенов). Реализация
        транслирует это в вызов своего SDK. При сбое поднимает ``ProviderError``.
        """
        raise NotImplementedError

    def __repr__(self) -> str:  # без ключа — только id/провайдер
        return f"{type(self).__name__}(provider={self.name!r}, model={self.model.id!r})"


# Фабрика хранит классы провайдеров (а не экземпляры): класс инстанцируется на
# каждый ``create_provider`` с конкретным ``ResolvedModel``.
_REGISTRY: dict[str, type[LLMProvider]] = {}

_P = TypeVar("_P", bound=type[LLMProvider])


def register_provider(name: str) -> "object":
    """Декоратор класса: зарегистрировать реализацию под именем провайдера ``name``.

    Имя должно совпадать со значением ``provider`` в каталоге моделей. Повторная
    регистрация того же имени — ошибка (защита от случайного затирания).
    """

    def decorator(cls: _P) -> _P:
        if not (isinstance(cls, type) and issubclass(cls, LLMProvider)):
            raise TypeError(
                f"register_provider({name!r}): ожидался подкласс LLMProvider, "
                f"получено {cls!r}"
            )
        existing = _REGISTRY.get(name)
        if existing is not None and existing is not cls:
            raise ProviderError(
                f"провайдер {name!r} уже зарегистрирован ({existing.__name__})"
            )
        _REGISTRY[name] = cls
        return cls

    return decorator


def registered_providers() -> list[str]:
    """Имена зарегистрированных провайдеров (отсортированы)."""
    return sorted(_REGISTRY)


def create_provider(model: ResolvedModel) -> LLMProvider:
    """Построить провайдера по ``ResolvedModel`` (фабрика по имени провайдера).

    ``ProviderError`` с понятным сообщением, если имя провайдера не
    зарегистрировано (например, его модуль-реализация не импортирован).
    """
    cls = _REGISTRY.get(model.provider)
    if cls is None:
        known = ", ".join(registered_providers()) or "<нет зарегистрированных>"
        raise ProviderError(
            f"неизвестный провайдер {model.provider!r}; "
            f"зарегистрированы: {known}"
        )
    return cls(model)
