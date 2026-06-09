"""Тесты каталога моделей: lookup по id, резолв ключа, fail-fast."""

import pytest

from arena.config import (
    AppConfig,
    ConfigError,
    ModelCatalog,
    ModelConfig,
    ModelParams,
    ProviderConfig,
    Secrets,
)
from arena.config.settings import DEFAULT_CONFIG_PATH


def _config() -> AppConfig:
    """Минимальный конфиг с двумя провайдерами и двумя моделями."""
    return AppConfig(
        providers={
            "openai": ProviderConfig(api_key_env="OPENAI_API_KEY"),
            "anthropic": ProviderConfig(api_key_env="ANTHROPIC_API_KEY"),
        },
        models=[
            ModelConfig(
                id="gpt-4o",
                provider="openai",
                display_name="GPT-4o",
                params=ModelParams(temperature=0.5, max_tokens=512),
            ),
            ModelConfig(
                id="claude",
                provider="anthropic",
                display_name="Claude",
            ),
        ],
    )


def _secrets(**kwargs) -> Secrets:
    """Secrets без чтения реального .env."""
    return Secrets(_env_file=None, **kwargs)


def test_catalog_lists_models_in_order():
    catalog = ModelCatalog(_config(), _secrets())
    assert catalog.ids() == ["gpt-4o", "claude"]
    assert [m.display_name for m in catalog.models] == ["GPT-4o", "Claude"]


def test_get_returns_model_and_raises_on_unknown():
    catalog = ModelCatalog(_config(), _secrets())
    assert catalog.get("gpt-4o").provider == "openai"
    with pytest.raises(ConfigError, match="неизвестная модель"):
        catalog.get("does-not-exist")


def test_api_key_env_resolved_from_provider():
    catalog = ModelCatalog(_config(), _secrets())
    assert catalog.api_key_env_for("gpt-4o") == "OPENAI_API_KEY"
    assert catalog.api_key_env_for("claude") == "ANTHROPIC_API_KEY"


def test_has_key_reflects_secrets():
    secrets = _secrets(openai_api_key="sk-123", anthropic_api_key="")
    catalog = ModelCatalog(_config(), secrets)
    assert catalog.has_key("gpt-4o") is True
    # Пустая строка трактуется как отсутствие ключа.
    assert catalog.has_key("claude") is False


def test_resolve_returns_model_with_key():
    secrets = _secrets(openai_api_key="sk-123")
    catalog = ModelCatalog(_config(), secrets)
    resolved = catalog.resolve("gpt-4o")
    assert resolved.id == "gpt-4o"
    assert resolved.api_key == "sk-123"
    assert resolved.api_key_env == "OPENAI_API_KEY"
    assert resolved.params.max_tokens == 512


def test_resolve_fails_fast_without_key():
    catalog = ModelCatalog(_config(), _secrets())
    with pytest.raises(ConfigError, match="нет API-ключа"):
        catalog.resolve("gpt-4o")


def test_resolved_model_hides_key_from_repr_and_dump():
    secrets = _secrets(openai_api_key="sk-secret-xyz")
    catalog = ModelCatalog(_config(), secrets)
    resolved = catalog.resolve("gpt-4o")
    # Ключ не должен утечь в repr или сериализацию.
    assert "sk-secret-xyz" not in repr(resolved)
    assert "api_key" not in resolved.model_dump()


def test_unknown_provider_raises():
    config = AppConfig(
        providers={"openai": ProviderConfig(api_key_env="OPENAI_API_KEY")},
        models=[ModelConfig(id="m", provider="ghost", display_name="M")],
    )
    catalog = ModelCatalog(config, _secrets())
    with pytest.raises(ConfigError, match="неизвестного провайдера"):
        catalog.api_key_env_for("m")


def test_duplicate_model_id_rejected():
    config = AppConfig(
        providers={"openai": ProviderConfig(api_key_env="OPENAI_API_KEY")},
        models=[
            ModelConfig(id="dup", provider="openai", display_name="A"),
            ModelConfig(id="dup", provider="openai", display_name="B"),
        ],
    )
    with pytest.raises(ConfigError, match="дублирующийся id"):
        ModelCatalog(config, _secrets())


def test_resolve_unknown_model_raises():
    """resolve неизвестной модели падает через get → ConfigError."""
    catalog = ModelCatalog(_config(), _secrets())
    with pytest.raises(ConfigError, match="неизвестная модель"):
        catalog.resolve("does-not-exist")


def test_api_key_env_for_unknown_model_raises():
    """api_key_env_for неизвестной модели → ConfigError."""
    catalog = ModelCatalog(_config(), _secrets())
    with pytest.raises(ConfigError, match="неизвестная модель"):
        catalog.api_key_env_for("does-not-exist")


def test_get_on_empty_catalog_reports_empty():
    """Сообщение об ошибке для пустого каталога перечисляет «<пусто>»."""
    catalog = ModelCatalog(AppConfig(), _secrets())
    assert catalog.ids() == []
    with pytest.raises(ConfigError, match="<пусто>"):
        catalog.get("anything")


def test_key_resolved_from_real_environment(monkeypatch):
    """Ключ может прийти из переменной окружения, а не только из .env."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    secrets = Secrets(_env_file=None)
    catalog = ModelCatalog(_config(), secrets)
    assert catalog.has_key("gpt-4o") is True
    assert catalog.resolve("gpt-4o").api_key == "sk-env"


def test_from_settings_uses_default_catalog(monkeypatch):
    """Каталог из дефолтного config.yaml содержит все объявленные модели."""
    from arena.config import Settings

    for var in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    settings = Settings.load(config_path=DEFAULT_CONFIG_PATH, env_file=None)
    catalog = ModelCatalog.from_settings(settings)
    assert set(catalog.ids()) == {"gpt-4o", "claude-opus-4-8", "gemini-2.5-pro"}
    # Без ключей резолв падает fail-fast.
    with pytest.raises(ConfigError):
        catalog.resolve("gpt-4o")
