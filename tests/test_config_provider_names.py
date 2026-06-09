"""Согласованность имён провайдеров в config.yaml с реестром реализаций.

Регрессия на баг Phase 6: в `config.yaml` провайдер Gemini назывался `google`, а
реализация зарегистрирована как `gemini` (D-018) → выбор Gemini падал при старте
партии (`create_provider('google')` → `ProviderError`). Эти тесты ловят любое такое
расхождение в **поставляемом** `config.yaml`: каждое имя провайдера (в секции
`providers` и у каждой модели) должно быть зарегистрировано в коде.
"""

from __future__ import annotations

from arena.config import AppConfig
from arena.providers import registered_providers  # импорт регистрирует все реализации


def test_shipped_config_models_use_registered_providers():
    config = AppConfig.from_yaml()  # дефолтный config.yaml репозитория
    registered = set(registered_providers())
    for model in config.models:
        assert model.provider in registered, (
            f"модель {model.id!r}: провайдер {model.provider!r} не зарегистрирован "
            f"(есть: {sorted(registered)})"
        )


def test_shipped_config_provider_section_names_are_registered():
    config = AppConfig.from_yaml()
    registered = set(registered_providers())
    for name in config.providers:
        assert name in registered, (
            f"провайдер {name!r} из секции providers не зарегистрирован "
            f"(есть: {sorted(registered)})"
        )
