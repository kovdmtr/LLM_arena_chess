"""Реализация ``LLMProvider`` поверх официального SDK ``anthropic`` (Messages API).

Транслирует историю диалога (``MessageRecord``) в вызов ``messages.create`` и
возвращает сырой текст ответа модели (разбор в ``LLMResponse`` — задача
вышестоящего слоя, D-007). Модель берётся из ``ResolvedModel.id`` (в каталоге
``id`` совпадает с именем модели API, напр. ``claude-opus-4-8``).

Отличия от OpenAI Chat Completions, которые здесь учитываются:

- system-реплики не входят в ``messages``, а собираются в отдельный параметр
  ``system`` (Messages API принимает в ``messages`` только ``user``/``assistant``);
- статичная часть (системный промпт — правила + формат ответа, неизменные в течение
  партии) помечается ``cache_control: ephemeral`` → prompt caching префикса (D-017),
  что экономит токены на каждом ходе;
- ответ — список content-блоков; берётся текст всех ``text``-блоков.

Ключ живёт только внутри ``ResolvedModel`` (``api_key``, исключён из ``repr``,
D-003); при оборачивании ошибок SDK он маскируется через ``mask_secret``.
Регистрируется под именем провайдера ``anthropic`` (см. ``providers/__init__``).
"""

from __future__ import annotations

from collections.abc import Sequence

import anthropic

from arena.config import ResolvedModel
from arena.config.settings import ModelParams, RetryConfig
from arena.models import MessageRecord
from arena.providers.base import (
    LLMProvider,
    ProviderError,
    mask_secret,
    register_provider,
)


@register_provider("anthropic")
class AnthropicProvider(LLMProvider):
    """Провайдер Anthropic (Messages API) с prompt caching системного префикса."""

    def __init__(self, model: ResolvedModel, *, retry: RetryConfig | None = None) -> None:
        super().__init__(model, retry=retry)
        self._client: anthropic.Anthropic | None = None

    def _ensure_client(self) -> "anthropic.Anthropic":
        """Лениво создать и закэшировать клиент SDK с ключом из модели."""
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=self.model.api_key)
        return self._client

    def complete(
        self, messages: Sequence[MessageRecord], params: ModelParams
    ) -> str:
        client = self._ensure_client()

        # system-реплики — отдельно от диалога; статичный префикс кэшируем (D-017).
        system_text = "\n\n".join(
            m.content for m in messages if m.role == "system"
        )
        payload = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role != "system"
        ]

        kwargs: dict = {
            "model": self.model.id,
            "messages": payload,
            "max_tokens": params.max_tokens,
        }
        if params.temperature is not None:  # None → не передаём (D: устарел у некоторых моделей)
            kwargs["temperature"] = params.temperature
        if system_text:
            kwargs["system"] = [
                {
                    "type": "text",
                    "text": system_text,
                    "cache_control": {"type": "ephemeral"},
                }
            ]

        try:
            response = self._call(lambda: client.messages.create(**kwargs))
        except Exception as exc:  # SDK/транспорт — единая ошибка слоя
            raise ProviderError(
                mask_secret(
                    f"anthropic: сбой запроса к модели {self.model.id!r}: {exc}",
                    self.model.api_key,
                )
            ) from exc

        try:
            blocks = response.content
            text = "".join(
                block.text
                for block in blocks
                if getattr(block, "type", None) == "text"
            )
        except (AttributeError, TypeError) as exc:
            raise ProviderError(
                f"anthropic: неожиданная форма ответа для модели "
                f"{self.model.id!r}: {exc}"
            ) from exc

        if not text:
            raise ProviderError(
                f"anthropic: пустой ответ модели {self.model.id!r} "
                f"(нет текстовых блоков)"
            )
        return text
