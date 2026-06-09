"""Тесты WebSocket live-просмотра партии (★, Phase 6, D-002).

Партию доигрывают скриптованные игроки (Fool's mate), затем по WebSocket
проверяется поток событий: replay от старта до мата, обогащение кадров (SVG доски,
рассуждение хода), финальный кадр статуса и обработка неизвестной партии.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from arena.config import AppConfig, ModelCatalog, Secrets, Settings
from arena.models import LLMResponse, PlayerInfo
from arena.web import GameManager, create_app

_WHITE_MOVES = ["f3", "g4"]
_BLACK_MOVES = ["e5", "Qh4#"]
_PROVIDERS = {"openai": {"api_key_env": "OPENAI_API_KEY"}}
_MODELS = [
    {"id": "w-model", "provider": "openai", "display_name": "White Model"},
    {"id": "b-model", "provider": "openai", "display_name": "Black Model"},
]
CLOCK = lambda: datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc)  # noqa: E731


class _ScriptedPlayer:
    def __init__(self, info: PlayerInfo, moves):
        self._info = info
        self._moves = list(moves)

    @property
    def info(self) -> PlayerInfo:
        return self._info

    def respond(self, messages) -> LLMResponse:
        move = self._moves.pop(0)
        return LLMResponse(reasoning=f"playing {move}", move=move)


def _settings() -> Settings:
    config = AppConfig.model_validate({"providers": _PROVIDERS, "models": _MODELS})
    return Settings(config=config, secrets=Secrets(_env_file=None, openai_api_key="sk-test"))


def _info(side: str) -> PlayerInfo:
    return PlayerInfo(model_id=f"{side}-model", provider="openai", display_name=side)


def _manager(tmp_path) -> GameManager:
    players = {
        "white": _ScriptedPlayer(_info("white"), _WHITE_MOVES),
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


def _drain(ws) -> list[dict]:
    frames = []
    while True:
        try:
            frames.append(ws.receive_json())
        except WebSocketDisconnect:
            break
    return frames


def test_ws_replays_full_game_to_finish(tmp_path):
    manager = _manager(tmp_path)
    settings = _settings()
    app = create_app(settings=settings, game_manager=manager)
    session = manager.start(_resolved(settings))
    assert session.join(timeout=5)  # детерминизм: все события уже в буфере

    with TestClient(app) as client:
        with client.websocket_connect(f"/games/{session.id}/ws") as ws:
            frames = _drain(ws)

    types = [f["type"] for f in frames]
    assert types[0] == "game_start"
    assert "move" in types
    assert types[-1] == "status"  # финальный кадр статуса


def test_ws_move_frame_carries_svg_and_reasoning(tmp_path):
    manager = _manager(tmp_path)
    settings = _settings()
    app = create_app(settings=settings, game_manager=manager)
    session = manager.start(_resolved(settings))
    assert session.join(timeout=5)

    with TestClient(app) as client:
        with client.websocket_connect(f"/games/{session.id}/ws") as ws:
            frames = _drain(ws)

    moves = [f for f in frames if f["type"] == "move"]
    assert moves, "должны быть кадры ходов"
    first = moves[0]["payload"]
    assert first["san"] == "f3"
    assert "<svg" in first["svg"]
    assert first["reasoning"] == "playing f3"


def test_ws_status_frame_reports_result(tmp_path):
    manager = _manager(tmp_path)
    settings = _settings()
    app = create_app(settings=settings, game_manager=manager)
    session = manager.start(_resolved(settings))
    assert session.join(timeout=5)

    with TestClient(app) as client:
        with client.websocket_connect(f"/games/{session.id}/ws") as ws:
            frames = _drain(ws)

    status_frame = frames[-1]["payload"]
    assert status_frame["status"] == "finished"
    assert status_frame["result"] == "0-1"
    assert status_frame["termination"] == "checkmate"


def test_ws_unknown_game_sends_error_frame(tmp_path):
    app = create_app(settings=_settings(), game_manager=_manager(tmp_path))
    with TestClient(app) as client:
        with client.websocket_connect("/games/does-not-exist/ws") as ws:
            frames = _drain(ws)
    assert frames[0]["type"] == "error"
    assert "unknown" in frames[0]["payload"]["message"]
