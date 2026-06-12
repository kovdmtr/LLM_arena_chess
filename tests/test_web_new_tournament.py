"""Тесты страницы создания турнира и эндпоинта запуска (веб-UI турниров).

Приложение поднимается с инъектированными ``Settings`` (детерминированный каталог) и
фейковым ``TournamentManager`` (фиксирует вызов ``start`` без реального прогона).
Проверяем форму ``/tournaments/new`` и ``POST /tournaments``: валидацию (≥2 модели,
наличие ключа), редирект на страницу турнира, не утечку ключа.
"""

from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from arena.config import AppConfig, Secrets, Settings
from arena.web import create_app

_PROVIDERS = {
    "openai": {"api_key_env": "OPENAI_API_KEY"},
    "anthropic": {"api_key_env": "ANTHROPIC_API_KEY"},
}
_MODELS = [
    {"id": "gpt-a", "provider": "openai", "display_name": "GPT A"},
    {"id": "gpt-b", "provider": "openai", "display_name": "GPT B"},
    {"id": "claude-x", "provider": "anthropic", "display_name": "Claude X"},
]
_SECRET = "sk-should-not-leak"


def _settings() -> Settings:
    config = AppConfig.model_validate({"providers": _PROVIDERS, "models": _MODELS})
    secrets = Secrets(_env_file=None, openai_api_key=_SECRET, anthropic_api_key=None)
    return Settings(config=config, secrets=secrets)


class _FakeTournamentManager:
    """Фейковый менеджер: фиксирует ``start`` и отдаёт сессию с ``id``."""

    def __init__(self):
        self.started = None

    def start(self, participants, *, double=False, tournament_id=None):
        self.started = {"participants": participants, "double": double}
        return SimpleNamespace(id="t-xyz")


def _client(manager=None) -> TestClient:
    return TestClient(
        create_app(settings=_settings(), tournament_manager=manager)
    )


# --- страница создания -----------------------------------------------------


def test_new_tournament_lists_models_as_checkboxes():
    with _client() as client:
        html = client.get("/tournaments/new").text
    assert "GPT A" in html and "GPT B" in html and "Claude X" in html
    assert 'name="models"' in html
    assert 'name="double"' in html
    assert 'action="/tournaments"' in html


def test_model_without_key_is_disabled_and_key_not_leaked():
    with _client() as client:
        html = client.get("/tournaments/new").text
    assert 'value="claude-x" disabled' in html  # нет ключа → недоступна
    assert 'value="gpt-a" disabled' not in html
    assert _SECRET not in html


def test_index_links_to_tournament_pages():
    with _client() as client:
        html = client.get("/").text
    assert "/tournaments/new" in html
    assert "/tournaments" in html


# --- запуск ----------------------------------------------------------------


def test_post_starts_tournament_and_redirects():
    fake = _FakeTournamentManager()
    with _client(fake) as client:
        resp = client.post(
            "/tournaments",
            data={"models": ["gpt-a", "gpt-b"], "double": "true"},
            follow_redirects=False,
        )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/tournaments/t-xyz"
    assert fake.started["double"] is True
    assert [p.model_id for p in fake.started["participants"]] == ["gpt-a", "gpt-b"]


def test_post_requires_at_least_two_models():
    fake = _FakeTournamentManager()
    with _client(fake) as client:
        resp = client.post(
            "/tournaments", data={"models": ["gpt-a"]}, follow_redirects=False
        )
    assert resp.status_code == 400
    assert "минимум две" in resp.text
    assert fake.started is None  # турнир не стартовал


def test_post_rejects_model_without_key():
    fake = _FakeTournamentManager()
    with _client(fake) as client:
        resp = client.post(
            "/tournaments",
            data={"models": ["gpt-a", "claude-x"]},
            follow_redirects=False,
        )
    assert resp.status_code == 400
    assert fake.started is None


def test_post_dedupes_models():
    fake = _FakeTournamentManager()
    with _client(fake) as client:
        client.post(
            "/tournaments",
            data={"models": ["gpt-a", "gpt-a", "gpt-b"]},
            follow_redirects=False,
        )
    # Дубликат схлопнут → два участника.
    assert [p.model_id for p in fake.started["participants"]] == ["gpt-a", "gpt-b"]
