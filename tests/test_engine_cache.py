"""Тесты кеша оценок позиций ``CachingEngine`` (Phase 8, бэклог-3).

Внутренний движок — счётчик вызовов: проверяем, что повтор по ``(fen, depth)``
не доходит до движка, что разная глубина кешируется отдельно, что результат
идентичен и что жизненный цикл (close/контекстный менеджер) делегируется.
"""

from __future__ import annotations

from arena.config import EngineConfig
from arena.engine import CachingEngine, build_engine
from arena.models import HintRecord


class _CountingEngine:
    """Движок-заглушка: считает обращения; eval = длина FEN, ход фиксирован."""

    def __init__(self):
        self.eval_calls = 0
        self.move_calls = 0
        self.closed = False
        self.opened = 0

    def open(self):
        self.opened += 1
        return self

    def evaluate(self, fen, *, depth=None):
        self.eval_calls += 1
        return len(fen) + (depth or 0)

    def best_move(self, fen, *, depth=None):
        self.move_calls += 1
        return HintRecord(best_move="e2e4", eval_cp=10, mate_in=None)

    def close(self):
        self.closed = True


def test_evaluate_is_cached_per_fen_and_depth():
    inner = _CountingEngine()
    engine = CachingEngine(inner)

    first = engine.evaluate("FEN-A", depth=10)
    second = engine.evaluate("FEN-A", depth=10)
    assert first == second
    assert inner.eval_calls == 1  # второй раз — из кеша
    assert engine.hits == 1
    assert engine.misses == 1


def test_different_depth_is_separate_entry():
    inner = _CountingEngine()
    engine = CachingEngine(inner)

    engine.evaluate("FEN-A", depth=10)
    engine.evaluate("FEN-A", depth=20)  # другая глубина → промах
    assert inner.eval_calls == 2
    assert engine.cache_info["eval_entries"] == 2


def test_best_move_is_cached():
    inner = _CountingEngine()
    engine = CachingEngine(inner)

    a = engine.best_move("FEN-A")
    b = engine.best_move("FEN-A")
    assert a == b
    assert inner.move_calls == 1


def test_clear_cache_resets_entries_and_counters():
    inner = _CountingEngine()
    engine = CachingEngine(inner)
    engine.evaluate("FEN-A")
    engine.evaluate("FEN-A")
    engine.clear_cache()

    assert engine.cache_info == {
        "hits": 0, "misses": 0, "eval_entries": 0, "move_entries": 0
    }
    engine.evaluate("FEN-A")
    assert inner.eval_calls == 2  # после очистки снова обращается к движку


def test_lifecycle_delegates_to_inner():
    inner = _CountingEngine()
    with CachingEngine(inner) as engine:
        assert inner.opened == 1
        engine.evaluate("FEN-A")
    assert inner.closed  # close проброшен на выходе из контекста


def test_build_engine_wraps_in_cache_when_requested():
    cfg = EngineConfig(enabled=True)

    class _FakeUci:
        def quit(self):
            pass

    engine = build_engine(cfg, cache=True, opener=lambda: _FakeUci())
    assert isinstance(engine, CachingEngine)
    engine.close()


def test_build_engine_without_cache_returns_plain_engine():
    cfg = EngineConfig(enabled=True)

    class _FakeUci:
        def quit(self):
            pass

    engine = build_engine(cfg, opener=lambda: _FakeUci())
    assert not isinstance(engine, CachingEngine)
    engine.close()
