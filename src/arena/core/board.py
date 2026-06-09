"""Обёртка над ``python-chess``: состояние доски и причина окончания партии.

``Board`` инкапсулирует ``chess.Board`` и отдаёт ядру арены ровно то, что нужно
для игрового цикла и логов:

- текущий FEN (``fen``) и чья очередь (``turn``);
- легальные ходы в SAN/UCI (``legal_moves_san`` / ``legal_moves_uci``);
- применение хода (``push`` для ``chess.Move``, ``push_san`` для строки SAN);
- проверку конца партии (``is_game_over``) и её исход с причиной (``outcome``).

Заявляемые ничьи (50-ходовое правило, троекратное повторение) учитываются
автоматически при ``auto_claim_draws=True`` — см. D-012 в ``docs/DECISIONS.md``.
Правила и легальность — только через ``python-chess`` (D-005), не вручную.
"""

from __future__ import annotations

from dataclasses import dataclass

import chess

# Перевод ``chess.Termination`` в стабильный строковый код причины окончания.
# Эти коды попадают в ``game.json``/PGN/HTML, поэтому они часть контракта.
_TERMINATION_NAMES: dict[chess.Termination, str] = {
    chess.Termination.CHECKMATE: "checkmate",
    chess.Termination.STALEMATE: "stalemate",
    chess.Termination.INSUFFICIENT_MATERIAL: "insufficient_material",
    chess.Termination.SEVENTYFIVE_MOVES: "seventyfive_moves",
    chess.Termination.FIVEFOLD_REPETITION: "fivefold_repetition",
    chess.Termination.FIFTY_MOVES: "fifty_moves",
    chess.Termination.THREEFOLD_REPETITION: "threefold_repetition",
    chess.Termination.VARIANT_WIN: "variant_win",
    chess.Termination.VARIANT_LOSS: "variant_loss",
    chess.Termination.VARIANT_DRAW: "variant_draw",
}


@dataclass(frozen=True)
class GameOutcome:
    """Исход партии: результат, победитель и причина окончания.

    - ``result`` — строка PGN-результата (``"1-0"`` / ``"0-1"`` / ``"1/2-1/2"``).
    - ``winner`` — ``"white"`` / ``"black"`` или ``None`` при ничьей.
    - ``termination`` — стабильный код причины (см. ``_TERMINATION_NAMES``).
    """

    result: str
    winner: str | None
    termination: str


def _color_name(white_to_move: bool) -> str:
    return "white" if white_to_move else "black"


class Board:
    """Тонкая обёртка над ``chess.Board`` для нужд арены."""

    def __init__(self, fen: str | None = None, *, auto_claim_draws: bool = True) -> None:
        """Создать доску из ``fen`` (или стартовую позицию).

        ``auto_claim_draws`` включает учёт 50-ходового правила и троекратного
        повторения как окончания партии (D-012).
        """
        self._board = chess.Board(fen) if fen else chess.Board()
        self._auto_claim_draws = auto_claim_draws

    @property
    def turn(self) -> str:
        """Чья очередь ходить: ``"white"`` или ``"black"``."""
        return _color_name(self._board.turn)

    @property
    def fullmove_number(self) -> int:
        """Номер полного хода (растёт после хода чёрных)."""
        return self._board.fullmove_number

    @property
    def ply(self) -> int:
        """Число сделанных полуходов от начала партии."""
        return self._board.ply()

    def fen(self) -> str:
        """Полный FEN текущей позиции."""
        return self._board.fen()

    def legal_moves_san(self) -> list[str]:
        """Легальные ходы в нотации SAN (в порядке генерации движка)."""
        return [self._board.san(move) for move in self._board.legal_moves]

    def legal_moves_uci(self) -> list[str]:
        """Легальные ходы в нотации UCI."""
        return [move.uci() for move in self._board.legal_moves]

    def san_of(self, move: chess.Move) -> str:
        """SAN-запись хода в текущей позиции (ход не применяется)."""
        return self._board.san(move)

    def parse_san(self, san: str) -> chess.Move:
        """Разобрать ход в SAN без применения.

        Бросает подклассы ``ValueError`` из ``python-chess``
        (``InvalidMoveError`` / ``IllegalMoveError`` / ``AmbiguousMoveError``).
        """
        return self._board.parse_san(san)

    def parse_uci(self, uci: str) -> chess.Move:
        """Разобрать ход в UCI без применения, с проверкой легальности.

        Бросает ``InvalidMoveError`` при неверном формате и ``IllegalMoveError``,
        если ход нелегален в текущей позиции.
        """
        return self._board.parse_uci(uci)

    def push(self, move: chess.Move) -> None:
        """Применить уже разобранный ``chess.Move``.

        ``ValueError``, если ход нелегален в текущей позиции.
        """
        if move not in self._board.legal_moves:
            raise ValueError(f"нелегальный ход {move.uci()} в позиции {self._board.fen()}")
        self._board.push(move)

    def push_san(self, san: str) -> chess.Move:
        """Разобрать ход в SAN, применить его и вернуть ``chess.Move``.

        Пробрасывает ``ValueError`` (``python-chess`` бросает его подклассы:
        ``InvalidMoveError`` / ``IllegalMoveError`` / ``AmbiguousMoveError``)
        при нераспознанном, нелегальном или неоднозначном ходе.
        """
        move = self._board.parse_san(san)
        self._board.push(move)
        return move

    def is_game_over(self) -> bool:
        """Окончена ли партия (с учётом ``auto_claim_draws``)."""
        return self._board.is_game_over(claim_draw=self._auto_claim_draws)

    def outcome(self) -> GameOutcome | None:
        """Исход партии или ``None``, если игра ещё идёт."""
        raw = self._board.outcome(claim_draw=self._auto_claim_draws)
        if raw is None:
            return None
        winner = None if raw.winner is None else _color_name(raw.winner)
        termination = _TERMINATION_NAMES.get(raw.termination, raw.termination.name.lower())
        return GameOutcome(result=raw.result(), winner=winner, termination=termination)

    def copy(self) -> "Board":
        """Независимая копия доски с тем же режимом ничьих."""
        clone = Board.__new__(Board)
        clone._board = self._board.copy()
        clone._auto_claim_draws = self._auto_claim_draws
        return clone

    def __repr__(self) -> str:
        return f"Board(fen={self._board.fen()!r})"
