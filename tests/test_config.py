"""Тесты загрузки настроек: config.yaml (типизация/дефолты) + секреты из .env."""

import textwrap

import pytest
from pydantic import ValidationError

from arena.config import AppConfig, ModelParams, Settings
from arena.config.settings import DEFAULT_CONFIG_PATH


def _write_config(tmp_path, body: str):
    path = tmp_path / "config.yaml"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def test_default_config_yaml_parses():
    """Дефолтный config.yaml репозитория валиден и содержит каталог моделей."""
    cfg = AppConfig.from_yaml(DEFAULT_CONFIG_PATH)
    assert cfg.arena.illegal_move_retries == 3
    assert cfg.arena.hints_per_player == 3
    assert cfg.arena.auto_claim_draws is True
    assert cfg.arena.strategy.enabled is True  # фича «стратегия» включена в дефолтном конфиге
    assert cfg.engine.path == "tools/bin/stockfish.exe"
    assert cfg.output.games_dir == "games"
    ids = [m.id for m in cfg.models]
    assert len(ids) == len(set(ids))
    assert {"gpt-4o", "claude-opus-4-8", "gemini-2.5-pro"} <= set(ids)
    assert {m.provider for m in cfg.models} <= set(cfg.providers)
    assert cfg.providers["openai"].api_key_env == "OPENAI_API_KEY"


def test_default_catalog_has_gpt_reasoning_variants():
    """Один и тот же GPT заведён тремя записями с разной глубиной раздумья."""
    cfg = AppConfig.from_yaml(DEFAULT_CONFIG_PATH)
    variants = [m for m in cfg.models if m.id.startswith("gpt-5.5-")]

    assert len(variants) == 3
    # разные записи каталога — одна модель в API
    assert {m.api_model for m in variants} == {"gpt-5.5"}
    assert {m.params.reasoning_effort for m in variants} == {"none", "medium", "high"}
    for model in variants:
        # серия отвергает temperature и требует max_completion_tokens
        assert model.params.reasoning is True
        assert model.params.temperature is None


def test_default_catalog_has_several_gemini_flash_versions():
    cfg = AppConfig.from_yaml(DEFAULT_CONFIG_PATH)
    flash = [m for m in cfg.models if m.provider == "gemini" and "flash" in m.id]

    assert len(flash) >= 3
    # у flash-моделей запас на «думающий» режим — иначе ответ приходит пустым
    assert all(m.params.max_tokens >= 8192 for m in flash)


# --- Фича «стратегия»: конфиг и мост в PlayerSettings ----------------------


def test_strategy_enabled_by_default_when_omitted(tmp_path):
    path = _write_config(tmp_path, "arena:\n  hints_per_player: 2\n")
    cfg = AppConfig.from_yaml(path)
    assert cfg.arena.strategy.enabled is True


def test_strategy_can_be_disabled_in_config(tmp_path):
    path = _write_config(
        tmp_path, "arena:\n  strategy:\n    enabled: false\n"
    )
    cfg = AppConfig.from_yaml(path)
    assert cfg.arena.strategy.enabled is False


def test_to_player_settings_maps_arena_fields(tmp_path):
    path = _write_config(
        tmp_path,
        """
        arena:
          illegal_move_retries: 5
          hints_per_player: 1
          include_legal_moves: true
          strategy:
            enabled: false
        """,
    )
    settings = AppConfig.from_yaml(path).arena.to_player_settings()
    assert settings.illegal_move_retries == 5
    assert settings.hints_per_player == 1
    assert settings.include_legal_moves is True
    assert settings.strategy_enabled is False


def test_to_player_settings_defaults_enable_strategy():
    from arena.config import ArenaConfig

    assert ArenaConfig().to_player_settings().strategy_enabled is True


def test_config_typed_fields(tmp_path):
    """Поля приводятся к типам моделей, params парсится в ModelParams."""
    path = _write_config(
        tmp_path,
        """
        arena:
          illegal_move_retries: 5
          hints_per_player: 2
          auto_claim_draws: false
        engine:
          enabled: false
          path: /opt/stockfish
          analysis_depth: 12
          hint_depth: 10
        providers:
          openai: { api_key_env: OPENAI_API_KEY }
        models:
          - id: gpt-4o
            provider: openai
            display_name: "GPT-4o"
            params: { temperature: 0.7, max_tokens: 256 }
        output:
          games_dir: out
        """,
    )
    cfg = AppConfig.from_yaml(path)
    assert cfg.arena.illegal_move_retries == 5
    assert cfg.arena.auto_claim_draws is False
    assert cfg.engine.enabled is False
    assert cfg.engine.path == "/opt/stockfish"
    model = cfg.models[0]
    assert isinstance(model.params, ModelParams)
    assert model.params.temperature == 0.7
    assert model.params.max_tokens == 256
    assert cfg.output.games_dir == "out"


def test_config_defaults_when_section_omitted(tmp_path):
    """Пропущенные секции и params заполняются дефолтами."""
    path = _write_config(
        tmp_path,
        """
        models:
          - id: gpt-4o
            provider: openai
            display_name: "GPT-4o"
        """,
    )
    cfg = AppConfig.from_yaml(path)
    assert cfg.arena.illegal_move_retries == 3  # дефолт ArenaConfig
    assert cfg.engine.enabled is True
    assert cfg.output.games_dir == "games"
    assert cfg.models[0].params.temperature == 0.2  # дефолт ModelParams


def test_config_rejects_non_mapping(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(ValueError):
        AppConfig.from_yaml(path)


def test_config_invalid_field_raises(tmp_path):
    path = _write_config(
        tmp_path,
        """
        arena:
          illegal_move_retries: "not-a-number"
        """,
    )
    with pytest.raises(Exception):
        AppConfig.from_yaml(path)


def test_secrets_loaded_from_env_file(tmp_path, monkeypatch):
    """Settings.load читает ключи из указанного .env по имени переменной."""
    # Изолируемся от реального окружения: переменные среды имеют приоритет над .env.
    for var in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    env = tmp_path / ".env"
    env.write_text(
        "OPENAI_API_KEY=sk-openai-123\nANTHROPIC_API_KEY=\n",
        encoding="utf-8",
    )
    settings = Settings.load(config_path=DEFAULT_CONFIG_PATH, env_file=env)
    # Заполненный ключ резолвится по имени переменной (как в api_key_env).
    assert settings.secrets.by_env_name("OPENAI_API_KEY") == "sk-openai-123"
    # Пустая строка трактуется как отсутствие ключа.
    assert settings.secrets.by_env_name("ANTHROPIC_API_KEY") is None
    # Отсутствующая переменная — тоже None.
    assert settings.secrets.by_env_name("GOOGLE_API_KEY") is None


def test_settings_load_without_env_file(monkeypatch):
    """Без .env секреты остаются пустыми, но загрузка не падает."""
    for var in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    settings = Settings.load(config_path=DEFAULT_CONFIG_PATH, env_file=None)
    assert isinstance(settings.config, AppConfig)
    assert settings.secrets.by_env_name("OPENAI_API_KEY") is None


# --- Краевые случаи загрузки/валидации (test(config): settings and catalog) ---


def test_from_yaml_missing_file_raises(tmp_path):
    """Несуществующий config.yaml → FileNotFoundError, а не молчаливый дефолт."""
    with pytest.raises(FileNotFoundError):
        AppConfig.from_yaml(tmp_path / "nope.yaml")


def test_empty_config_yields_all_defaults(tmp_path):
    """Пустой YAML (safe_load → None) даёт полностью дефолтный конфиг без падения."""
    path = tmp_path / "config.yaml"
    path.write_text("", encoding="utf-8")
    cfg = AppConfig.from_yaml(path)
    assert cfg.arena.illegal_move_retries == 3
    assert cfg.engine.path == "stockfish"
    assert cfg.providers == {}
    assert cfg.models == []
    assert cfg.output.games_dir == "games"


def test_unknown_top_level_section_is_ignored(tmp_path):
    """Незнакомая секция в config.yaml не ломает загрузку (extra игнорируется)."""
    path = _write_config(
        tmp_path,
        """
        future_feature: { whatever: 1 }
        output:
          games_dir: out
        """,
    )
    cfg = AppConfig.from_yaml(path)
    assert cfg.output.games_dir == "out"


def test_provider_without_api_key_env_raises(tmp_path):
    """Запись провайдера без обязательного api_key_env → ошибка валидации."""
    path = _write_config(
        tmp_path,
        """
        providers:
          openai: {}
        """,
    )
    with pytest.raises(ValidationError):
        AppConfig.from_yaml(path)


def test_model_missing_required_field_raises(tmp_path):
    """Модель без обязательного поля (display_name) → ошибка валидации."""
    path = _write_config(
        tmp_path,
        """
        models:
          - id: gpt-4o
            provider: openai
        """,
    )
    with pytest.raises(ValidationError):
        AppConfig.from_yaml(path)


def test_env_var_overrides_env_file(tmp_path, monkeypatch):
    """Переменная окружения имеет приоритет над значением из .env."""
    for var in ("ANTHROPIC_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
    env = tmp_path / ".env"
    env.write_text("OPENAI_API_KEY=sk-from-file\n", encoding="utf-8")
    settings = Settings.load(config_path=DEFAULT_CONFIG_PATH, env_file=env)
    assert settings.secrets.by_env_name("OPENAI_API_KEY") == "sk-from-env"


def test_by_env_name_unknown_returns_none(monkeypatch):
    """Неизвестное имя переменной → None, без исключения."""
    for var in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    settings = Settings.load(config_path=DEFAULT_CONFIG_PATH, env_file=None)
    assert settings.secrets.by_env_name("NOT_A_REAL_KEY") is None


def test_response_language_defaults_to_none_and_reaches_player_settings(tmp_path):
    """Язык ответов моделей: по умолчанию не навязываем, из конфига доезжает в партию."""
    from arena.config.settings import ArenaConfig

    assert ArenaConfig().response_language is None
    assert ArenaConfig().to_player_settings().response_language is None

    config = ArenaConfig(response_language="en")
    assert config.to_player_settings().response_language == "en"


def test_default_catalog_has_several_claude_models():
    """Клод заведён несколькими моделями — от Opus до быстрой Haiku."""
    cfg = AppConfig.from_yaml(DEFAULT_CONFIG_PATH)
    claude = [m for m in cfg.models if m.provider == "anthropic"]

    assert len(claude) >= 3
    # 5-я серия и Opus 4.8 отвергают temperature (400) — она должна быть снята
    for model in claude:
        if model.api_model.startswith(("claude-opus-5", "claude-sonnet-5", "claude-opus-4-8")):
            assert model.params.temperature is None, model.id
