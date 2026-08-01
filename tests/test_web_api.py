"""Тесты JSON-API веб-слоя (``/api/*``) — контракт данных для SPA-фронтенда.

Как и в тестах SSR-роутов, ``GameManager`` подменяется фабрикой скриптованных
игроков (без сети и LLM-вызовов): два игрока доигрывают «дурацкий мат». На этом
проверяются каталог моделей, старт партии, список, полная запись и экспорт PGN.
``access_token=""`` выключает «ворота» доступа явно — тесты не зависят от
окружения.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from arena.config import AppConfig, Secrets, Settings
from arena.models import LLMResponse, PlayerInfo
from arena.web import GameManager, create_app

# Fool's mate: 1. f3 e5 2. g4 Qh4# — чёрные ставят мат (0-1).
_WHITE_MOVES = ["f3", "g4"]
_BLACK_MOVES = ["e5", "Qh4#"]

_SECRET_KEY = "sk-super-secret-value"
_PROVIDERS = {
    "openai": {"api_key_env": "OPENAI_API_KEY"},
    "anthropic": {"api_key_env": "ANTHROPIC_API_KEY"},
}
_MODELS = [
    {"id": "w-model", "provider": "openai", "display_name": "White Model"},
    {"id": "b-model", "provider": "openai", "display_name": "Black Model"},
    # У anthropic ключа в тестовых секретах нет → has_key=False.
    {"id": "no-key-model", "provider": "anthropic", "display_name": "Keyless Model"},
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


def _settings() -> Settings:
    config = AppConfig.model_validate({"providers": _PROVIDERS, "models": _MODELS})
    secrets = Secrets(_env_file=None, openai_api_key=_SECRET_KEY)
    return Settings(config=config, secrets=secrets)


def _info(side: str) -> PlayerInfo:
    return PlayerInfo(model_id=f"{side}-model", provider="openai", display_name=side)


def _scripted_factory():
    players = {
        "white": _ScriptedPlayer(_info("white"), _WHITE_MOVES),
        "black": _ScriptedPlayer(_info("black"), _BLACK_MOVES),
    }
    return lambda side, resolved: players[side]


def _client(tmp_path) -> TestClient:
    manager = GameManager(
        player_factory=_scripted_factory(),
        games_root=str(tmp_path),
        clock=CLOCK,
    )
    app = create_app(_settings(), game_manager=manager, access_token="")
    return TestClient(app)


def _play(client: TestClient) -> str:
    """Стартовать партию через API и дождаться её завершения; вернуть id."""
    response = client.post("/api/games", json={"white": "w-model", "black": "b-model"})
    assert response.status_code == 201, response.text
    game_id = response.json()["id"]
    session = client.app.state.game_manager.get(game_id)
    assert session.join(timeout=5)
    return game_id


# --- каталог моделей ----------------------------------------------------------

def test_models_endpoint_lists_catalog_with_key_flags(tmp_path):
    client = _client(tmp_path)

    payload = client.get("/api/models").json()

    assert [m["id"] for m in payload] == ["w-model", "b-model", "no-key-model"]
    by_id = {m["id"]: m for m in payload}
    assert by_id["w-model"] == {
        "id": "w-model",
        "display_name": "White Model",
        "provider": "openai",
        "has_key": True,
    }
    # Модель без ключа видна, но помечена — фронт её задизейблит.
    assert by_id["no-key-model"]["has_key"] is False


def test_models_endpoint_does_not_leak_api_key(tmp_path):
    client = _client(tmp_path)

    assert _SECRET_KEY not in client.get("/api/models").text


# --- старт партии -------------------------------------------------------------

def test_start_game_returns_id_and_runs_game(tmp_path):
    client = _client(tmp_path)

    game_id = _play(client)

    assert game_id
    session = client.app.state.game_manager.get(game_id)
    assert session.result == "0-1"
    assert (tmp_path / game_id / "game.json").is_file()


def test_start_game_rejects_unknown_model(tmp_path):
    client = _client(tmp_path)

    response = client.post("/api/games", json={"white": "nope", "black": "b-model"})

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "error.modelUnknown"
    assert detail["params"] == {"id": "nope"}
    # техническая подробность остаётся для диагностики
    assert "nope" in detail["message"]


def test_start_game_rejects_model_without_key(tmp_path):
    client = _client(tmp_path)

    response = client.post(
        "/api/games", json={"white": "no-key-model", "black": "b-model"}
    )

    assert response.status_code == 400
    assert _SECRET_KEY not in response.text


def test_start_game_validates_payload(tmp_path):
    client = _client(tmp_path)

    assert client.post("/api/games", json={"white": "w-model"}).status_code == 422


# --- список и запись партии ---------------------------------------------------

def test_games_endpoint_lists_played_game(tmp_path):
    client = _client(tmp_path)
    game_id = _play(client)

    items = client.get("/api/games").json()

    assert [item["id"] for item in items] == [game_id]
    card = items[0]
    assert card["white"] == "white" and card["black"] == "black"
    assert card["result"] == "0-1"
    assert card["live"] is False
    assert card["created_at"].startswith("2026-06-09T12:00:00")


def test_game_endpoint_returns_record_with_moves(tmp_path):
    client = _client(tmp_path)
    game_id = _play(client)

    payload = client.get(f"/api/games/{game_id}").json()

    assert payload["id"] == game_id
    assert payload["live"] is False
    assert payload["status"] == "finished"
    record = payload["record"]
    assert record["result"] == "0-1"
    assert record["termination"] == "checkmate"
    assert [move["san"] for move in record["moves"]] == ["f3", "e5", "g4", "Qh4#"]
    # Фронту нужны позиция и рассуждение каждого хода — они в записи.
    assert record["moves"][0]["fen_after"]
    assert record["moves"][0]["reasoning"] == "playing f3"


def test_game_endpoint_404_for_unknown_game(tmp_path):
    client = _client(tmp_path)

    assert client.get("/api/games/nope").status_code == 404


def test_game_endpoint_does_not_leak_api_key(tmp_path):
    client = _client(tmp_path)
    game_id = _play(client)

    assert _SECRET_KEY not in client.get(f"/api/games/{game_id}").text


# --- экспорт PGN --------------------------------------------------------------

def test_pgn_endpoint_returns_downloadable_pgn(tmp_path):
    client = _client(tmp_path)
    game_id = _play(client)

    response = client.get(f"/api/games/{game_id}/pgn")

    assert response.status_code == 200
    assert f'filename="{game_id}.pgn"' in response.headers["content-disposition"]
    body = response.text
    assert '[Result "0-1"]' in body
    assert "Qh4#" in body


def test_pgn_endpoint_404_for_unknown_game(tmp_path):
    client = _client(tmp_path)

    assert client.get("/api/games/nope/pgn").status_code == 404


# --- язык интерфейса → язык ответов моделей -----------------------------------

def test_start_game_stores_ui_language_in_settings(tmp_path):
    """Язык интерфейса доезжает до настроек партии — на нём модели рассуждают."""
    client = _client(tmp_path)

    response = client.post(
        "/api/games", json={"white": "w-model", "black": "b-model", "language": "en"}
    )
    assert response.status_code == 201, response.text
    game_id = response.json()["id"]

    record = client.app.state.game_manager.get(game_id).record
    assert record.settings.response_language == "en"


def test_start_game_without_language_keeps_config_default(tmp_path):
    client = _client(tmp_path)

    game_id = _play(client)

    record = client.app.state.game_manager.load_record(game_id)
    assert record.settings.response_language is None


def test_start_game_ignores_unsupported_language(tmp_path):
    """Незнакомый код языка не роняет старт — партия идёт без указания языка."""
    client = _client(tmp_path)

    response = client.post(
        "/api/games", json={"white": "w-model", "black": "b-model", "language": "klingon"}
    )
    assert response.status_code == 201, response.text

    record = client.app.state.game_manager.get(response.json()["id"]).record
    assert record.settings.response_language is None


def test_language_code_is_normalized(tmp_path):
    client = _client(tmp_path)

    response = client.post(
        "/api/games", json={"white": "w-model", "black": "b-model", "language": " RU "}
    )
    assert response.status_code == 201, response.text

    record = client.app.state.game_manager.get(response.json()["id"]).record
    assert record.settings.response_language == "ru"


# --- коды ошибок (интерфейс одноязычный: текст подставляет фронт) -------------

def test_error_detail_carries_machine_readable_code(tmp_path):
    """Отказ описан кодом + параметрами — фронт переведёт его на язык интерфейса."""
    client = _client(tmp_path)

    response = client.post("/api/games", json={"white": "no-key-model", "black": "b-model"})

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "error.modelNoKey"
    assert detail["params"] == {"id": "no-key-model"}


def test_missing_game_reports_code_and_id(tmp_path):
    client = _client(tmp_path)

    for path in ("/api/games/ghost", "/api/games/ghost/pgn"):
        response = client.get(path)
        assert response.status_code == 404, path
        detail = response.json()["detail"]
        assert detail["code"] == "error.gameNotFound"
        assert detail["params"] == {"id": "ghost"}


def test_error_detail_never_leaks_api_key(tmp_path):
    client = _client(tmp_path)

    response = client.post("/api/games", json={"white": "nope", "black": "b-model"})

    assert _SECRET_KEY not in response.text


def test_report_downloads_as_self_contained_file(tmp_path):
    """Разбор показывает SPA; этот файл — тот же отчёт, но автономный (D-013)."""
    client = _client(tmp_path)
    game_id = _play(client)

    response = client.get(f"/api/games/{game_id}/report")

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert f'filename="{game_id}.html"' in response.headers["content-disposition"]
    body = response.text
    assert body.lstrip().startswith("<!DOCTYPE html>")
    # доски встроены как inline-SVG; внешних файлов и сети нет
    # (xmlns="http://www.w3.org/2000/svg" — это пространство имён, не запрос)
    assert "<img" not in body
    assert "<link" not in body
    assert 'src="http' not in body
    # ссылки «на главную» в скачанном файле нет — он открывается без сервера
    assert 'href="/"' not in body


def test_report_of_unknown_game_is_404(tmp_path):
    client = _client(tmp_path)

    response = client.get("/api/games/ghost/report")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "error.gameNotFound"
