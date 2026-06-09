"""Тесты политики повторов провайдеров (Phase 7).

Покрывают три уровня:

1. ``is_transient_error`` — классификация «повторять / не повторять».
2. ``call_with_retry`` — само поведение повторов и backoff (с инъекцией
   ``sleep``/``rng`` — без реальных пауз и случайности).
3. Интеграция: ``OpenAIProvider`` с фейковым клиентом, который временно падает —
   проверяем, что ``complete`` повторяет и в итоге возвращает ответ, а при
   исчерпании попыток оборачивает ошибку в ``ProviderError``.
"""

from __future__ import annotations

import random
from types import SimpleNamespace

import pytest

from arena.config import ModelParams, ResolvedModel, RetryConfig
from arena.models import MessageRecord
from arena.providers import (
    OpenAIProvider,
    ProviderError,
    call_with_retry,
    is_transient_error,
)


# --- is_transient_error -------------------------------------------------------

class _StatusError(Exception):
    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


@pytest.mark.parametrize(
    "exc",
    [
        RuntimeError("Rate limit exceeded, please retry"),
        RuntimeError("Request timed out"),
        RuntimeError("connection reset by peer"),
        RuntimeError("The model is overloaded"),
        RuntimeError("503 Service Unavailable"),
        _StatusError("boom", 429),
        _StatusError("boom", 500),
        _StatusError("boom", 503),
        type("APITimeoutError", (Exception,), {})("nope"),
    ],
)
def test_transient_errors_detected(exc):
    assert is_transient_error(exc) is True


@pytest.mark.parametrize(
    "exc",
    [
        ValueError("illegal move 'Zz9'"),
        RuntimeError("invalid api key"),
        _StatusError("bad request", 400),
        _StatusError("not found", 404),
        KeyError("missing field"),
    ],
)
def test_permanent_errors_not_retried(exc):
    assert is_transient_error(exc) is False


# --- call_with_retry ----------------------------------------------------------

def _recorder():
    """Список пауз + функция ``sleep``, которая их фиксирует (без реальных задержек)."""
    delays: list[float] = []
    return delays, delays.append


def test_returns_on_first_success():
    delays, sleep = _recorder()
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        return "ok"

    out = call_with_retry(fn, RetryConfig(attempts=3), sleep=sleep)
    assert out == "ok"
    assert calls["n"] == 1
    assert delays == []  # успех с первого раза — пауз нет


def test_retries_transient_then_succeeds():
    delays, sleep = _recorder()
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("rate limit")
        return "ok"

    out = call_with_retry(
        fn, RetryConfig(attempts=5, base_delay=1.0, multiplier=2.0, jitter=0.0), sleep=sleep
    )
    assert out == "ok"
    assert calls["n"] == 3
    assert delays == [1.0, 2.0]  # две паузы перед 2-й и 3-й попыткой


def test_permanent_error_not_retried():
    delays, sleep = _recorder()
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise ValueError("bad request")

    with pytest.raises(ValueError):
        call_with_retry(fn, RetryConfig(attempts=5), sleep=sleep)
    assert calls["n"] == 1  # постоянную ошибку не повторяем
    assert delays == []


def test_exhausts_attempts_then_raises_last():
    delays, sleep = _recorder()
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise RuntimeError(f"timeout #{calls['n']}")

    with pytest.raises(RuntimeError, match="timeout #3"):
        call_with_retry(fn, RetryConfig(attempts=3, base_delay=1.0, jitter=0.0), sleep=sleep)
    assert calls["n"] == 3
    assert len(delays) == 2  # attempts-1 пауз


def test_backoff_is_capped_at_max_delay():
    delays, sleep = _recorder()
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise RuntimeError("overloaded")

    with pytest.raises(RuntimeError):
        call_with_retry(
            fn,
            RetryConfig(attempts=5, base_delay=1.0, multiplier=2.0, max_delay=5.0, jitter=0.0),
            sleep=sleep,
        )
    # 1, 2, 4, затем clamp 8→5
    assert delays == [1.0, 2.0, 4.0, 5.0]


def test_jitter_keeps_delay_within_bounds():
    delays, sleep = _recorder()
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise RuntimeError("connection error")

    rng = random.Random(0)
    with pytest.raises(RuntimeError):
        call_with_retry(
            fn,
            RetryConfig(attempts=3, base_delay=1.0, multiplier=1.0, jitter=0.5),
            sleep=sleep,
            rng=rng,
        )
    # base=1, multiplier=1 → база 1.0 на каждой; jitter 0.5 → [0.5, 1.5]
    assert len(delays) == 2
    assert all(0.5 <= d <= 1.5 for d in delays)


# --- RetryConfig валидация ----------------------------------------------------

@pytest.mark.parametrize(
    "kwargs",
    [
        {"attempts": 0},
        {"multiplier": 0.5},
        {"jitter": 1.5},
        {"jitter": -0.1},
        {"base_delay": -1.0},
    ],
)
def test_retry_config_rejects_bad_values(kwargs):
    with pytest.raises(ValueError):
        RetryConfig(**kwargs)


# --- интеграция с провайдером -------------------------------------------------

API_KEY = "sk-secret-retry-1"


def _model() -> ResolvedModel:
    return ResolvedModel(
        id="gpt-4o",
        provider="openai",
        display_name="GPT-4o",
        params=ModelParams(temperature=0.2, max_tokens=64),
        api_key_env="OPENAI_API_KEY",
        api_key=API_KEY,
    )


def _text_response(content):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


class _FlakyClient:
    """Фейковый OpenAI-клиент: первые ``fail`` вызовов падают временной ошибкой."""

    def __init__(self, *, fail, response, error):
        self.calls = 0
        self._fail = fail
        self._response = response
        self._error = error
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=self._create)
        )

    def _create(self, **kwargs):
        self.calls += 1
        if self.calls <= self._fail:
            raise self._error
        return self._response


def _msgs():
    return [MessageRecord(role="user", content="your move")]


def test_provider_retries_transient_and_succeeds(monkeypatch):
    client = _FlakyClient(
        fail=2, response=_text_response("Nf3"), error=RuntimeError("rate limit")
    )
    # base_delay=0 → паузы мгновенны; реальный sleep не вызываем по сути.
    provider = OpenAIProvider(
        _model(), retry=RetryConfig(attempts=3, base_delay=0.0, jitter=0.0)
    )
    monkeypatch.setattr(provider, "_ensure_client", lambda: client)

    out = provider.complete(_msgs(), provider.model.params)
    assert out == "Nf3"
    assert client.calls == 3  # 2 падения + успех


def test_provider_wraps_error_after_exhaustion(monkeypatch):
    client = _FlakyClient(
        fail=99, response=_text_response("x"), error=RuntimeError("rate limit")
    )
    provider = OpenAIProvider(
        _model(), retry=RetryConfig(attempts=2, base_delay=0.0, jitter=0.0)
    )
    monkeypatch.setattr(provider, "_ensure_client", lambda: client)

    with pytest.raises(ProviderError) as ei:
        provider.complete(_msgs(), provider.model.params)
    assert client.calls == 2  # исчерпали попытки
    assert API_KEY not in str(ei.value)  # ключ не утёк в сообщение
