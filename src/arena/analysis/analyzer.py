"""★ Пост-анализ партии: centipawn loss, классификация ходов, сводка (D-009).

``analyze_game`` проходит по ходам ``GameRecord``, для каждого считает оценку
позиции движком и centipawn loss относительно лучшего хода, проставляет в
``MoveRecord`` оценку (``engine_eval_cp``, POV белых — как у eval-бара) и класс
(``classification``), и собирает ``AnalysisSummary`` (точность и счётчики ошибок
по сторонам + ключевые моменты).

Centipawn loss считается из двух оценок (обе — POV стороны, которая ходит в
позиции, так отдаёт ``StockfishEngine.evaluate``):

- ``best = evaluate(fen_before)`` — лучшее, чего могла достичь ходившая сторона;
- ``after = evaluate(fen_after)`` — позиция после хода, но POV там у **соперника**,
  поэтому оценка ходившей стороны = ``-after``;
- ``cpl = max(0, best - (-after)) = max(0, best + after)``.

Терминальные позиции (``fen_after`` — мат/пат/ничья) движку не отдаются: мат в
пользу ходившей стороны → решающая оценка, пат/ничья → 0.

Класс ``brilliant`` — эвристика поверх классификации (D-009): ход почти лучший
(``cpl ≤ brilliant_max_cpl``), сторона сохраняет перевес (``≥ brilliant_min_eval_cp``)
и при этом жертвует материал (см. ``_is_sacrifice``).

Движок опционален (D-008): при ``EngineUnavailableError`` анализ деградирует —
``analyze_game`` возвращает ``None``, поля ходов остаются ``None`` (партия не
размечается, но артефакты базы валидны).
"""

from __future__ import annotations

from typing import Protocol

import chess

from arena.analysis.classify import ClassificationThresholds, classify_cpl
from arena.engine import EngineUnavailableError
from arena.models import (
    AnalysisSummary,
    Classification,
    GameRecord,
    KeyMoment,
    MoveRecord,
    PlayerAnalysis,
    Side,
)

# Конечная оценка форсированного мата (как в ``engine.stockfish``): мат строго
# лучше/хуже любой материальной оценки.
_MATE_SCORE = 100_000

# Ценность фигур для эвристики жертвы (сантипешки). Король «дорогой», чтобы не
# считаться дешёвым атакующим при взятии защищённой фигуры (взятие было бы нелегально).
_PIECE_VALUE: dict[int, int] = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: _MATE_SCORE,
}

# Классы, считающиеся «точными» при расчёте accuracy (не ухудшают позицию).
_ACCURATE: frozenset[Classification] = frozenset(
    {"good", "brilliant", "interesting", "normal", "book"}
)

# Классы, попадающие в ключевые моменты партии.
_KEY_CLASSES: frozenset[Classification] = frozenset({"brilliant", "mistake", "blunder"})


class EvalEngine(Protocol):
    """Минимальный контракт движка для пост-анализа: оценка позиции по FEN."""

    def evaluate(self, fen: str, *, depth: int | None = None) -> int: ...


def analyze_game(
    game: GameRecord,
    engine: EvalEngine,
    *,
    thresholds: ClassificationThresholds | None = None,
    depth: int | None = None,
) -> AnalysisSummary | None:
    """Разметить ходы партии и собрать ``AnalysisSummary`` (D-009).

    Проставляет в каждый ``MoveRecord`` оценку (``engine_eval_cp``) и класс
    (``classification``), возвращает сводку по сторонам и ключевые моменты. При
    недоступности движка (``EngineUnavailableError``) — деградация: возвращает
    ``None``, ходы остаются неразмеченными (D-008).
    """
    thresholds = thresholds or ClassificationThresholds()
    try:
        # Сначала считаем всё (движок может упасть), потом мутируем записи — чтобы
        # при деградации не оставить ходы размеченными наполовину.
        graded = [
            (record, *_analyze_move(record, engine, thresholds, depth))
            for record in game.moves
        ]
    except EngineUnavailableError:
        return None

    tally: dict[Side, _SideTally] = {"white": _SideTally(), "black": _SideTally()}
    key_moments: list[KeyMoment] = []
    for record, classification, eval_white in graded:
        record.engine_eval_cp = eval_white
        record.classification = classification
        tally[record.side].add(classification)
        if classification in _KEY_CLASSES:
            key_moments.append(
                KeyMoment(ply=record.ply, classification=classification)
            )

    return AnalysisSummary(
        white=tally["white"].summary(),
        black=tally["black"].summary(),
        key_moments=key_moments,
    )


def _analyze_move(
    record: MoveRecord,
    engine: EvalEngine,
    thresholds: ClassificationThresholds,
    depth: int | None,
) -> tuple[Classification, int]:
    """Оценить один ход: вернуть ``(класс, оценку POV белых)``.

    ``best`` берётся из ``fen_before`` (POV ходившей стороны); оценка после хода —
    из ``fen_after`` (POV соперника, поэтому со знаком минус), с обработкой
    терминальных позиций без обращения к движку.
    """
    best = engine.evaluate(record.fen_before, depth=depth)
    eval_mover_after = _eval_mover_after(record, engine, depth)
    cpl = max(0, best - eval_mover_after)

    classification = classify_cpl(cpl, thresholds)
    if _is_brilliant(record, cpl, eval_mover_after, thresholds):
        classification = "brilliant"
    elif _is_interesting(record, cpl, eval_mover_after, thresholds):
        classification = "interesting"

    # Сохраняем оценку с POV белых (как у eval-бара): для хода чёрных — со знаком минус.
    eval_white = eval_mover_after if record.side == "white" else -eval_mover_after
    return classification, eval_white


def _eval_mover_after(
    record: MoveRecord, engine: EvalEngine, depth: int | None
) -> int:
    """Оценка позиции после хода с POV **ходившей** стороны.

    Терминальные ``fen_after`` движку не отдаются: мат (ход поставил мат сопернику)
    → ``+_MATE_SCORE``; пат/иная ничья → ``0``. Иначе — ``-evaluate(fen_after)``
    (движок оценивает с POV соперника, чья теперь очередь).
    """
    board_after = chess.Board(record.fen_after)
    if board_after.is_checkmate():
        return _MATE_SCORE
    if board_after.is_game_over():
        return 0
    return -engine.evaluate(record.fen_after, depth=depth)


def _is_brilliant(
    record: MoveRecord,
    cpl: int,
    eval_mover_after: int,
    thresholds: ClassificationThresholds,
) -> bool:
    """Эвристика «блестящий» (D-009): почти лучший ход + сохранённый перевес + жертва."""
    if cpl > thresholds.brilliant_max_cpl:
        return False
    if eval_mover_after < thresholds.brilliant_min_eval_cp:
        return False
    board_before = chess.Board(record.fen_before)
    move = chess.Move.from_uci(record.uci)
    return _is_sacrifice(board_before, move)


def _is_interesting(
    record: MoveRecord,
    cpl: int,
    eval_mover_after: int,
    thresholds: ClassificationThresholds,
) -> bool:
    """Эвристика «интересный» (``!?``): почти лучшая жертва, но позиция неясная.

    Тот же критерий, что и «блестящий» (почти лучший ход + жертва материала), но
    перевес после хода НЕ достигает порога блестящего (``< brilliant_min_eval_cp``),
    оставаясь при этом не проигрышным (``> -brilliant_min_eval_cp``) — спекулятивная,
    острая жертва, заслуживающая внимания, но требующая проверки.
    """
    if cpl > thresholds.brilliant_max_cpl:
        return False
    if not -thresholds.brilliant_min_eval_cp < eval_mover_after < thresholds.brilliant_min_eval_cp:
        return False
    board_before = chess.Board(record.fen_before)
    move = chess.Move.from_uci(record.uci)
    return _is_sacrifice(board_before, move)


def _is_sacrifice(board: chess.Board, move: chess.Move) -> bool:
    """Жертвует ли ход материал: после размена на целевом поле сторона в минусе.

    Эвристика: берём ценность взятого ходом (если было взятие), ценность своей
    фигуры, которую теперь может забрать соперник на поле назначения самым дешёвым
    атакующим, и возможное возвращение материала (если поле защищено). Если итоговый
    баланс для ходившей стороны отрицателен — это жертва. Короля-«жертву» не
    рассматриваем.
    """
    moved = board.piece_at(move.from_square)
    if moved is None or moved.piece_type == chess.KING:
        return False

    if board.is_en_passant(move):
        captured_value = _PIECE_VALUE[chess.PAWN]
    else:
        captured = board.piece_at(move.to_square)
        captured_value = _PIECE_VALUE[captured.piece_type] if captured else 0

    after = board.copy(stack=False)
    after.push(move)
    target = move.to_square
    opponent = after.turn  # соперник ходит в позиции после нашего хода

    attackers = after.attackers(opponent, target)
    if not attackers:
        return False  # нашу фигуру никто не бьёт — это не жертва
    cheapest_attacker = min(
        _PIECE_VALUE[after.piece_at(sq).piece_type] for sq in attackers
    )
    defended = bool(after.attackers(not opponent, target))

    moved_value = _PIECE_VALUE[moved.piece_type]
    # Баланс материала для ходившей стороны: взяли захваченное, теряем свою фигуру,
    # при защите отыгрываем самого дешёвого атакующего соперника.
    swing = captured_value - moved_value + (cheapest_attacker if defended else 0)
    return swing < 0


class _SideTally:
    """Накопитель статистики классов по одной стороне → ``PlayerAnalysis``."""

    def __init__(self) -> None:
        self.total = 0
        self.accurate = 0
        self.blunders = 0
        self.mistakes = 0
        self.inaccuracies = 0

    def add(self, classification: Classification) -> None:
        self.total += 1
        if classification in _ACCURATE:
            self.accurate += 1
        if classification == "blunder":
            self.blunders += 1
        elif classification == "mistake":
            self.mistakes += 1
        elif classification == "inaccuracy":
            self.inaccuracies += 1

    def summary(self) -> PlayerAnalysis:
        accuracy = self.accurate / self.total if self.total else None
        return PlayerAnalysis(
            accuracy=accuracy,
            blunders=self.blunders,
            mistakes=self.mistakes,
            inaccuracies=self.inaccuracies,
        )
