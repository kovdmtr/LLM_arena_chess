"""Тесты списка партий и страницы партии (★, Phase 6, D-002).

Покрывают: список ``GET /games`` (пусто / из памяти / дедуп память+диск), страницу
завершённой партии ``GET /games/{id}`` (self-contained отчёт), страницу идущей партии
(live-просмотр через «ворота», удерживающие игрока в ходе) и 404 для неизвестной.
Игроки — фейковые (Fool's mate), без сети.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from arena.config import AppConfig, ModelCatalog, Secrets, Settings
from arena.models import LLMResponse, PlayerInfo
from arena.web import GameManager, create_app

_WHITE_MOVES = ["f3", "g4"]
_BLACK_MOVES = ["e5", "Qh4#"]
_PROVIDERS = {"openai": {"api_key_env": "OPENAI_API_KEY"}}
_MODELS = [
    {"id": "w-model", "provider": "openai", "display_name": "White Bot"},
    {"id": "b-model", "provider": "openai", "display_name": "Black Bot"},
]
CLOCK = lambda: datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc)  # noqa: E731


class _ScriptedPlayer:
    def __init__(self, info: PlayerInfo, moves, gate: threading.Event | None = None):
        self._info = info
        self._moves = list(moves)
        self._gate = gate

    @property
    def info(self) -> PlayerInfo:
        return self._info

    def respond(self, messages) -> LLMResponse:
        if self._gate is not None:
            self._gate.wait(5)  # держим партию «идущей», пока тест не отпустит
            self._gate = None
        move = self._moves.pop(0)
        return LLMResponse(reasoning=f"playing {move}", move=move)


def _settings() -> Settings:
    config = AppConfig.model_validate({"providers": _PROVIDERS, "models": _MODELS})
    return Settings(config=config, secrets=Secrets(_env_file=None, openai_api_key="sk-test"))


def _info(side: str) -> PlayerInfo:
    return PlayerInfo(model_id=f"{side}-model", provider="openai", display_name=f"{side.title()} Bot")


def _manager(tmp_path, *, gate: threading.Event | None = None) -> GameManager:
    players = {
        "white": _ScriptedPlayer(_info("white"), _WHITE_MOVES, gate=gate),
        "black": _ScriptedPlayer(_info("black"), _BLACK_MOVES),
    }
    return GameManager(
        player_factory=lambda side, resolved: players[side],
        games_root=str(tmp_path),
        clock=CLOCK,
    )


def _resolved(settings: Settings):
    catalog = ModelCatalog.from_settings(settings)
    return {"white": catalog.resolve("w-model"), "black": catalog.resolve("b-model")}


# --- список партий ------------------------------------------------------------

def test_games_list_empty(tmp_path):
    app = create_app(settings=_settings(), game_manager=_manager(tmp_path))
    with TestClient(app) as client:
        resp = client.get("/games")
    assert resp.status_code == 200
    assert "Пока нет партий" in resp.text


def test_games_list_shows_finished_game(tmp_path):
    manager = _manager(tmp_path)
    settings = _settings()
    app = create_app(settings=settings, game_manager=manager)
    session = manager.start(_resolved(settings))
    assert session.join(timeout=5)

    with TestClient(app) as client:
        resp = client.get("/games")
    assert resp.status_code == 200
    assert session.id in resp.text
    assert "White Bot" in resp.text and "Black Bot" in resp.text
    assert "0-1" in resp.text


def test_list_games_dedup_memory_and_disk(tmp_path):
    # Первый менеджер играет и сохраняет партию на диск.
    manager1 = _manager(tmp_path)
    settings = _settings()
    session = manager1.start(_resolved(settings))
    assert session.join(timeout=5)

    # Второй менеджер (без сессий в памяти) видит её на диске.
    manager2 = GameManager(games_root=str(tmp_path), clock=CLOCK)
    infos = manager2.list_games()
    ids = [g.id for g in infos]
    assert ids == [session.id]
    assert infos[0].status == "finished"
    assert infos[0].result == "0-1"
    assert infos[0].live is False


# --- страница партии ----------------------------------------------------------

def test_game_detail_finished_renders_report(tmp_path):
    manager = _manager(tmp_path)
    settings = _settings()
    app = create_app(settings=settings, game_manager=manager)
    session = manager.start(_resolved(settings))
    assert session.join(timeout=5)

    with TestClient(app) as client:
        resp = client.get(f"/games/{session.id}")
    assert resp.status_code == 200
    assert "<!DOCTYPE html>" in resp.text
    # отчёт показывает игроков и итог.
    assert "White Bot" in resp.text
    assert "0-1" in resp.text


def test_game_detail_running_shows_live_page(tmp_path):
    gate = threading.Event()
    manager = _manager(tmp_path, gate=gate)
    settings = _settings()
    app = create_app(settings=settings, game_manager=manager)
    session = manager.start(_resolved(settings))
    try:
        # партия удерживается «воротами» в первом ходу → не завершена.
        assert not session.done
        with TestClient(app) as client:
            resp = client.get(f"/games/{session.id}")
        assert resp.status_code == 200
        assert "WebSocket" in resp.text  # live-страница, а не отчёт
        assert f'data-game-id="{session.id}"' in resp.text
        assert "live-board" in resp.text
    finally:
        gate.set()
        session.join(timeout=5)


def test_game_detail_after_finish_switches_to_report(tmp_path):
    gate = threading.Event()
    manager = _manager(tmp_path, gate=gate)
    settings = _settings()
    app = create_app(settings=settings, game_manager=manager)
    session = manager.start(_resolved(settings))
    gate.set()
    assert session.join(timeout=5)

    with TestClient(app) as client:
        resp = client.get(f"/games/{session.id}")
    assert resp.status_code == 200
    assert "<!DOCTYPE html>" in resp.text  # уже отчёт


def test_game_detail_unknown_returns_404(tmp_path):
    app = create_app(settings=_settings(), game_manager=_manager(tmp_path))
    with TestClient(app) as client:
        resp = client.get("/games/does-not-exist")
    assert resp.status_code == 404


def test_load_record_unknown_and_bad_id(tmp_path):
    manager = _manager(tmp_path)
    assert manager.load_record("nope") is None
    assert manager.load_record("../escape") is None  # анти-traversal id
