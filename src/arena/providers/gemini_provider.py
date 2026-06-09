"""Реализация ``LLMProvider`` поверх официального SDK ``google-genai`` (Gemini).

Транслирует историю диалога (``MessageRecord``) в вызов
``client.models.generate_content`` и возвращает сырой текст ответа модели (разбор
в ``LLMResponse`` — задача вышестоящего слоя, D-007). Модель берётся из
``ResolvedModel.id`` (в каталоге ``id`` совпадает с именем модели API,
напр. ``gemini-2.5-pro``).

Отличия Gemini API, которые здесь учитываются (D-018):

- роль ассистента в ``contents`` называется ``model``, а не ``assistant``;
  ``user`` остаётся ``user``. Каждое сообщение — ``{"role", "parts": [{"text"}]}``;
- system-реплики не входят в ``contents``, а собираются (через ``\n\n``) в
  ``system_instruction`` внутри ``GenerateContentConfig`` (как и у Anthropic,
  system — это отдельный top-level параметр, а не сообщение);
- параметры генерации (``temperature``/``max_output_tokens``) также передаются
  через ``GenerateContentConfig``;
- ответ — ``response.text`` (конкатенация текстовых частей); пусто → ошибка.

Ключ живёт только внутри ``ResolvedModel`` (``api_key``, исключён из ``repr``,
D-003); при оборачивании ошибок SDK он маскируется через ``mask_secret``.
Регистрируется под именем провайдера ``gemini`` (см. ``providers/__init__``).
"""

from __future__ import annotations

from collections.abc import Sequence

from google import genai
from google.genai import types

from arena.config import ResolvedModel
from arena.config.settings import ModelParams
from arena.models import MessageRecord
from arena.providers.base import (
    LLMProvider,
    ProviderError,
    mask_secret,
    register_provider,
)

# Роли диалога → роли Gemini: ассистент в Gemini называется "model".
_ROLE_MAP = {"user": "user", "assistant": "model"}


@register_provider("gemini")
class GeminiProvider(LLMProvider):
    """Провайдер Google Gemini (``generate_content``) с system_instruction."""

    def __init__(self, model: ResolvedModel) -> None:
        super().__init__(model)
        self._client: "genai.Client | None" = None

    def _ensure_client(self) -> "genai.Client":
        """Лениво создать и закэшировать клиент SDK с ключом из модели."""
        if self._client is None:
            self._client = genai.Client(api_key=self.model.api_key)
        return self._client

    def complete(
        self, messages: Sequence[MessageRecord], params: ModelParams
    ) -> str:
        client = self._ensure_client()

        # system-реплики — отдельно от диалога (в system_instruction).
        system_text = "\n\n".join(
            m.content for m in messages if m.role == "system"
        )
        contents = [
            {"role": _ROLE_MAP[m.role], "parts": [{"text": m.content}]}
            for m in messages
            if m.role != "system"
        ]

        config = types.GenerateContentConfig(
            temperature=params.temperature,
            max_output_tokens=params.max_tokens,
            system_instruction=system_text or None,
        )

        try:
            response = client.models.generate_content(
                model=self.model.id,
                contents=contents,
                config=config,
            )
        except Exception as exc:  # SDK/транспорт — единая ошибка слоя
            raise ProviderError(
                mask_secret(
                    f"gemini: сбой запроса к модели {self.model.id!r}: {exc}",
                    self.model.api_key,
                )
            ) from exc

        try:
            text = response.text
        except (AttributeError, TypeError, ValueError) as exc:
            raise ProviderError(
                f"gemini: неожиданная форма ответа для модели "
                f"{self.model.id!r}: {exc}"
            ) from exc

        if not text:
            raise ProviderError(
                f"gemini: пустой ответ модели {self.model.id!r} "
                f"(нет текста)"
            )
        return text
