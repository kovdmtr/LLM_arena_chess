"""Шахматный домен: доска, парсинг ходов, сборка PGN (поверх python-chess)."""

from arena.core.board import Board, GameOutcome
from arena.core.move_parsing import MoveParseError, ParsedMove, parse_move

__all__ = ["Board", "GameOutcome", "MoveParseError", "ParsedMove", "parse_move"]
