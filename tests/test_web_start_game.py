"""Тесты запуска партии из веб-интерфейса (★, Phase 6, D-002).

``GameManager`` подменяется фабрикой фейковых (скриптованных) игроков — без сети и
без реальных LLM-вызовов: два игрока доигрывают «дурацкий мат» (Fool's mate). На этом
проверяется и сам менеджер (фоновый прогон + сохранение артефактов, накопление
событий, статус ошибки), и эндпоинт ``POST /games`` (резолв моделей, редирект,
перерисовка формы с ошибкой при отсутствии ключа/неизвестной модели).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from arena.config import AppConfig, ModelCatalog, Secrets, Settings
from arena.models import LLMResponse, PlayerInfo
from arena.web import GameManager, create_app
from arena.web.games import STATUS_ERROR, STATUS_FINISHED

# Fool's mate: 1. f3 e5 2. g4 Qh4# — чёрные ставят мат (0-1).
_WHITE_MOVES = ["f3", "g4"]
_BLACK_MOVES = ["e5", "Qh4#"]

_PROVIDERS = {"openai": {"api_key_env": "OPENAI_API_KEY"}}
_MODELS = [
    {"id": "w-model", "provider": "openai", "display_name": "White Model"},
    {"id": "b-model", "provider": "openai", "display_name": "Black Model"},
]
CLOCK = lambda: datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc)  # noqa: E731


class _ScriptedPlayer:
    """Фейковый игрок: возвращает заранее заданные ходы по очереди."""

    def __init__(self, info: PlayerInfo, moves):
        self._info = info
        self._moves = list(moves)

    @property
    def info(self) -> PlayerInfo:
        return self._info

    def respond(self, messages) -> LLMResponse:
        move = self._moves.pop(0)
        return LLMResponse(reasoning=f"playing {move}", move=move)


class _BoomPlayer:
    """Игрок, падающий при ходе — для проверки статуса ошибки сессии."""

    def __init__(self, info: PlayerInfo):
        self._info = info

    @property
    def info(self) -> PlayerInfo:
        return self._info

    def respond(self, messages) -> LLMResponse:
        raise RuntimeError("provider exploded")


def _settings(*, key: str | None = "sk-test") -> Settings:
    config = AppConfig.model_validate({"providers": _PROVIDERS, "models": _MODELS})
    secrets = Secrets(_env_file=None, openai_api_key=key)
    return Settings(config=config, secrets=secrets)


def _info(side: str) -> PlayerInfo:
    return PlayerInfo(model_id=f"{side}-model", provider="openai", display_name=side)


def _scripted_factory():
    players = {
        "white": _ScriptedPlayer(_info("white"), _WHITE_MOVES),
        "black": _ScriptedPlayer(_info("black"), _BLACK_MOVES),
    }
    return lambda side, resolved: players[side]


def _manager(tmp_path, *, factory=None, persist=True) -> GameManager:
    return GameManager(
        player_factory=factory or _scripted_factory(),
        games_root=str(tmp_path),
        persist=persist,
        clock=CLOCK,
    )


def _resolved(settings: Settings):
    catalog = ModelCatalog.from_settings(settings)
    return {"white": catalog.resolve("w-model"), "black": catalog.resolve("b-model")}


# --- уровень менеджера --------------------------------------------------------

def test_manager_runs_game_to_checkmate_and_persists(tmp_path):
    manager = _manager(tmp_path)
    session = manager.start(_resolved(_settings()))

    assert session.join(timeout=5)
    assert session.status == STATUS_FINISHED
    assert session.result == "0-1"
    assert session.termination == "checkmate"
    # артефакты сохранены рядом (game.json + pgn + html).
    game_dir = tmp_path / session.id
    assert (game_dir / "game.json").is_file()
    assert (game_dir / "game.pgn").is_file()
    assert (game_dir / "report.html").is_file()


def test_manager_records_events_with_game_over_last(tmp_path):
    manager = _manager(tmp_path)
    session = manager.start(_resolved(_settings()))
    assert session.join(timeout=5)

    types = [event["type"] for event in session.events]
    assert types[0] == "game_start"
    assert types[-1] == "game_over"
    assert "move" in types


def test_manager_registers_and_lists_session(tmp_path):
    manager = _manager(tmp_path)
    session = manager.start(_resolved(_settings()))
    assert manager.get(session.id) is session
    assert session in manager.sessions


def test_manager_marks_error_when_player_raises(tmp_path):
    boom = lambda side, resolved: _BoomPlayer(_info(side))  # noqa: E731
    manager = _manager(tmp_path, factory=boom)
    session = manager.start(_resolved(_settings()))

    assert session.join(timeout=5)
    assert session.status == STATUS_ERROR
    assert "exploded" in (session.error or "")


def test_manager_no_persist_writes_nothing(tmp_path):
    manager = _manager(tmp_path, persist=False)
    session = manager.start(_resolved(_settings()))
    assert session.join(timeout=5)
    assert not (tmp_path / session.id).exists()


# --- эндпоинт POST /games -----------------------------------------------------

def _client(tmp_path, settings=None, factory=None) -> tuple[TestClient, GameManager]:
    settings = settings or _settings()
    manager = _manager(tmp_path, factory=factory)
    app = create_app(settings=settings, game_manager=manager)
    return TestClient(app), manager


def test_post_games_starts_and_redirects(tmp_path):
    client, manager = _client(tmp_path)
    with client:
        resp = client.post(
            "/games",
            data={"white": "w-model", "black": "b-model"},
            follow_redirects=False,
        )
    assert resp.status_code == 303
    location = resp.headers["location"]
    assert location.startswith("/games/")
    game_id = location.rsplit("/", 1)[-1]
    session = manager.get(game_id)
    assert session is not None
    assert session.join(timeout=5)
    assert session.status == STATUS_FINISHED
    assert session.result == "0-1"


def test_post_games_unknown_model_rerenders_form_with_error(tmp_path):
    client, manager = _client(tmp_path)
    with client:
        resp = client.post(
            "/games",
            data={"white": "nope", "black": "b-model"},
            follow_redirects=False,
        )
    assert resp.status_code == 400
    assert "неизвестная модель" in resp.text
    assert manager.sessions == []  # партия не стартовала


def test_post_games_missing_key_rerenders_form_with_error(tmp_path):
    client, manager = _client(tmp_path, settings=_settings(key=None))
    with client:
        resp = client.post(
            "/games",
            data={"white": "w-model", "black": "b-model"},
            follow_redirects=False,
        )
    assert resp.status_code == 400
    assert "API-ключа" in resp.text
    assert manager.sessions == []
