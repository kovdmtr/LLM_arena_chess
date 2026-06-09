"""Тесты жизненного цикла логирования веб-партии + маскирования (Phase 7).

Проверяют, что ``GameManager`` пишет структурные записи о старте/финале/сбое партии
в логгер ``arena`` и что секрет (API-ключ), попавший в текст ошибки, маскируется в
логе (D-003). Логгер ``arena`` изолируется автоюз-фикстурой.
"""

from __future__ import annotations

import io
import logging

import pytest

from arena.models import LLMResponse, PlayerInfo
from arena.obs import ROOT_NAME, clear_secrets, configure_logging
from arena.obs import log as log_module
from arena.web import GameManager

_WHITE_MOVES = ["f3", "g4"]
_BLACK_MOVES = ["e5", "Qh4#"]


class _ScriptedPlayer:
    def __init__(self, info, moves):
        self._info = info
        self._moves = list(moves)

    @property
    def info(self):
        return self._info

    def respond(self, messages):
        return LLMResponse(reasoning="x", move=self._moves.pop(0))


class _BoomPlayer:
    """Игрок, падающий с секретом в тексте ошибки (проверка маскирования трейсбека)."""

    def __init__(self, info, secret):
        self._info = info
        self._secret = secret

    @property
    def info(self):
        return self._info

    def respond(self, messages):
        raise RuntimeError(f"auth failed for {self._secret}")


def _info(side):
    return PlayerInfo(model_id=f"{side}-model", provider="openai", display_name=side)


def _resolved():
    # GameManager.start не обращается к ключам резолва — фабрика возвращает фейка.
    return {"white": _info("white"), "black": _info("black")}


@pytest.fixture(autouse=True)
def _isolate_logger():
    clear_secrets()
    logger = logging.getLogger(ROOT_NAME)
    saved = list(logger.handlers)
    for h in saved:
        logger.removeHandler(h)
    log_module._configured = False
    yield
    clear_secrets()
    for h in list(logger.handlers):
        logger.removeHandler(h)
    log_module._configured = False
    for h in saved:
        logger.addHandler(h)


def test_lifecycle_logs_start_and_finish(tmp_path):
    stream = io.StringIO()
    configure_logging(level="DEBUG", stream=stream, force=True)

    players = {
        "white": _ScriptedPlayer(_info("white"), _WHITE_MOVES),
        "black": _ScriptedPlayer(_info("black"), _BLACK_MOVES),
    }
    manager = GameManager(
        player_factory=lambda side, resolved: players[side],
        games_root=str(tmp_path),
        persist=False,
    )
    session = manager.start(_resolved())
    assert session.join(timeout=5)

    output = stream.getvalue()
    assert "game started" in output
    assert "game finished" in output
    assert f"game_id={session.id}" in output
    assert "result=0-1" in output


def test_failure_log_masks_secret_in_traceback(tmp_path):
    secret = "sk-super-secret-42"
    stream = io.StringIO()
    configure_logging(level="DEBUG", stream=stream, secrets=[secret], force=True)

    boom = lambda side, resolved: _BoomPlayer(_info(side), secret)  # noqa: E731
    manager = GameManager(
        player_factory=boom, games_root=str(tmp_path), persist=False
    )
    session = manager.start(_resolved())
    assert session.join(timeout=5)

    output = stream.getvalue()
    assert "game failed" in output
    assert "RuntimeError" in output  # трейсбек попал в лог
    assert secret not in output  # …но ключ замаскирован
    assert "***" in output
