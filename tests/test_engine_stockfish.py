"""★ Тесты UCI-обёртки Stockfish (D-008).

Логика разбора оценок проверяется на **фейковом** движке (без бинарника):
извлечение лучшего хода, знак оценки с точки зрения ходящей стороны (``.relative``,
а не ``.white()``), обработка мата, жизненный цикл процесса и деградация
``EngineUnavailableError``. Отдельный интеграционный тест запускает реальный
Stockfish и **пропускается**, если бинарника нет в PATH (как требует CLAUDE.md).
"""

import shutil

import chess
import chess.engine
import pytest

import os

from arena.engine import (
    DEFAULT_DEPTH,
    EngineUnavailableError,
    StockfishEngine,
)
from arena.engine.stockfish import _resolve_launch_path
from arena.models import HintRecord

_START_FEN = chess.STARTING_FEN


class _FakeEngine:
    """Минимальный движок-заглушка: возвращает заранее заданный ``InfoDict``."""

    def __init__(self, info):
        self._info = info
        self.analysed: list[tuple[str, int | None]] = []
        self.quit_calls = 0

    def analyse(self, board, limit, **_kwargs):
        self.analysed.append((board.fen(), limit.depth))
        return self._info

    def quit(self):
        self.quit_calls += 1


def _info(score, *, pv=("e2e4",)):
    """Собрать ``InfoDict`` с оценкой ``score`` и главной линией ``pv``."""
    return {
        "score": score,
        "pv": [chess.Move.from_uci(uci) for uci in pv],
    }


def _engine(info, *, counter=None):
    """``StockfishEngine`` поверх фейкового движка с заданным ``info``."""
    fake = _FakeEngine(info)

    def opener():
        if counter is not None:
            counter.append(1)
        return fake

    return StockfishEngine(opener=opener), fake


# --- best_move --------------------------------------------------------------


def test_best_move_returns_hint_record_with_uci_and_eval():
    score = chess.engine.PovScore(chess.engine.Cp(30), chess.WHITE)
    engine, _ = _engine(_info(score, pv=("e2e4", "e7e5")))

    hint = engine.best_move(_START_FEN)

    assert isinstance(hint, HintRecord)
    assert hint.best_move == "e2e4"  # первый ход главной линии
    assert hint.eval_cp == 30
    assert hint.mate_in is None


def test_best_move_uses_side_to_move_perspective():
    # Оценка относительно ходящей стороны (.relative), не относительно белых.
    # Для чёрных .relative = +50, а .white() было бы -50 — берём первое.
    score = chess.engine.PovScore(chess.engine.Cp(50), chess.BLACK)
    engine, _ = _engine(_info(score))

    assert engine.best_move(_START_FEN).eval_cp == 50


def test_best_move_reports_mate_instead_of_cp():
    score = chess.engine.PovScore(chess.engine.Mate(3), chess.WHITE)
    engine, _ = _engine(_info(score))

    hint = engine.best_move(_START_FEN)
    assert hint.eval_cp is None  # при мате сантипешек нет
    assert hint.mate_in == 3


def test_best_move_without_pv_raises():
    score = chess.engine.PovScore(chess.engine.Cp(0), chess.WHITE)
    engine, _ = _engine(_info(score, pv=()))
    with pytest.raises(EngineUnavailableError):
        engine.best_move(_START_FEN)


# --- evaluate ---------------------------------------------------------------


def test_evaluate_returns_centipawns_from_side_to_move():
    score = chess.engine.PovScore(chess.engine.Cp(-120), chess.WHITE)
    engine, _ = _engine(_info(score))
    assert engine.evaluate(_START_FEN) == -120


def test_evaluate_maps_mate_to_large_finite_score():
    score = chess.engine.PovScore(chess.engine.Mate(2), chess.WHITE)
    engine, _ = _engine(_info(score))
    value = engine.evaluate(_START_FEN)
    assert isinstance(value, int)
    assert value > 90_000  # мат сведён к большому конечному значению


def test_evaluate_negative_mate_is_large_negative():
    score = chess.engine.PovScore(chess.engine.Mate(-1), chess.WHITE)
    engine, _ = _engine(_info(score))
    assert engine.evaluate(_START_FEN) < -90_000


# --- глубина и параметры ----------------------------------------------------


def test_default_depth_is_used_when_not_overridden():
    score = chess.engine.PovScore(chess.engine.Cp(0), chess.WHITE)
    engine, fake = _engine(_info(score))
    engine.evaluate(_START_FEN)
    assert fake.analysed[-1][1] == DEFAULT_DEPTH


def test_explicit_depth_overrides_default():
    score = chess.engine.PovScore(chess.engine.Cp(0), chess.WHITE)
    engine, fake = _engine(_info(score))
    engine.best_move(_START_FEN, depth=5)
    assert fake.analysed[-1][1] == 5


# --- жизненный цикл процесса ------------------------------------------------


def test_engine_opens_lazily_once():
    score = chess.engine.PovScore(chess.engine.Cp(0), chess.WHITE)
    counter: list[int] = []
    engine, _ = _engine(_info(score), counter=counter)

    engine.evaluate(_START_FEN)
    engine.evaluate(_START_FEN)
    assert sum(counter) == 1  # процесс запущен один раз на оба обращения


def test_close_quits_process_and_is_idempotent():
    score = chess.engine.PovScore(chess.engine.Cp(0), chess.WHITE)
    engine, fake = _engine(_info(score))
    engine.evaluate(_START_FEN)
    engine.close()
    engine.close()  # повторный close не падает
    assert fake.quit_calls == 1


def test_context_manager_opens_and_closes():
    score = chess.engine.PovScore(chess.engine.Cp(0), chess.WHITE)
    counter: list[int] = []
    engine, fake = _engine(_info(score), counter=counter)

    with engine as ctx:
        ctx.evaluate(_START_FEN)
    assert sum(counter) == 1
    assert fake.quit_calls == 1


def test_reopen_after_close_starts_new_process():
    score = chess.engine.PovScore(chess.engine.Cp(0), chess.WHITE)
    counter: list[int] = []
    engine, _ = _engine(_info(score), counter=counter)

    engine.evaluate(_START_FEN)
    engine.close()
    engine.evaluate(_START_FEN)
    assert sum(counter) == 2  # после close процесс запускается заново


# --- деградация без бинарника -----------------------------------------------


def test_missing_binary_raises_engine_unavailable():
    def opener():
        raise FileNotFoundError("stockfish: no such file")

    engine = StockfishEngine(path="definitely-not-stockfish", opener=opener)
    with pytest.raises(EngineUnavailableError):
        engine.open()


def test_engine_error_on_launch_raises_engine_unavailable():
    def opener():
        raise chess.engine.EngineError("handshake failed")

    engine = StockfishEngine(opener=opener)
    with pytest.raises(EngineUnavailableError):
        engine.evaluate(_START_FEN)


# --- разрешение пути запуска --------------------------------------------------

def test_resolve_launch_path_keeps_bare_name_for_path_lookup():
    # bare-имя без разделителей ищется в PATH — не трогаем.
    assert _resolve_launch_path("stockfish") == "stockfish"
    assert _resolve_launch_path("stockfish.exe") == "stockfish.exe"


def test_resolve_launch_path_makes_relative_file_absolute():
    # путь с разделителем делаем абсолютным (Windows не запускает относительный с /).
    resolved = _resolve_launch_path("tools/bin/stockfish.exe")
    assert os.path.isabs(resolved)
    assert resolved.replace("\\", "/").endswith("tools/bin/stockfish.exe")


def test_resolve_launch_path_keeps_absolute_absolute():
    abs_path = os.path.abspath("tools/bin/stockfish.exe")
    assert _resolve_launch_path(abs_path) == os.path.abspath(abs_path)


# --- интеграция с реальным Stockfish (skip, если бинарника нет) --------------


@pytest.mark.skipif(
    shutil.which("stockfish") is None,
    reason="бинарник Stockfish не найден в PATH",
)
def test_real_stockfish_best_move_and_evaluate():
    with StockfishEngine(depth=8) as engine:
        hint = engine.best_move(_START_FEN)
        # Лучший ход стартовой позиции — легальный ход в UCI.
        assert chess.Move.from_uci(hint.best_move) in chess.Board().legal_moves
        # Старт примерно равен — оценка близка к нулю и это целое число.
        assert isinstance(engine.evaluate(_START_FEN), int)
