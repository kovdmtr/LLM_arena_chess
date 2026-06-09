"""Шахматный домен: доска, парсинг ходов, сборка PGN (поверх python-chess)."""

from arena.core.board import Board, GameOutcome
from arena.core.move_parsing import MoveParseError, ParsedMove, parse_move
from arena.core.pgn import build_pgn

__all__ = [
    "Board",
    "GameOutcome",
    "MoveParseError",
    "ParsedMove",
    "build_pgn",
    "parse_move",
]
