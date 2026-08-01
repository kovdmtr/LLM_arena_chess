"""Раздача SPA-фронтенда из FastAPI: history-fallback, ассеты, отсутствие сборки.

Каталог сборки подставляется через ``create_app(spa_dir=...)`` — тесты не зависят
от того, собран ли реальный фронтенд (``src/arena/web/spa`` в ``.gitignore``).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from arena.config import AppConfig, Secrets, Settings
from arena.web import create_app

_INDEX = "<!DOCTYPE html><title>LLM Chess Arena</title><div id='root'></div>"
_PROVIDERS = {"openai": {"api_key_env": "OPENAI_API_KEY"}}
_MODELS = [{"id": "m", "provider": "openai", "display_name": "M"}]


def _settings() -> Settings:
    config = AppConfig.model_validate({"providers": _PROVIDERS, "models": _MODELS})
    return Settings(config=config, secrets=Secrets(_env_file=None, openai_api_key="sk"))


def _built_spa(tmp_path):
    (tmp_path / "index.html").write_text(_INDEX, encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "index-abc.js").write_text("export default 1", encoding="utf-8")
    (tmp_path / "assets" / "index-abc.css").write_text(".app{}", encoding="utf-8")
    return tmp_path


def _client(tmp_path, *, built: bool = True) -> TestClient:
    spa_dir = _built_spa(tmp_path) if built else tmp_path / "not-built"
    app = create_app(settings=_settings(), access_token="", spa_dir=spa_dir)
    return TestClient(app)


def test_index_is_served_at_root(tmp_path):
    with _client(tmp_path) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "<div id='root'>" in response.text


def test_deep_links_fall_back_to_index(tmp_path):
    """Маршруты SPA открываются напрямую и переживают перезагрузку страницы."""
    with _client(tmp_path) as client:
        for path in ("/games", "/games/new", "/games/abc123", "/tournaments", "/tournaments/t1"):
            response = client.get(path)
            assert response.status_code == 200, path
            assert "<div id='root'>" in response.text, path


def test_assets_are_served(tmp_path):
    with _client(tmp_path) as client:
        response = client.get("/assets/index-abc.js")

    assert response.status_code == 200
    assert "export default 1" in response.text


def test_api_and_health_are_not_swallowed_by_fallback(tmp_path):
    with _client(tmp_path) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert client.get("/api/models").json() == [
            {"id": "m", "display_name": "M", "provider": "openai", "has_key": True}
        ]


def test_unknown_api_path_is_404_not_index(tmp_path):
    """Опечатка в пути API — ошибка клиента, а не маршрут фронта."""
    with _client(tmp_path) as client:
        response = client.get("/api/nope")

    assert response.status_code == 404
    assert "<div id='root'>" not in response.text


def test_missing_build_explains_how_to_build(tmp_path):
    """Без собранного фронта сервер жив: API работает, страница объясняет, что делать."""
    with _client(tmp_path, built=False) as client:
        page = client.get("/")
        assert page.status_code == 503
        assert "npm run build" in page.text
        # API от фронтенда не зависит
        assert client.get("/api/games").status_code == 200
