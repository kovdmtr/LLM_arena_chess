"""LLM-провайдеры за единым интерфейсом (OpenAI / Anthropic / Gemini).

Точка входа слоя: базовый контракт ``LLMProvider``, фабрика по имени провайдера
(``create_provider``) и регистрация реализаций (``register_provider``).
Конкретные реализации (openai/anthropic/gemini) регистрируются в своих модулях.
"""

from arena.providers.base import (
    LLMProvider,
    ProviderError,
    create_provider,
    register_provider,
    registered_providers,
)

__all__ = [
    "LLMProvider",
    "ProviderError",
    "create_provider",
    "register_provider",
    "registered_providers",
]
