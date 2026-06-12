"""Тесты списка турниров и страницы турнира (веб-UI турниров).

Поднимаем приложение с инъектированным реальным ``TournamentManager`` на фейковых
игроках (чемпион/сдающийся). Покрываем: список ``GET /tournaments`` (пусто/завершённый),
страницу ``GET /tournaments/{id}`` (итоговая таблица+расписание; идущий — авто-обновление
через «ворота»; 404 для неизвестного).
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from arena.config import AppConfig, Secrets, Settings
from arena.models import LLMResponse, PlayerInfo
from arena.web import create_app
from arena.web.tournaments import TournamentManager

CLOCK = lambda: datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)  # noqa: E731
_PROVIDERS = {"openai": {"api_key_env": "OPENAI_API_KEY"}}
_MODELS = [
    {"id": "champ", "provider": "openai", "display_name": "Champion"},
    {"id": "weak", "provider": "openai", "display_name": "Weakling"},
]
_CHAMP = PlayerInfo(model_id="champ", provider="openai", display_name="Champion")
_WEAK = PlayerInfo(model_id="weak", provider="openai", display_name="Weakling")


class _ChampPlayer:
    def __init__(self, info, gate=None):
        self._info = info
        self._gate = gate

    @property
    def info(self):
        return self._info

    def respond(self, messages) -> LLMResponse:
        if self._gate is not None:
            self._gate.wait(5)  # держим турнир «идущим», пока тест не отпустит
            self._gate = None
        return LLMResponse(move="e4", reasoning="advance")


class _ResignPlayer:
    def __init__(self, info):
        self._info = info

    @property
    def info(self):
        return self._info

    def respond(self, messages) -> LLMResponse:
        return LLMResponse(resign=True, reasoning="gg")


def _settings() -> Settings:
    config = AppConfig.model_validate({"providers": _PROVIDERS, "models": _MODELS})
    return Settings(config=config, secrets=Secrets(_env_file=None, openai_api_key="sk"))


def _manager(tmp_path, *, gate=None) -> TournamentManager:
    def factory(side, info):
        if info.model_id == "champ":
            return _ChampPlayer(info, gate)
        return _ResignPlayer(info)

    return TournamentManager(
        player_factory=factory,
        games_root=str(tmp_path),
        clock=CLOCK,
        engine_factory=lambda: None,
    )


def _app(manager):
    return create_app(settings=_settings(), tournament_manager=manager)


# --- список ----------------------------------------------------------------


def test_tournaments_list_empty(tmp_path):
    with TestClient(_app(_manager(tmp_path))) as client:
        resp = client.get("/tournaments")
    assert resp.status_code == 200
    assert "Пока нет турниров" in resp.text


def test_tournaments_list_shows_finished(tmp_path):
    manager = _manager(tmp_path)
    manager.start([_CHAMP, _WEAK], double=True, tournament_id="t1").join(timeout=10)
    with TestClient(_app(manager)) as client:
        html = client.get("/tournaments").text
    assert "t1" in html
    assert "Champion" in html and "Weakling" in html
    assert "2/2" in html  # сыграно/всего


# --- страница турнира ------------------------------------------------------


def test_tournament_detail_finished_shows_standings_and_schedule(tmp_path):
    manager = _manager(tmp_path)
    manager.start([_CHAMP, _WEAK], double=True, tournament_id="t1").join(timeout=10)
    with TestClient(_app(manager)) as client:
        html = client.get("/tournaments/t1").text
    # Таблица с чемпионом и расписание с результатами и ссылкой на партию.
    assert "Champion" in html
    assert "<table" in html
    assert "/games/t1-g01" in html
    assert "1-0" in html or "0-1" in html
    assert 'http-equiv="refresh"' not in html  # завершён → без авто-обновления


def test_tournament_detail_running_auto_refreshes(tmp_path):
    gate = threading.Event()
    manager = _manager(tmp_path, gate=gate)
    session = manager.start([_CHAMP, _WEAK], tournament_id="t1")
    try:
        assert not session.done  # удерживается «воротами»
        with TestClient(_app(manager)) as client:
            html = client.get("/tournaments/t1").text
        assert 'http-equiv="refresh"' in html  # идущий → авто-обновление
        assert "идёт" in html
    finally:
        gate.set()
        session.join(timeout=10)


def test_tournament_detail_unknown_returns_404(tmp_path):
    with TestClient(_app(_manager(tmp_path))) as client:
        resp = client.get("/tournaments/nope")
    assert resp.status_code == 404
