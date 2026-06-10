"""Тесты консольного интерфейса ``arena`` (пост-бэклог).

Фейковые игроки без сети (швы ``player_factory``/``engine_factory``): партия играется
«дурацким матом» (0-1), турнир — чемпион vs сдающийся. Проверяем команды ``models``/
``play``/``tournament``, коды возврата, сохранение артефактов и обработку ошибок
конфигурации, плюс точку входа ``main`` на временном ``config.yaml``.
"""

from __future__ import annotations

import textwrap
from datetime import datetime, timezone

from arena.cli import (
    _configure_output_encoding,
    build_parser,
    cmd_models,
    cmd_play,
    cmd_tournament,
    main,
)
from arena.config import AppConfig, Secrets, Settings
from arena.models import LLMResponse, PlayerInfo
from arena.storage import GAME_JSON_NAME

CLOCK = lambda: datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)  # noqa: E731

# Дурацкий мат: 1. f3 e5 2. g4 Qh4# → 0-1.
_WHITE_MOVES = {"f3", "g4"}
_BLACK_MOVES = {"e5", "Qh4#"}


class _ScriptedPlayer:
    def __init__(self, info: PlayerInfo, moves):
        self._info = info
        self._moves = list(moves)

    @property
    def info(self) -> PlayerInfo:
        return self._info

    def respond(self, messages) -> LLMResponse:
        return LLMResponse(move=self._moves.pop(0), reasoning="scripted")


class _ResignPlayer:
    def __init__(self, info: PlayerInfo):
        self._info = info

    @property
    def info(self) -> PlayerInfo:
        return self._info

    def respond(self, messages) -> LLMResponse:
        return LLMResponse(resign=True, reasoning="gg")


def _settings(games_root, *, key="sk-test", models=None) -> Settings:
    config = AppConfig.model_validate(
        {
            "providers": {"openai": {"api_key_env": "OPENAI_API_KEY"}},
            "models": models
            or [
                {"id": "w-model", "provider": "openai", "display_name": "White"},
                {"id": "b-model", "provider": "openai", "display_name": "Black"},
            ],
            "engine": {"enabled": False},
            "output": {"games_dir": str(games_root)},
        }
    )
    secrets = Secrets(_env_file=None, openai_api_key=key)  # type: ignore[call-arg]
    return Settings(config=config, secrets=secrets)


def _play_factory(side, resolved):
    info = PlayerInfo(
        model_id=resolved.id, provider=resolved.provider, display_name=resolved.display_name
    )
    moves = ["f3", "g4"] if side == "white" else ["e5", "Qh4#"]
    return _ScriptedPlayer(info, moves)


def _parse(argv):
    return build_parser().parse_args(argv)


# --- models ---------------------------------------------------------------


def test_models_lists_with_key_flags(tmp_path):
    settings = _settings(tmp_path, key="sk-test")
    lines: list[str] = []
    rc = cmd_models(settings, out=lines.append)
    assert rc == 0
    text = "\n".join(lines)
    assert "w-model" in text and "b-model" in text
    assert "✓ ключ" in text  # ключ задан


def test_models_marks_missing_key(tmp_path):
    settings = _settings(tmp_path, key=None)
    lines: list[str] = []
    cmd_models(settings, out=lines.append)
    assert "✗ нет ключа" in "\n".join(lines)


# --- play -----------------------------------------------------------------


def test_play_runs_game_and_writes_artifacts(tmp_path):
    settings = _settings(tmp_path)
    args = _parse(["play", "w-model", "b-model", "--id", "g-cli"])
    lines: list[str] = []
    rc = cmd_play(
        args,
        settings=settings,
        player_factory=_play_factory,
        engine_factory=lambda: None,
        clock=CLOCK,
        out=lines.append,
    )
    assert rc == 0
    text = "\n".join(lines)
    assert "0-1" in text  # чёрные ставят мат
    assert (tmp_path / "g-cli" / GAME_JSON_NAME).is_file()
    assert (tmp_path / "g-cli" / "game.pgn").is_file()
    assert (tmp_path / "g-cli" / "report.html").is_file()


def test_play_no_persist_skips_disk(tmp_path):
    settings = _settings(tmp_path)
    args = _parse(["play", "w-model", "b-model", "--id", "g-cli", "--no-persist"])
    lines: list[str] = []
    rc = cmd_play(
        args,
        settings=settings,
        player_factory=_play_factory,
        engine_factory=lambda: None,
        clock=CLOCK,
        out=lines.append,
    )
    assert rc == 0
    assert not (tmp_path / "g-cli").exists()


def test_play_unknown_model_returns_error(tmp_path):
    settings = _settings(tmp_path)
    args = _parse(["play", "nope", "b-model"])
    lines: list[str] = []
    rc = cmd_play(args, settings=settings, engine_factory=lambda: None, out=lines.append)
    assert rc == 2
    assert "Ошибка конфигурации" in "\n".join(lines)


def test_play_missing_key_returns_error(tmp_path):
    settings = _settings(tmp_path, key=None)
    args = _parse(["play", "w-model", "b-model"])
    lines: list[str] = []
    rc = cmd_play(args, settings=settings, engine_factory=lambda: None, out=lines.append)
    assert rc == 2
    assert "Ошибка конфигурации" in "\n".join(lines)


# --- tournament -----------------------------------------------------------


def _tour_factory(side, info: PlayerInfo):
    return (
        _ScriptedPlayer(info, ["e4"])
        if info.model_id == "champ"
        else _ResignPlayer(info)
    )


def _tour_settings(games_root):
    return _settings(
        games_root,
        models=[
            {"id": "champ", "provider": "openai", "display_name": "Champion"},
            {"id": "weak", "provider": "openai", "display_name": "Weakling"},
        ],
    )


def test_tournament_runs_and_prints_standings(tmp_path):
    settings = _tour_settings(tmp_path)
    args = _parse(["tournament", "champ", "weak", "--double", "--id", "t1"])
    lines: list[str] = []
    rc = cmd_tournament(
        args,
        settings=settings,
        player_factory=_tour_factory,
        engine_factory=lambda: None,
        clock=CLOCK,
        out=lines.append,
    )
    assert rc == 0
    text = "\n".join(lines)
    assert "Champion" in text and "Weakling" in text
    # Итоговые артефакты турнира записаны.
    assert (tmp_path / "tournaments" / "t1" / "standings.html").is_file()
    assert (tmp_path / "tournaments" / "t1" / "tournament.pgn").is_file()
    assert (tmp_path / "tournaments" / "t1" / "tournament.json").is_file()


def test_tournament_needs_two_models(tmp_path):
    settings = _tour_settings(tmp_path)
    args = _parse(["tournament", "champ"])
    lines: list[str] = []
    rc = cmd_tournament(args, settings=settings, out=lines.append)
    assert rc == 2
    assert "минимум две" in "\n".join(lines)


def test_tournament_unknown_model_returns_error(tmp_path):
    settings = _tour_settings(tmp_path)
    args = _parse(["tournament", "champ", "ghost"])
    lines: list[str] = []
    rc = cmd_tournament(args, settings=settings, engine_factory=lambda: None, out=lines.append)
    assert rc == 2
    assert "Ошибка конфигурации" in "\n".join(lines)


# --- main / точка входа ---------------------------------------------------


def test_configure_output_encoding_is_safe():
    # Не должно падать (и быть идемпотентным) — защита печати кириллицы на Windows.
    _configure_output_encoding()
    _configure_output_encoding()


def test_main_no_command_prints_help_returns_1(capsys):
    rc = main([])
    assert rc == 1
    assert "usage" in capsys.readouterr().out.lower()


def test_main_models_loads_config_file(tmp_path, capsys):
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        textwrap.dedent(
            """
            providers:
              openai:
                api_key_env: OPENAI_API_KEY
            models:
              - id: m1
                provider: openai
                display_name: Model One
            output:
              games_dir: games
            """
        ),
        encoding="utf-8",
    )
    env = tmp_path / ".env"
    env.write_text("OPENAI_API_KEY=sk-test\n", encoding="utf-8")

    rc = main(["--config", str(cfg), "--env", str(env), "models"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "m1" in out and "✓ ключ" in out
