"""Тесты JSON-API турниров (``/api/tournaments*``) — данные для SPA-фронтенда.

Поднимаем приложение с реальным ``TournamentManager`` на фейковых игроках
(чемпион делает ход, соперник сдаётся) — без сети и LLM-вызовов. Покрываем старт
турнира с валидацией, список карточек и детальный ответ (участники, прогресс,
таблица, расписание). ``access_token=""`` выключает «ворота» доступа явно.
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

_SECRET_KEY = "sk-super-secret-value"
_PROVIDERS = {
    "openai": {"api_key_env": "OPENAI_API_KEY"},
    "anthropic": {"api_key_env": "ANTHROPIC_API_KEY"},
}
_MODELS = [
    {"id": "champ", "provider": "openai", "display_name": "Champion"},
    {"id": "weak", "provider": "openai", "display_name": "Weakling"},
    # Ключа для anthropic в секретах нет → участие невозможно (fail-fast).
    {"id": "no-key", "provider": "anthropic", "display_name": "Keyless"},
]
_CHAMP = PlayerInfo(model_id="champ", provider="openai", display_name="Champion")
_WEAK = PlayerInfo(model_id="weak", provider="openai", display_name="Weakling")


class _ChampPlayer:
    """Игрок, всегда играющий 1. e4 (опц. ждёт «ворота», чтобы турнир был живым)."""

    def __init__(self, info, gate=None):
        self._info = info
        self._gate = gate

    @property
    def info(self):
        return self._info

    def respond(self, messages) -> LLMResponse:
        if self._gate is not None:
            self._gate.wait(5)
            self._gate = None
        return LLMResponse(move="e4", reasoning="advance")


class _ResignPlayer:
    """Игрок, немедленно сдающийся — партия заканчивается за один полуход."""

    def __init__(self, info):
        self._info = info

    @property
    def info(self):
        return self._info

    def respond(self, messages) -> LLMResponse:
        return LLMResponse(resign=True, reasoning="gg")


def _settings() -> Settings:
    config = AppConfig.model_validate({"providers": _PROVIDERS, "models": _MODELS})
    secrets = Secrets(_env_file=None, openai_api_key=_SECRET_KEY)
    return Settings(config=config, secrets=secrets)


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


def _client(manager) -> TestClient:
    app = create_app(
        settings=_settings(), tournament_manager=manager, access_token=""
    )
    return TestClient(app)


# --- старт турнира ------------------------------------------------------------

def test_start_tournament_returns_id_and_runs(tmp_path):
    manager = _manager(tmp_path)
    client = _client(manager)

    response = client.post(
        "/api/tournaments", json={"models": ["champ", "weak"], "double": True}
    )

    assert response.status_code == 201, response.text
    tournament_id = response.json()["id"]
    assert manager.get(tournament_id).join(timeout=10)
    # Два круга на двух участниках — две партии, обе сыграны.
    record = manager.load_record(tournament_id)
    assert len(record.games) == 2
    assert all(game.result is not None for game in record.games)


def test_start_tournament_requires_two_models(tmp_path):
    client = _client(_manager(tmp_path))

    # Дубли схлопываются — одна уникальная модель это всё ещё «мало».
    response = client.post("/api/tournaments", json={"models": ["champ", "champ"]})

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "error.tournamentTooFewModels"


def test_start_tournament_rejects_model_without_key(tmp_path):
    client = _client(_manager(tmp_path))

    response = client.post("/api/tournaments", json={"models": ["champ", "no-key"]})

    assert response.status_code == 400
    assert _SECRET_KEY not in response.text


def test_start_tournament_rejects_unknown_model(tmp_path):
    client = _client(_manager(tmp_path))

    response = client.post("/api/tournaments", json={"models": ["champ", "nope"]})

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "error.modelUnknown"


# --- список -------------------------------------------------------------------

def test_tournaments_list_empty(tmp_path):
    client = _client(_manager(tmp_path))

    assert client.get("/api/tournaments").json() == []


def test_tournaments_list_shows_finished_with_progress(tmp_path):
    manager = _manager(tmp_path)
    manager.start([_CHAMP, _WEAK], double=True, tournament_id="t1").join(timeout=10)
    client = _client(manager)

    items = client.get("/api/tournaments").json()

    assert len(items) == 1
    card = items[0]
    assert card["id"] == "t1"
    assert card["participants"] == ["Champion", "Weakling"]
    assert card["double"] is True
    assert card["live"] is False
    assert card["played"] == card["total"] == 2
    assert card["created_at"].startswith("2026-06-11T12:00:00")


# --- детали -------------------------------------------------------------------

def test_tournament_detail_returns_standings_and_schedule(tmp_path):
    manager = _manager(tmp_path)
    manager.start([_CHAMP, _WEAK], double=True, tournament_id="t1").join(timeout=10)
    client = _client(manager)

    payload = client.get("/api/tournaments/t1").json()

    assert payload["id"] == "t1"
    assert payload["live"] is False
    assert payload["status"] == "finished"
    assert payload["double"] is True
    assert payload["played"] == payload["total"] == 2
    assert [p["model_id"] for p in payload["participants"]] == ["champ", "weak"]
    # Сдающийся проигрывает обе партии → чемпион первый с 2 очками.
    rows = payload["standings"]["models"]
    assert rows[0]["model_id"] == "champ"
    assert rows[0]["points"] == 2.0
    # Расписание несёт и id моделей, и человекочитаемые имена, и ссылку на партию.
    schedule = payload["schedule"]
    assert len(schedule) == 2
    assert schedule[0]["white_name"] in {"Champion", "Weakling"}
    assert schedule[0]["result"] is not None
    assert schedule[0]["game_id"]


def test_tournament_detail_live_reports_partial_progress(tmp_path):
    gate = threading.Event()
    manager = _manager(tmp_path, gate=gate)
    session = manager.start([_CHAMP, _WEAK], double=True, tournament_id="t-live")
    client = _client(manager)
    try:
        payload = client.get("/api/tournaments/t-live").json()

        assert payload["live"] is True
        assert payload["status"] == "running"
        assert payload["played"] < payload["total"]
    finally:
        gate.set()
        session.join(timeout=10)


def test_tournament_detail_404_for_unknown(tmp_path):
    client = _client(_manager(tmp_path))

    assert client.get("/api/tournaments/nope").status_code == 404


# --- язык интерфейса → язык ответов моделей во всех партиях турнира -----------

def test_start_tournament_stores_ui_language(tmp_path):
    manager = _manager(tmp_path, gate=threading.Event())
    client = _client(manager)

    response = client.post(
        "/api/tournaments",
        json={"models": ["champ", "weak"], "double": False, "language": "en"},
    )

    assert response.status_code == 201, response.text
    session = manager.get(response.json()["id"])
    assert session.player_settings is not None
    assert session.player_settings.response_language == "en"


def test_start_tournament_without_language_keeps_default(tmp_path):
    manager = _manager(tmp_path, gate=threading.Event())
    client = _client(manager)

    response = client.post("/api/tournaments", json={"models": ["champ", "weak"]})

    session = manager.get(response.json()["id"])
    assert session.player_settings is None


def test_missing_tournament_reports_code_and_id(tmp_path):
    client = _client(_manager(tmp_path))

    response = client.get("/api/tournaments/ghost")

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["code"] == "error.tournamentNotFound"
    assert detail["params"] == {"id": "ghost"}


def test_tournament_model_without_key_reports_code(tmp_path):
    client = _client(_manager(tmp_path))

    response = client.post("/api/tournaments", json={"models": ["champ", "no-key"]})

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "error.modelNoKey"
