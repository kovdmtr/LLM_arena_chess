"""Тесты структурного логирования и маскирования секретов (Phase 7).

Реестр секретов глобален, поэтому каждый тест изолируется автоюз-фикстурой
``_isolate`` (очистка реестра + снятие handler'ов логгера ``arena``).
"""

from __future__ import annotations

import io
import json
import logging

import pytest

from arena.config import ModelParams, ResolvedModel
from arena.obs import (
    ROOT_NAME,
    StructuredFormatter,
    clear_secrets,
    configure_logging,
    get_logger,
    redact,
    register_secret,
    register_secrets,
)
from arena.obs import log as log_module
from arena.providers import OpenAIProvider


@pytest.fixture(autouse=True)
def _isolate():
    clear_secrets()
    logger = logging.getLogger(ROOT_NAME)
    saved = list(logger.handlers)
    for handler in saved:
        logger.removeHandler(handler)
    log_module._configured = False
    yield
    clear_secrets()
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    log_module._configured = False
    for handler in saved:
        logger.addHandler(handler)


# --- redact -------------------------------------------------------------------

def test_redact_masks_registered_secret():
    register_secret("sk-secret-123")
    assert redact("key=sk-secret-123 done") == "key=*** done"


def test_redact_noop_without_secrets():
    assert redact("nothing to hide") == "nothing to hide"


def test_redact_ignores_empty_values():
    register_secret("")
    register_secret(None)
    assert redact("plain text") == "plain text"


def test_redact_handles_overlapping_secrets():
    # Длинный секрет вырезается раньше короткого — не остаётся «хвостов».
    register_secrets(["abc", "abcdef"])
    assert redact("x abcdef y") == "x *** y"


# --- StructuredFormatter ------------------------------------------------------

def _record(msg, *, level=logging.INFO, name="arena.test", args=(), **extra):
    record = logging.LogRecord(
        name=name, level=level, pathname=__file__, lineno=1,
        msg=msg, args=args, exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_text_format_includes_fields_and_extras():
    fmt = StructuredFormatter(json_format=False)
    out = fmt.format(_record("hello %s", args=("world",), game_id="g1"))
    assert "INFO" in out
    assert "arena.test" in out
    assert "hello world" in out
    assert "game_id=g1" in out


def test_text_format_masks_secret_in_message_and_extra():
    register_secret("sk-zzz")
    fmt = StructuredFormatter(json_format=False)
    out = fmt.format(_record("using sk-zzz", token="sk-zzz"))
    assert "sk-zzz" not in out
    assert "***" in out


def test_json_format_is_valid_and_structured():
    fmt = StructuredFormatter(json_format=True)
    out = fmt.format(_record("move played", move="e4", game_id="g1"))
    payload = json.loads(out)
    assert payload["level"] == "INFO"
    assert payload["logger"] == "arena.test"
    assert payload["message"] == "move played"
    assert payload["move"] == "e4"
    assert payload["game_id"] == "g1"
    assert "ts" in payload


def test_json_format_masks_secret():
    register_secret("sk-zzz")
    fmt = StructuredFormatter(json_format=True)
    out = fmt.format(_record("auth", api_key="sk-zzz"))
    assert "sk-zzz" not in out
    payload = json.loads(out)
    assert payload["api_key"] == "***"


def test_format_includes_and_masks_exception():
    register_secret("sk-zzz")
    fmt = StructuredFormatter(json_format=True)
    try:
        raise RuntimeError("failed with sk-zzz inside")
    except RuntimeError:
        import sys

        record = logging.LogRecord(
            name="arena.test", level=logging.ERROR, pathname=__file__,
            lineno=1, msg="boom", args=(), exc_info=sys.exc_info(),
        )
    out = fmt.format(record)
    assert "sk-zzz" not in out
    payload = json.loads(out)
    assert "RuntimeError" in payload["exc"]


# --- configure_logging / get_logger -------------------------------------------

def test_configure_logging_writes_to_stream_and_masks():
    stream = io.StringIO()
    configure_logging(level="DEBUG", stream=stream, secrets=["sk-zzz"], force=True)
    get_logger("web").info("connecting with sk-zzz", extra={"game_id": "g9"})
    output = stream.getvalue()
    assert "sk-zzz" not in output
    assert "game_id=g9" in output
    assert "arena.web" in output


def test_configure_logging_is_idempotent():
    stream = io.StringIO()
    logger = configure_logging(stream=stream, force=True)
    assert len(logger.handlers) == 1
    configure_logging(stream=stream)  # без force — handler не дублируется
    assert len(logger.handlers) == 1


def test_configure_logging_force_switches_json():
    stream = io.StringIO()
    configure_logging(stream=stream, json_format=True, force=True)
    get_logger("x").warning("hi", extra={"k": "v"})
    payload = json.loads(stream.getvalue().strip())
    assert payload["level"] == "WARNING"
    assert payload["k"] == "v"


def test_get_logger_namespaces_under_arena():
    assert get_logger().name == "arena"
    assert get_logger("engine").name == "arena.engine"


def test_logger_does_not_propagate():
    logger = configure_logging(force=True)
    assert logger.propagate is False


# --- интеграция: провайдер регистрирует свой ключ -----------------------------

def test_provider_construction_registers_key_for_masking():
    OpenAIProvider(
        ResolvedModel(
            id="gpt-4o", provider="openai", display_name="GPT-4o",
            params=ModelParams(), api_key_env="OPENAI_API_KEY",
            api_key="sk-provider-key-xyz",
        )
    )
    assert redact("token sk-provider-key-xyz end") == "token *** end"
