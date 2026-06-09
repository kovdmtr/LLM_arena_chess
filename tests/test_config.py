"""Тесты загрузки настроек: config.yaml (типизация/дефолты) + секреты из .env."""

import textwrap

import pytest

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
    assert cfg.engine.path == "stockfish"
    assert cfg.output.games_dir == "games"
    assert {m.id for m in cfg.models} == {"gpt-4o", "claude-opus-4-8", "gemini-2.5-pro"}
    assert cfg.providers["openai"].api_key_env == "OPENAI_API_KEY"


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
