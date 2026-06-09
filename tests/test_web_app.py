"""Smoke-тесты каркаса веб-приложения (★, Phase 6, D-002).

Поднимаем приложение через ``TestClient`` (без реального сервера) и проверяем
фундамент: health-эндпоинт, рендер стартовой страницы из шаблона, отдачу статики
и регистрацию ключевых роутов. Сетевых/LLM-вызовов здесь нет.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from arena.web import APP_TITLE, APP_VERSION, create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_health_returns_ok():
    with _client() as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == APP_TITLE
    assert body["version"] == APP_VERSION


def test_index_renders_html_page():
    with _client() as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "LLM Chess Arena" in resp.text
    # шаблон расширяет base.html → есть DOCTYPE и подключение статики.
    assert "<!DOCTYPE html>" in resp.text
    assert "/static/app.css" in resp.text


def test_static_css_is_served():
    with _client() as client:
        resp = client.get("/static/app.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers["content-type"]
    assert "LLM Chess Arena" in resp.text  # комментарий в начале файла


def test_create_app_stores_settings_on_state():
    sentinel = object()
    app = create_app(settings=sentinel)
    assert app.state.settings is sentinel
    # без аргумента настройки не загружаются принудительно (каркасу не нужны).
    assert create_app().state.settings is None


def test_app_metadata():
    app = create_app()
    assert app.title == APP_TITLE
    assert app.version == APP_VERSION
