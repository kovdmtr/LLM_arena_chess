"""Реализация ``LLMProvider`` поверх официального SDK ``openai``.

Транслирует историю диалога (``MessageRecord``) в вызов Chat Completions и
возвращает сырой текст ответа модели (разбор в ``LLMResponse`` — задача
вышестоящего слоя, D-007). Модель OpenAI берётся из ``ResolvedModel.id``
(в каталоге ``id`` совпадает с именем модели API, напр. ``gpt-4o``).

Ключ живёт только внутри ``ResolvedModel`` (``api_key``, исключён из ``repr``,
D-003); при оборачивании ошибок SDK он маскируется через ``mask_secret``.
Регистрируется под именем провайдера ``openai`` (см. ``providers/__init__``).
"""

from __future__ import annotations

from collections.abc import Sequence

import openai

from arena.config import ResolvedModel
from arena.config.settings import ModelParams
from arena.models import MessageRecord
from arena.providers.base import (
    LLMProvider,
    ProviderError,
    mask_secret,
    register_provider,
)


@register_provider("openai")
class OpenAIProvider(LLMProvider):
    """Провайдер OpenAI (Chat Completions)."""

    def __init__(self, model: ResolvedModel) -> None:
        super().__init__(model)
        self._client: openai.OpenAI | None = None

    def _ensure_client(self) -> "openai.OpenAI":
        """Лениво создать и закэшировать клиент SDK с ключом из модели."""
        if self._client is None:
            self._client = openai.OpenAI(api_key=self.model.api_key)
        return self._client

    def complete(
        self, messages: Sequence[MessageRecord], params: ModelParams
    ) -> str:
        client = self._ensure_client()
        payload = [{"role": m.role, "content": m.content} for m in messages]
        try:
            response = client.chat.completions.create(
                model=self.model.id,
                messages=payload,
                temperature=params.temperature,
                max_tokens=params.max_tokens,
            )
        except Exception as exc:  # SDK/транспорт — единая ошибка слоя
            raise ProviderError(
                mask_secret(
                    f"openai: сбой запроса к модели {self.model.id!r}: {exc}",
                    self.model.api_key,
                )
            ) from exc

        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, KeyError, TypeError) as exc:
            raise ProviderError(
                f"openai: неожиданная форма ответа для модели {self.model.id!r}: {exc}"
            ) from exc

        if content is None:
            raise ProviderError(
                f"openai: пустой ответ модели {self.model.id!r} (content=None)"
            )
        return content
