"""LLM-провайдеры за единым интерфейсом (OpenAI / Anthropic / Gemini).

Точка входа слоя: базовый контракт ``LLMProvider``, фабрика по имени провайдера
(``create_provider``) и регистрация реализаций (``register_provider``).
Конкретные реализации (openai/anthropic/gemini) регистрируются в своих модулях.
"""

from arena.providers.base import (
    LLMProvider,
    ProviderError,
    create_provider,
    mask_secret,
    register_provider,
    registered_providers,
)
from arena.providers.retry import call_with_retry, is_transient_error

# Импорт реализаций регистрирует их в реестре (фабрика по имени провайдера).
from arena.providers.anthropic_provider import AnthropicProvider
from arena.providers.gemini_provider import GeminiProvider
from arena.providers.openai_provider import OpenAIProvider

__all__ = [
    "LLMProvider",
    "ProviderError",
    "AnthropicProvider",
    "GeminiProvider",
    "OpenAIProvider",
    "call_with_retry",
    "create_provider",
    "is_transient_error",
    "mask_secret",
    "register_provider",
    "registered_providers",
]
