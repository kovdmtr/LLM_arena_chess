"""Данные для анимации скольжения фигур в плеере (live и отчёт).

Доска рендерится статичным SVG-снимком на каждый ход (см. ``board_image``).
Чтобы фигуры «двигались», фронтенд накладывает поверх доски одну фигуру и
плавно перемещает её с клетки отправления на клетку прибытия. Здесь считается
геометрия этого наложения в **долях стороны доски** (0..1) — фронт не зависит от
конкретного размера/пикселей и масштабирует наложение под текущую ширину доски.

Координаты соответствуют ориентации «белые снизу» (как и весь рендер board_image).

Публичное:

- ``move_animation(fen_before, uci)`` — словарь с подходами (``moves``) и размером
  клетки (``sq``); рокировка раскладывается на скольжение короля **и** ладьи;
- ``piece_svgs()`` — словарь ``{symbol: <svg фигуры>}`` для всех 12 фигур (отчёт
  ссылается на них по символу, чтобы не дублировать SVG в каждом ходе);
- ``piece_svg(symbol)`` — SVG отдельной фигуры (для live, где удобнее инлайн).
"""

from __future__ import annotations

import chess
import chess.svg

# Геометрия chess.svg при coordinates=True: клетка 45 ед., поле координат 15 ед.
# с каждой стороны → сторона доски 8*45 + 2*15 = 390 ед. (см. chess/svg.py).
_MARGIN = 15
_BOARD_UNITS = 8 * chess.svg.SQUARE_SIZE + 2 * _MARGIN

# Размер клетки как доля стороны доски (одинаков по обеим осям).
SQUARE_FRACTION = round(chess.svg.SQUARE_SIZE / _BOARD_UNITS, 5)

# Все 12 символов фигур (FEN): заглавные — белые, строчные — чёрные.
_PIECE_SYMBOLS = "PNBRQKpnbrqk"


def _square_center_fraction(square: int) -> list[float]:
    """Центр клетки (ориентация «белые снизу») как доли стороны доски (0..1)."""
    file = chess.square_file(square)
    rank = chess.square_rank(square)
    x = _MARGIN + file * chess.svg.SQUARE_SIZE + chess.svg.SQUARE_SIZE / 2
    y = _MARGIN + (7 - rank) * chess.svg.SQUARE_SIZE + chess.svg.SQUARE_SIZE / 2
    return [round(x / _BOARD_UNITS, 5), round(y / _BOARD_UNITS, 5)]


def _sub_move(board: chess.Board, square_from: int, square_to: int) -> dict:
    """Подход одной фигуры: откуда/куда (центры), символ фигуры и цвет клетки.

    ``fromLight`` нужен фронту, чтобы замаскировать уезжающую фигуру заплаткой
    цвета клетки отправления (иначе под наложением остаётся «призрак»).
    """
    piece = board.piece_at(square_from)
    return {
        "from": _square_center_fraction(square_from),
        "to": _square_center_fraction(square_to),
        "pc": piece.symbol() if piece else "",
        "fromLight": bool(chess.BB_LIGHT_SQUARES & chess.BB_SQUARES[square_from]),
    }


def _castle_rook_squares(king_to: int) -> tuple[int, int]:
    """Клетки ладьи при рокировке по клетке прибытия короля (обычные шахматы)."""
    rank = chess.square_rank(king_to)
    if chess.square_file(king_to) == 6:  # король на g → короткая
        return chess.square(7, rank), chess.square(5, rank)
    return chess.square(0, rank), chess.square(3, rank)  # король на c → длинная


def move_animation(fen_before: str, uci: str) -> dict | None:
    """Данные анимации хода ``uci`` из позиции ``fen_before``.

    Возвращает ``{"sq": доля, "moves": [подход, ...]}``: обычно один подход, для
    рокировки — два (король и ладья). ``None``, если на клетке отправления нет
    фигуры или ход не парсится (анимация просто пропускается — доска сменится
    мгновенно). Превращение скользит пешкой, а итоговую фигуру показывает уже
    снимок после хода (для фронта это один обычный подход).
    """
    try:
        board = chess.Board(fen_before)
        move = chess.Move.from_uci(uci)
    except ValueError:
        return None
    if board.piece_at(move.from_square) is None:
        return None
    subs = [_sub_move(board, move.from_square, move.to_square)]
    if board.is_castling(move):
        rook_from, rook_to = _castle_rook_squares(move.to_square)
        subs.append(_sub_move(board, rook_from, rook_to))
    return {"sq": SQUARE_FRACTION, "moves": subs}


def piece_svg(symbol: str) -> str:
    """SVG отдельной фигуры по FEN-символу (``"P"``/``"n"`` …)."""
    return chess.svg.piece(chess.Piece.from_symbol(symbol))


def piece_svgs() -> dict[str, str]:
    """Словарь ``{symbol: <svg>}`` для всех 12 фигур (для самодостаточного отчёта)."""
    return {sym: piece_svg(sym) for sym in _PIECE_SYMBOLS}
