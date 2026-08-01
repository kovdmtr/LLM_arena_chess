"""Тесты доступа к веб-UI «по ссылке» (секретный токен).

Если задан ``access_token``, к сайту пускают только запросы с верным токеном
(``?token=…`` → cookie); открыт без токена только health. Без токена сайт открыт
целиком (обратная совместимость). Поднимаем приложение с инъектированными
``Settings`` и подставным каталогом сборки SPA — тесты не зависят от того,
собран ли фронтенд.
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


def _spa(tmp_path):
    """Подставная сборка фронтенда: важно лишь наличие index.html."""
    (tmp_path / "index.html").write_text("<!DOCTYPE html><title>spa</title>", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "index.js").write_text("console.log(1)", encoding="utf-8")
    return tmp_path


def _app(token, tmp_path):
    return create_app(settings=_settings(), access_token=token, spa_dir=_spa(tmp_path))


def test_site_open_when_no_token_configured(tmp_path):
    with TestClient(_app(None, tmp_path)) as client:
        assert client.get("/").status_code == 200


def test_request_without_token_is_denied(tmp_path):
    with TestClient(_app("secret", tmp_path)) as client:
        resp = client.get("/")
    assert resp.status_code == 403
    assert "только по ссылке" in resp.text


def test_query_token_grants_and_sets_cookie(tmp_path):
    with TestClient(_app("secret", tmp_path)) as client:
        resp = client.get("/?token=secret")
        assert resp.status_code == 200
        assert client.cookies.get("arena_access") == "secret"
        # дальше навигация работает по cookie, без токена в URL.
        assert client.get("/games").status_code == 200


def test_wrong_token_is_denied(tmp_path):
    with TestClient(_app("secret", tmp_path)) as client:
        assert client.get("/?token=nope").status_code == 403


def test_cookie_alone_grants_access(tmp_path):
    app = _app("secret", tmp_path)
    with TestClient(app) as client:
        client.cookies.set("arena_access", "secret")
        assert client.get("/").status_code == 200


def test_only_health_is_open_when_gated(tmp_path):
    """Ассеты — часть закрытого сайта: cookie к их запросу уже поставлена."""
    with TestClient(_app("secret", tmp_path)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/assets/index.js").status_code == 403


def test_assets_load_after_token_sets_cookie(tmp_path):
    with TestClient(_app("secret", tmp_path)) as client:
        assert client.get("/?token=secret").status_code == 200
        assert client.get("/assets/index.js").status_code == 200


def test_token_from_secrets_env(tmp_path):
    # Без явного access_token токен берётся из секретов (.env/окружение).
    config = AppConfig.model_validate({"providers": _PROVIDERS, "models": _MODELS})
    settings = Settings(
        config=config,
        secrets=Secrets(_env_file=None, openai_api_key="sk", arena_access_token="zzz"),
    )
    with TestClient(create_app(settings=settings, spa_dir=_spa(tmp_path))) as client:
        assert client.get("/").status_code == 403
        assert client.get("/?token=zzz").status_code == 200
