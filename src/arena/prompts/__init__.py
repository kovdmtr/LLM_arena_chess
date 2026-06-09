"""Сборка системного промпта и контекста хода для моделей."""

from arena.prompts.system import (
    RESPONSE_KEYS,
    build_system_prompt,
    system_message,
)

__all__ = ["RESPONSE_KEYS", "build_system_prompt", "system_message"]
