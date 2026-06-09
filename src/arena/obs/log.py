"""Структурное логирование с маскированием секретов (Phase 7).

Единая точка настройки логов приложения. Две задачи:

1. **Структурный вывод.** ``StructuredFormatter`` пишет записи либо человекочитаемой
   строкой ``ts LEVEL logger: message [k=v …]``, либо JSON-строкой (по одной на запись)
   с полями ``ts``/``level``/``logger``/``message`` + произвольные ``extra``-поля и
   трейсбек исключения. JSON удобен для машинной обработки/грепа.

2. **Маскирование секретов (D-003).** API-ключи не должны попадать в логи. Значения
   секретов регистрируются в глобальном реестре (``register_secret(s)``), и
   форматтер вырезает их из **итоговой** строки (сообщение, аргументы, extra,
   трейсбек) — где бы ключ ни всплыл. Дополняет точечное маскирование в провайдерах
   (``providers.mask_secret``) сквозной защитой на уровне вывода.

Логгеры живут под пространством имён ``arena`` (``get_logger("web")`` →
``arena.web``); ``configure_logging`` настраивает именно его, не трогая корневой
логгер хоста.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from typing import IO, Any

ROOT_NAME = "arena"
REDACTION = "***"

# Глобальный реестр значений секретов — маскируются во всех логах приложения.
_SECRETS: set[str] = set()
_configured = False

# Стандартные атрибуты ``LogRecord`` — всё, что вне этого набора, считаем ``extra``.
_STD_ATTRS = frozenset(
    {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "taskName", "asctime", "message",
    }
)


def register_secret(value: str | None) -> None:
    """Зарегистрировать значение секрета для маскирования в логах.

    Пустые/``None`` значения игнорируются (заготовки в ``.env.example``).
    """
    if value:
        _SECRETS.add(value)


def register_secrets(values: Iterable[str | None]) -> None:
    """Зарегистрировать несколько секретов (см. ``register_secret``)."""
    for value in values:
        register_secret(value)


def clear_secrets() -> None:
    """Очистить реестр секретов (главным образом для изоляции тестов)."""
    _SECRETS.clear()


def redact(text: str) -> str:
    """Вырезать из ``text`` все зарегистрированные секреты, заменив на ``***``.

    Секреты применяются от длинных к коротким, чтобы вложенные подстроки не
    оставляли «хвостов». Пустой реестр — текст без изменений.
    """
    for secret in sorted(_SECRETS, key=len, reverse=True):
        if secret:
            text = text.replace(secret, REDACTION)
    return text


class StructuredFormatter(logging.Formatter):
    """Форматтер: человекочитаемая строка или JSON-строка, всегда с маскированием.

    ``json_format=True`` — JSON-объект на запись; иначе текстовая строка. В обоих
    случаях итог пропускается через ``redact`` (D-003).
    """

    def __init__(self, *, json_format: bool = False) -> None:
        super().__init__()
        self.json_format = json_format

    def _extra(self, record: logging.LogRecord) -> dict[str, Any]:
        return {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STD_ATTRS and not key.startswith("_")
        }

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        extra = self._extra(record)
        exc_text = ""
        if record.exc_info:
            exc_text = self.formatException(record.exc_info)
        elif record.stack_info:
            exc_text = self.formatStack(record.stack_info)

        if self.json_format:
            payload: dict[str, Any] = {
                "ts": self.formatTime(record),
                "level": record.levelname,
                "logger": record.name,
                "message": message,
            }
            payload.update(extra)
            if exc_text:
                payload["exc"] = exc_text
            rendered = json.dumps(payload, ensure_ascii=False, default=str)
        else:
            parts = [
                f"{self.formatTime(record)} {record.levelname} {record.name}: {message}"
            ]
            for key, value in extra.items():
                parts.append(f"{key}={value}")
            rendered = " ".join(parts)
            if exc_text:
                rendered = f"{rendered}\n{exc_text}"

        return redact(rendered)


def configure_logging(
    *,
    level: int | str = "INFO",
    json_format: bool = False,
    stream: IO[str] | None = None,
    secrets: Iterable[str | None] | None = None,
    force: bool = False,
) -> logging.Logger:
    """Настроить логгер ``arena``: один handler + ``StructuredFormatter``.

    Идемпотентна: повторный вызов без ``force`` лишь обновляет уровень и
    регистрирует переданные ``secrets`` (handler не дублируется). ``force=True``
    пересобирает handler (например, чтобы сменить ``json_format``/поток). Логгер
    не пропагирует в корневой (``propagate=False``), чтобы не дублировать вывод и
    не зависеть от настроек хоста.
    """
    global _configured
    logger = logging.getLogger(ROOT_NAME)
    logger.setLevel(level)
    logger.propagate = False

    if secrets is not None:
        register_secrets(secrets)

    if _configured and not force:
        return logger

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    handler = logging.StreamHandler(stream)
    handler.setFormatter(StructuredFormatter(json_format=json_format))
    logger.addHandler(handler)
    _configured = True
    return logger


def get_logger(name: str = "") -> logging.Logger:
    """Вернуть логгер под пространством имён ``arena`` (``get_logger("web")`` → ``arena.web``)."""
    return logging.getLogger(f"{ROOT_NAME}.{name}" if name else ROOT_NAME)


# Стандартный приём библиотеки: NullHandler на корне пакета — пока приложение не
# вызвало ``configure_logging``, записи никуда не выводятся (нет «No handlers» и
# мусора в stderr). ``configure_logging`` снимает все handler'ы и ставит реальный.
logging.getLogger(ROOT_NAME).addHandler(logging.NullHandler())
