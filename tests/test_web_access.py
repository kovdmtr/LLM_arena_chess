"""Тесты доступа к веб-UI «по ссылке» (секретный токен).

Если задан ``access_token``, к сайту пускают только запросы с верным токеном
(``?token=…`` → cookie); health и статика открыты всегда; без токена сайт открыт
(обратная совместимость). Поднимаем приложение с инъектированными ``Settings``.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from arena.config import AppConfig, Secrets, Settings
from arena.web import create_app

_PROVIDERS = {"openai": {"api_key_env": "OPENAI_API_KEY"}}
_MODELS = [{"id": "m", "provider": "openai", "display_name": "M"}]


def _settings() -> Settings:
    config = AppConfig.model_validate({"providers": _PROVIDERS, "models": _MODELS})
    return Settings(config=config, secrets=Secrets(_env_file=None, openai_api_key="sk"))


def _app(token):
    return create_app(settings=_settings(), access_token=token)


def test_site_open_when_no_token_configured():
    with TestClient(_app(None)) as client:
        assert client.get("/").status_code == 200


def test_request_without_token_is_denied():
    with TestClient(_app("secret")) as client:
        resp = client.get("/")
    assert resp.status_code == 403
    assert "только по ссылке" in resp.text


def test_query_token_grants_and_sets_cookie():
    with TestClient(_app("secret")) as client:
        resp = client.get("/?token=secret")
        assert resp.status_code == 200
        assert client.cookies.get("arena_access") == "secret"
        # дальше навигация работает по cookie, без токена в URL.
        assert client.get("/games").status_code == 200


def test_wrong_token_is_denied():
    with TestClient(_app("secret")) as client:
        assert client.get("/?token=nope").status_code == 403


def test_cookie_alone_grants_access():
    app = _app("secret")
    with TestClient(app) as client:
        client.cookies.set("arena_access", "secret")
        assert client.get("/").status_code == 200


def test_health_and_static_open_even_when_gated():
    with TestClient(_app("secret")) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/static/app.css").status_code == 200


def test_token_from_secrets_env(monkeypatch):
    # Без явного access_token токен берётся из секретов (.env/окружение).
    config = AppConfig.model_validate({"providers": _PROVIDERS, "models": _MODELS})
    settings = Settings(
        config=config,
        secrets=Secrets(_env_file=None, openai_api_key="sk", arena_access_token="zzz"),
    )
    with TestClient(create_app(settings=settings)) as client:
        assert client.get("/").status_code == 403
        assert client.get("/?token=zzz").status_code == 200
