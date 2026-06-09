"""Каталог моделей: lookup по ``id`` и резолв API-ключа провайдера.

Каталог строится из несекретного ``AppConfig`` (``providers`` + ``models``) и
``Secrets`` (значения ключей из ``.env``/окружения). Он умеет:

- отдавать запись модели по ``id`` (``get``);
- сообщать имя переменной с ключом для модели (``api_key_env_for``);
- проверять наличие ключа (``has_key``);
- резолвить модель в ``ResolvedModel`` с подставленным ключом (``resolve``),
  с fail-fast при отсутствии ключа или неизвестной модели/провайдере.

Сам ключ никогда не логируется и не попадает в ``repr`` (см. ``ResolvedModel``).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from arena.config.settings import (
    AppConfig,
    ModelConfig,
    ModelParams,
    Secrets,
    Settings,
)


class ConfigError(ValueError):
    """Ошибка конфигурации (неизвестная модель/провайдер, отсутствие ключа)."""


class ResolvedModel(BaseModel):
    """Модель с резолвленным API-ключом, готовая к передаче провайдеру.

    ``api_key`` исключён из ``repr``/сериализации по умолчанию, чтобы секрет
    не утёк в логи или артефакты партии.
    """

    id: str
    provider: str
    display_name: str
    params: ModelParams = Field(default_factory=ModelParams)
    api_key_env: str
    api_key: str = Field(repr=False, exclude=True)


class ModelCatalog:
    """Каталог выбираемых моделей поверх ``AppConfig`` + ``Secrets``."""

    def __init__(self, config: AppConfig, secrets: Secrets) -> None:
        self._secrets = secrets
        self._providers = config.providers
        # Сохраняем порядок из config.yaml; дубликаты id запрещены.
        self._models: dict[str, ModelConfig] = {}
        for model in config.models:
            if model.id in self._models:
                raise ConfigError(f"дублирующийся id модели в каталоге: {model.id!r}")
            self._models[model.id] = model

    @classmethod
    def from_settings(cls, settings: Settings) -> "ModelCatalog":
        """Построить каталог из объединённых ``Settings``."""
        return cls(settings.config, settings.secrets)

    @property
    def models(self) -> list[ModelConfig]:
        """Записи каталога в порядке объявления в ``config.yaml``."""
        return list(self._models.values())

    def ids(self) -> list[str]:
        """Идентификаторы доступных моделей."""
        return list(self._models)

    def get(self, model_id: str) -> ModelConfig:
        """Запись модели по ``id``; ``ConfigError`` при отсутствии."""
        try:
            return self._models[model_id]
        except KeyError:
            known = ", ".join(self._models) or "<пусто>"
            raise ConfigError(
                f"неизвестная модель {model_id!r}; доступны: {known}"
            ) from None

    def api_key_env_for(self, model_id: str) -> str:
        """Имя переменной окружения с ключом для провайдера модели."""
        model = self.get(model_id)
        provider = self._providers.get(model.provider)
        if provider is None:
            known = ", ".join(self._providers) or "<пусто>"
            raise ConfigError(
                f"модель {model_id!r} ссылается на неизвестного провайдера "
                f"{model.provider!r}; объявлены: {known}"
            )
        return provider.api_key_env

    def has_key(self, model_id: str) -> bool:
        """Есть ли непустой ключ для модели."""
        return self._secrets.by_env_name(self.api_key_env_for(model_id)) is not None

    def resolve(self, model_id: str) -> ResolvedModel:
        """Резолвнуть модель в ``ResolvedModel`` с ключом; fail-fast без ключа."""
        model = self.get(model_id)
        api_key_env = self.api_key_env_for(model_id)
        api_key = self._secrets.by_env_name(api_key_env)
        if api_key is None:
            raise ConfigError(
                f"нет API-ключа для модели {model_id!r} "
                f"(провайдер {model.provider!r}): задайте {api_key_env} в .env"
            )
        return ResolvedModel(
            id=model.id,
            provider=model.provider,
            display_name=model.display_name,
            params=model.params,
            api_key_env=api_key_env,
            api_key=api_key,
        )
