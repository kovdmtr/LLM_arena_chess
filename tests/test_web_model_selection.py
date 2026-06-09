"""Тесты страницы выбора моделей (★, Phase 6, D-002).

Поднимаем приложение с инъектированными ``Settings`` (детерминированный каталог,
без чтения реального ``.env``) и проверяем страницу ``/games/new``: каталог
отрисован формой выбора белых/чёрных, модели без ключа помечены и недоступны,
секрет ключа не утекает в HTML (D-003), пустой каталог отрабатывает корректно.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from arena.config import AppConfig, Secrets, Settings
from arena.web import create_app

_PROVIDERS = {
    "openai": {"api_key_env": "OPENAI_API_KEY"},
    "anthropic": {"api_key_env": "ANTHROPIC_API_KEY"},
}

_MODELS = [
    {"id": "gpt-test", "provider": "openai", "display_name": "GPT Test"},
    {"id": "claude-test", "provider": "anthropic", "display_name": "Claude Test"},
]

_SECRET = "sk-should-not-leak"


def _settings(models=_MODELS, *, openai_key=_SECRET, anthropic_key=None) -> Settings:
    config = AppConfig.model_validate({"providers": _PROVIDERS, "models": models})
    # Ключи задаём явно (priority над окружением), .env отключаем — детерминизм.
    secrets = Secrets(
        _env_file=None,
        openai_api_key=openai_key,
        anthropic_api_key=anthropic_key,
    )
    return Settings(config=config, secrets=secrets)


def _client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings=settings))


def test_new_game_lists_catalog_models():
    with _client(_settings()) as client:
        resp = client.get("/games/new")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "GPT Test" in resp.text
    assert "Claude Test" in resp.text
    # форма выбора обеих сторон.
    assert 'name="white"' in resp.text
    assert 'name="black"' in resp.text
    assert 'action="/games"' in resp.text


def test_model_with_key_is_selectable_without_key_is_disabled():
    # openai имеет ключ, anthropic — нет.
    with _client(_settings()) as client:
        html = client.get("/games/new").text
    # опция модели без ключа помечена disabled и подписью.
    assert 'value="claude-test" disabled' in html
    assert "ключ не задан" in html
    # модель с ключом — обычная опция (без disabled на этом value).
    assert 'value="gpt-test" disabled' not in html
    assert 'value="gpt-test"' in html


def test_api_key_value_never_leaks_into_page():
    with _client(_settings()) as client:
        html = client.get("/games/new").text
    assert _SECRET not in html


def test_empty_catalog_renders_placeholder():
    with _client(_settings(models=[])) as client:
        resp = client.get("/games/new")
    assert resp.status_code == 200
    assert "нет моделей" in resp.text
    assert "<select" not in resp.text


def test_index_links_to_new_game_page():
    with _client(_settings()) as client:
        html = client.get("/").text
    assert "/games/new" in html


def test_catalog_is_built_once_and_cached_on_state():
    app = create_app(settings=_settings())
    with TestClient(app) as client:
        client.get("/games/new")
        first = app.state.catalog
        client.get("/games/new")
    assert first is not None
    assert app.state.catalog is first  # каталог не пересоздаётся на каждый запрос
