"""Повтор вызова провайдера при временных сбоях (Phase 7).

LLM-API периодически отвечают временными ошибками: rate-limit (429), таймаут,
обрыв соединения, перегрузка/5xx. Такие сбои разумно повторить с экспоненциальной
задержкой (backoff), а постоянные (неверный ключ, 400/404, ошибка валидации) —
нет. Этот модуль даёт:

- ``is_transient_error`` — эвристика «стоит ли повторять» по типу/сообщению/коду
  статуса исключения, без жёсткой зависимости от классов конкретных SDK;
- ``call_with_retry`` — обёртка, исполняющая функцию с повторами по ``RetryConfig``.

Задержка детерминируема при ``jitter=0`` и инъекции ``sleep``/``rng`` — это делает
поведение проверяемым в тестах без реальных пауз и случайности.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

from arena.config.settings import RetryConfig

T = TypeVar("T")

# Подстроки в имени класса/тексте ошибки, указывающие на временный сбой.
_TRANSIENT_MARKERS = (
    "rate limit",
    "ratelimit",
    "rate_limit",
    "too many requests",
    "timeout",
    "timed out",
    "temporar",
    "overloaded",
    "unavailable",
    "connection",
    "connect error",
    "reset by peer",
    "try again",
    "service unavailable",
    "internal server error",
    "bad gateway",
    "gateway timeout",
)

# HTTP-коды, которые считаем временными (429 + 5xx-серия).
_TRANSIENT_STATUS = frozenset({429, 500, 502, 503, 504})


def is_transient_error(exc: BaseException) -> bool:
    """Похоже ли ``exc`` на временный сбой, который имеет смысл повторить.

    Эвристика (объединение признаков, без импорта классов SDK):

    1. Числовой ``status_code``/``code`` исключения ∈ {429, 5xx}.
    2. Имя класса или текст сообщения содержит маркер из ``_TRANSIENT_MARKERS``.

    Постоянные ошибки (неверный ключ, 400/404, ``ValueError`` бизнес-логики) под
    эвристику не попадают и не повторяются.
    """
    status = getattr(exc, "status_code", None)
    if not isinstance(status, int):
        status = getattr(exc, "status", None)
    if not isinstance(status, int):
        code = getattr(exc, "code", None)
        status = code if isinstance(code, int) else None
    if isinstance(status, int) and status in _TRANSIENT_STATUS:
        return True

    haystack = f"{type(exc).__name__} {exc}".lower()
    return any(marker in haystack for marker in _TRANSIENT_MARKERS)


def _backoff_delay(config: RetryConfig, attempt: int, rng: random.Random) -> float:
    """Задержка перед попыткой ``attempt`` (1-индексной): экспонента + jitter, clamp.

    ``base_delay * multiplier**(attempt-1)``, не выше ``max_delay``; затем
    размывается в ``[base*(1-jitter), base*(1+jitter)]``. При ``jitter=0`` —
    детерминирована.
    """
    raw = config.base_delay * (config.multiplier ** (attempt - 1))
    capped = min(raw, config.max_delay)
    if config.jitter:
        factor = 1.0 + config.jitter * (2.0 * rng.random() - 1.0)
        capped *= factor
    return max(0.0, capped)


def call_with_retry(
    fn: Callable[[], T],
    config: RetryConfig,
    *,
    sleep: Callable[[float], None] = time.sleep,
    is_transient: Callable[[BaseException], bool] = is_transient_error,
    rng: random.Random | None = None,
) -> T:
    """Выполнить ``fn`` с повторами по политике ``config``.

    Повторяет только при «временной» ошибке (``is_transient``) и пока не исчерпаны
    ``config.attempts`` попыток; между попытками вызывает ``sleep(delay)`` с
    backoff (``_backoff_delay``). Постоянную ошибку или последнюю попытку
    пробрасывает наружу без изменений (вызывающий слой обернёт её в
    ``ProviderError``). ``sleep``/``rng`` инъектируются для детерминизма в тестах.
    """
    if rng is None:
        rng = random  # type: ignore[assignment]
    attempt = 0
    while True:
        attempt += 1
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — решение о повторе по эвристике
            if attempt >= config.attempts or not is_transient(exc):
                raise
            sleep(_backoff_delay(config, attempt, rng))  # type: ignore[arg-type]
