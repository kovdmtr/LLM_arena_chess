"""Тесты пост-анализа партии (★, D-009): centipawn loss, классификация, сводка.

Движок подменяется детерминированным ``_FakeEval`` (оценки по FEN), чтобы проверять
именно логику анализа без Stockfish: расчёт cpl и POV (оценка после хода берётся
со знаком минус — у соперника очередь), обработку терминальных позиций без
обращения к движку, эвристику «блестящий» (жертва), агрегацию точности/счётчиков
и ключевых моментов по сторонам, а также деградацию при недоступности движка.
"""

from __future__ import annotations

from datetime import datetime

import chess

from arena.analysis import ClassificationThresholds, analyze_game
from arena.engine import EngineUnavailableError
from arena.models import GameRecord, MoveRecord, PlayerInfo

CREATED_AT = datetime(2026, 6, 9, 12, 0, 0)
THRESHOLDS = ClassificationThresholds(
    inaccuracy_cp=50, mistake_cp=120, blunder_cp=300,
    brilliant_max_cpl=10, brilliant_min_eval_cp=100,
)


class _FakeEval:
    """Фейковый движок: оценка позиции по FEN из словаря (по умолчанию 0)."""

    def __init__(self, evals=None, *, error: bool = False, default: int = 0):
        self.evals = dict(evals or {})
        self.error = error
        self.default = default
        self.calls: list[str] = []

    def evaluate(self, fen: str, *, depth: int | None = None) -> int:
        if self.error:
            raise EngineUnavailableError("движок недоступен")
        self.calls.append(fen)
        return self.evals.get(fen, self.default)


def _pinfo(name: str) -> PlayerInfo:
    return PlayerInfo(model_id=name, provider="fake", display_name=name.upper())


def _game_from_sans(sans):
    """Построить ``GameRecord`` из последовательности SAN (с реальными FEN ходов)."""
    board = chess.Board()
    moves = []
    for i, san in enumerate(sans, start=1):
        fen_before = board.fen()
        move = board.parse_san(san)
        uci = move.uci()
        board.push(move)
        moves.append(
            MoveRecord(
                ply=i,
                side="white" if i % 2 == 1 else "black",
                san=san,
                uci=uci,
                fen_before=fen_before,
                fen_after=board.fen(),
            )
        )
    game = GameRecord(
        id="g1",
        created_at=CREATED_AT,
        players={"white": _pinfo("w"), "black": _pinfo("b")},
        moves=moves,
    )
    return game, board


def _single_move_game(fen: str, san: str):
    """Партия из одного хода из позиции ``fen`` (для эвристики «блестящий»)."""
    board = chess.Board(fen)
    fen_before = board.fen()
    move = board.parse_san(san)
    uci = move.uci()
    side = "white" if board.turn == chess.WHITE else "black"
    board.push(move)
    record = MoveRecord(
        ply=1, side=side, san=san, uci=uci,
        fen_before=fen_before, fen_after=board.fen(),
    )
    game = GameRecord(
        id="s1", created_at=CREATED_AT,
        players={"white": _pinfo("w"), "black": _pinfo("b")},
        moves=[record],
    )
    return game


# --- centipawn loss, POV и классификация ------------------------------------

def test_cpl_computed_from_both_evals_and_classified():
    # e4 e5 Qh5 Nc6; оценки позиций (POV хода) подобраны под известные cpl.
    game, _ = _game_from_sans(["e4", "e5", "Qh5", "Nc6"])
    s0 = game.moves[0].fen_before  # старт (белые)
    s1 = game.moves[1].fen_before  # после e4 (чёрные)
    s2 = game.moves[2].fen_before  # после e5 (белые)
    s3 = game.moves[3].fen_before  # после Qh5 (чёрные)
    s4 = game.moves[3].fen_after   # после Nc6 (белые)
    evals = {s0: 20, s1: 10, s2: 50, s3: 270, s4: -260}
    engine = _FakeEval(evals)

    summary = analyze_game(game, engine, thresholds=THRESHOLDS)

    # cpl(m1)=20+10=30 → normal (просто ход, >good_cp); cpl(m2)=10+50=60 → inaccuracy;
    # cpl(m3)=50+270=320 → blunder; cpl(m4)=270-260=10 → good.
    assert [m.classification for m in game.moves] == [
        "normal", "inaccuracy", "blunder", "good",
    ]
    # Оценка хода хранится с POV белых (для хода чёрных — со знаком минус).
    assert game.moves[0].engine_eval_cp == -10   # -eval(s1)
    assert game.moves[1].engine_eval_cp == 50    # -(-eval(s2))
    assert game.moves[2].engine_eval_cp == -270  # -eval(s3)
    assert summary is not None


def test_summary_aggregates_accuracy_counters_and_key_moments():
    game, _ = _game_from_sans(["e4", "e5", "Qh5", "Nc6"])
    s0 = game.moves[0].fen_before
    s1 = game.moves[1].fen_before
    s2 = game.moves[2].fen_before
    s3 = game.moves[3].fen_before
    s4 = game.moves[3].fen_after
    engine = _FakeEval({s0: 20, s1: 10, s2: 50, s3: 270, s4: -260})

    summary = analyze_game(game, engine, thresholds=THRESHOLDS)

    # белые: normal + blunder → точность 0.5 (normal «точен»), один зевок.
    assert summary.white.accuracy == 0.5
    assert summary.white.blunders == 1
    assert summary.white.mistakes == 0
    # чёрные: inaccuracy + good → точность 0.5, одна неточность.
    assert summary.black.accuracy == 0.5
    assert summary.black.inaccuracies == 1
    # ключевой момент — только зевок белых на 3-м полуходе.
    assert [(k.ply, k.classification) for k in summary.key_moments] == [(3, "blunder")]


def test_negative_cpl_from_search_noise_is_clamped_to_good():
    # Оценка после хода даже лучше «лучшей» (шум) → cpl<0 → 0 → good.
    game = _single_move_game(chess.STARTING_FEN, "e4")
    before = game.moves[0].fen_before
    after = game.moves[0].fen_after
    engine = _FakeEval({before: 10, after: -40})  # eval_mover_after=40, cpl=max(0,-30)=0

    analyze_game(game, engine, thresholds=THRESHOLDS)

    assert game.moves[0].classification == "good"


# --- терминальные позиции ----------------------------------------------------

def test_checkmate_fen_after_is_not_sent_to_engine():
    # Детский мат: последний ход Qh4# даёт терминальный fen_after.
    game, _ = _game_from_sans(["f3", "e5", "g4", "Qh4#"])
    mate_record = game.moves[-1]
    engine = _FakeEval()  # все оценки по умолчанию 0

    analyze_game(game, engine, thresholds=THRESHOLDS)

    # матовый fen_after движку не отдаём (терминальная позиция).
    assert mate_record.fen_after not in engine.calls
    # ход поставил мат → решающая оценка с POV белых отрицательна (выиграли чёрные).
    assert mate_record.engine_eval_cp == -100_000
    assert mate_record.classification == "good"


# --- эвристика «блестящий» (жертва) ------------------------------------------

# Ферзь берёт защищённую пешку d5 — отдаёт ферзя за пешку (жертва).
_SAC_FEN = "3k4/8/2p5/3p4/8/8/3Q4/3K4 w - - 0 1"


def test_best_sacrifice_in_winning_position_is_brilliant():
    game = _single_move_game(_SAC_FEN, "Qxd5")
    before = game.moves[0].fen_before
    after = game.moves[0].fen_after
    # cpl≈0 (лучший ход) и перевес сохраняется (eval_mover_after=160 ≥ 100).
    engine = _FakeEval({before: 150, after: -160})

    analyze_game(game, engine, thresholds=THRESHOLDS)

    assert game.moves[0].classification == "brilliant"


def test_sacrifice_that_is_not_best_is_not_brilliant():
    game = _single_move_game(_SAC_FEN, "Qxd5")
    before = game.moves[0].fen_before
    after = game.moves[0].fen_after
    engine = _FakeEval({before: 150, after: 200})  # cpl=350 → зевок, не блестящий

    analyze_game(game, engine, thresholds=THRESHOLDS)

    assert game.moves[0].classification == "blunder"


def test_best_quiet_move_is_good_not_brilliant():
    # Лучший ход в выигранной позиции, но без жертвы → good, не brilliant.
    game = _single_move_game(chess.STARTING_FEN, "e4")
    before = game.moves[0].fen_before
    after = game.moves[0].fen_after
    engine = _FakeEval({before: 10, after: -150})  # cpl=0, eval_mover_after=150

    analyze_game(game, engine, thresholds=THRESHOLDS)

    assert game.moves[0].classification == "good"


def test_best_sacrifice_in_unclear_position_is_interesting():
    # Та же жертва ферзя, но перевес после хода не дотягивает до порога блестящего
    # (eval в коридоре ±brilliant_min_eval_cp) → «интересный» (!?), а не «блестящий».
    game = _single_move_game(_SAC_FEN, "Qxd5")
    before = game.moves[0].fen_before
    after = game.moves[0].fen_after
    # cpl=max(0, 40-50)=0 (почти лучший), eval_mover_after=50 (< 100 и > -100).
    engine = _FakeEval({before: 40, after: -50})

    analyze_game(game, engine, thresholds=THRESHOLDS)

    assert game.moves[0].classification == "interesting"


# --- деградация без движка (D-008) -------------------------------------------

def test_unavailable_engine_degrades_to_none_without_marking_moves():
    game, _ = _game_from_sans(["e4", "e5"])
    engine = _FakeEval(error=True)

    summary = analyze_game(game, engine, thresholds=THRESHOLDS)

    assert summary is None
    # ходы остаются неразмеченными — артефакты базы валидны (D-008).
    assert all(m.classification is None for m in game.moves)
    assert all(m.engine_eval_cp is None for m in game.moves)


def test_default_thresholds_used_when_none_passed():
    game = _single_move_game(chess.STARTING_FEN, "e4")
    before = game.moves[0].fen_before
    after = game.moves[0].fen_after
    engine = _FakeEval({before: 0, after: 200})  # cpl=200 → ошибка по дефолтным порогам

    summary = analyze_game(game, engine)  # без thresholds → дефолтные

    assert game.moves[0].classification == "mistake"
    assert summary.white.mistakes == 1
