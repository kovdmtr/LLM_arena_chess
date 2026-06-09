"""Тесты единого пути включения движка ``build_engine`` (Phase 7, D-008).

``build_engine`` — единственная точка решения «★ включены / выключены»: конфиг с
``enabled=false`` или недоступный бинарник дают ``None`` (без исключений у
вызывающего), иначе — открытый ``StockfishEngine``. UCI-процесс подменяется
фейковым ``opener``.
"""

from __future__ import annotations

import chess

from arena.config import EngineConfig
from arena.engine import build_engine


class _FakeUci:
    """Фейковый UCI-движок: достаточно ``quit`` для жизненного цикла."""

    def __init__(self):
        self.quit_called = False

    def quit(self):
        self.quit_called = True


def test_disabled_config_returns_none():
    cfg = EngineConfig(enabled=False)
    assert build_engine(cfg, opener=lambda: _FakeUci()) is None


def test_unavailable_binary_returns_none():
    def boom_opener():
        raise FileNotFoundError("stockfish not found")

    cfg = EngineConfig(enabled=True, path="missing")
    assert build_engine(cfg, opener=boom_opener) is None


def test_engine_error_returns_none():
    def boom_opener():
        raise chess.engine.EngineError("handshake failed")

    cfg = EngineConfig(enabled=True)
    assert build_engine(cfg, opener=boom_opener) is None


def test_enabled_returns_open_engine():
    fake = _FakeUci()
    cfg = EngineConfig(enabled=True, hint_depth=12)
    engine = build_engine(cfg, opener=lambda: fake)
    assert engine is not None
    assert engine._engine is fake  # процесс уже поднят
    assert engine.depth == 12  # глубина по умолчанию = hint_depth
    engine.close()
    assert fake.quit_called


def test_explicit_depth_overrides_hint_depth():
    cfg = EngineConfig(enabled=True, hint_depth=12, analysis_depth=20)
    engine = build_engine(cfg, depth=20, opener=lambda: _FakeUci())
    assert engine is not None
    assert engine.depth == 20
