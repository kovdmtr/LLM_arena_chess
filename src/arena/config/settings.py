"""Загрузка настроек: несекретное из ``config.yaml`` + секреты из ``.env``.

``config.yaml`` парсится в типизированные pydantic-модели (``AppConfig``).
Секреты (API-ключи) читаются через ``pydantic-settings`` из окружения/``.env``
и никогда не хранятся в ``config.yaml``. Резолв ключа по ``api_key_env`` и
fail-fast при отсутствии — задача следующего шага (каталог моделей).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Корень репозитория: .../src/arena/config/settings.py -> подняться на 4 уровня.
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = _REPO_ROOT / "config.yaml"
DEFAULT_ENV_FILE = _REPO_ROOT / ".env"


class StrategyConfig(BaseModel):
    """Фича «стратегия»: модель ведёт приватный rolling-план между ходами.

    При ``enabled`` системный промпт описывает поля ``strategy``/``plan_status``, а в
    контекст хода инъектируется план предыдущего хода стороны — партия играется как
    связная игра, а не оценка позиции с нуля. По умолчанию включено.
    """

    enabled: bool = True


class ArenaConfig(BaseModel):
    """Параметры игрового цикла."""

    illegal_move_retries: int = 3
    hints_per_player: int = 3
    auto_claim_draws: bool = True
    include_legal_moves: bool = False  # класть ли список легальных ходов в промпт (D-021)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)

    def to_player_settings(self) -> "PlayerSettings":  # noqa: F821 — строковая аннотация
        """Спроецировать конфиг арены в ``PlayerSettings`` (срез, хранимый в партии).

        Мост ``config.yaml`` → ``GameRecord.settings``: переносит лимиты и флаги, под
        которыми играется партия (попытки, подсказки, список легальных ходов D-021,
        фича «стратегия»). ``auto_claim_draws`` — свойство доски, не игрока, поэтому
        здесь не переносится. ``PlayerSettings`` импортируется лениво (``arena.models``
        не зависит от ``config`` — не замыкаем).
        """
        from arena.models import PlayerSettings

        return PlayerSettings(
            illegal_move_retries=self.illegal_move_retries,
            hints_per_player=self.hints_per_player,
            include_legal_moves=self.include_legal_moves,
            strategy_enabled=self.strategy.enabled,
        )


class EngineConfig(BaseModel):
    """Настройки Stockfish (опциональная зависимость)."""

    enabled: bool = True
    path: str = "stockfish"
    analysis_depth: int = 18
    hint_depth: int = 18


class AnalysisConfig(BaseModel):
    """★ Пороги классификации ходов по centipawn loss (D-009).

    Универсально «правильных» значений нет, поэтому они вынесены в конфиг. Пороги
    cpl должны возрастать (``inaccuracy_cp`` ≤ ``mistake_cp`` ≤ ``blunder_cp``);
    согласованность проверяет ``analysis.ClassificationThresholds``.
    """

    enabled: bool = True
    inaccuracy_cp: int = 50
    mistake_cp: int = 120
    blunder_cp: int = 300
    brilliant_max_cpl: int = 10
    brilliant_min_eval_cp: int = 100


class RetryConfig(BaseModel):
    """Политика повторов вызова провайдера при временных сбоях (Phase 7).

    Применяется к транзиентным ошибкам SDK (rate-limit/таймаут/сетевой сбой/5xx) —
    см. ``providers.retry``. Постоянные ошибки (неверный ключ, 4xx кроме 429) не
    повторяются. ``attempts`` — общее число попыток (1 = без повторов). Задержка
    растёт экспоненциально: ``base_delay * multiplier**(n-1)``, но не выше
    ``max_delay``; ``jitter`` (доля 0..1) размывает её, чтобы избежать
    синхронных повторов.
    """

    attempts: int = 3
    base_delay: float = 0.5
    max_delay: float = 8.0
    multiplier: float = 2.0
    jitter: float = 0.1

    @model_validator(mode="after")
    def _check(self) -> "RetryConfig":
        if self.attempts < 1:
            raise ValueError("retry.attempts должно быть ≥ 1")
        if self.base_delay < 0 or self.max_delay < 0:
            raise ValueError("retry.base_delay/max_delay должны быть ≥ 0")
        if self.multiplier < 1:
            raise ValueError("retry.multiplier должно быть ≥ 1")
        if not 0 <= self.jitter <= 1:
            raise ValueError("retry.jitter должно быть в диапазоне [0, 1]")
        return self


class ProviderConfig(BaseModel):
    """Несекретное описание провайдера: имя переменной окружения с ключом."""

    api_key_env: str


class ModelParams(BaseModel):
    """Параметры генерации для конкретной модели.

    ``temperature`` можно отключить значением ``null`` в ``config.yaml`` — тогда
    провайдер не передаёт его в API. Это нужно для моделей, у которых параметр
    запрещён/устарел (например, ``claude-opus-4-8`` отвечает 400 на любой
    ``temperature``). По умолчанию остаётся ``0.2``.
    """

    temperature: float | None = 0.2
    max_tokens: int = 1024


class ModelConfig(BaseModel):
    """Запись каталога моделей."""

    id: str
    provider: str
    display_name: str
    params: ModelParams = Field(default_factory=ModelParams)


class OutputConfig(BaseModel):
    """Куда складывать артефакты партий."""

    games_dir: str = "games"


class AppConfig(BaseModel):
    """Полное содержимое ``config.yaml`` (несекретное)."""

    arena: ArenaConfig = Field(default_factory=ArenaConfig)
    engine: EngineConfig = Field(default_factory=EngineConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    models: list[ModelConfig] = Field(default_factory=list)
    output: OutputConfig = Field(default_factory=OutputConfig)

    @classmethod
    def from_yaml(cls, path: str | Path = DEFAULT_CONFIG_PATH) -> "AppConfig":
        """Прочитать и провалидировать ``config.yaml``."""
        path = Path(path)
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"{path}: ожидался YAML-объект, получено {type(raw).__name__}")
        return cls.model_validate(raw)


class Secrets(BaseSettings):
    """API-ключи провайдеров из окружения/``.env`` (значения, не имена)."""

    model_config = SettingsConfigDict(
        env_file=str(DEFAULT_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None

    def by_env_name(self, env_name: str) -> str | None:
        """Вернуть ключ по имени переменной окружения (как в ``api_key_env``).

        Пустая строка трактуется как отсутствие ключа (заготовка в ``.env.example``).
        """
        value = getattr(self, env_name.lower(), None)
        return value or None


class Settings(BaseModel):
    """Объединённые настройки приложения: конфиг + секреты."""

    model_config = {"arbitrary_types_allowed": True}

    config: AppConfig
    secrets: Secrets

    @classmethod
    def load(
        cls,
        config_path: str | Path = DEFAULT_CONFIG_PATH,
        env_file: str | Path | None = DEFAULT_ENV_FILE,
    ) -> "Settings":
        """Загрузить ``config.yaml`` и секреты из окружения/``.env``."""
        app_config = AppConfig.from_yaml(config_path)
        if env_file is None:
            secrets = Secrets(_env_file=None)  # type: ignore[call-arg]
        else:
            secrets = Secrets(_env_file=str(env_file))  # type: ignore[call-arg]
        return cls(config=app_config, secrets=secrets)
