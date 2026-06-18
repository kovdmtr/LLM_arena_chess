"""Тесты данных анимации скольжения фигур (геометрия клеток, рокировка, фигуры)."""

import chess

from arena.report import SQUARE_FRACTION, move_animation, piece_svg, piece_svgs


def test_square_fraction_matches_geometry():
    # Клетка 45 ед. из стороны 390 ед. (8*45 + 2*15 поля координат).
    assert abs(SQUARE_FRACTION - 45 / 390) < 1e-4


def test_move_animation_simple_pawn_push():
    anim = move_animation(chess.STARTING_FEN, "e2e4")
    assert anim is not None
    assert anim["sq"] == SQUARE_FRACTION
    assert len(anim["moves"]) == 1
    sub = anim["moves"][0]
    assert sub["pc"] == "P"
    assert sub["fromLight"] is True  # e2 — светлая клетка
    # Тот же файл (x совпадает), движение «вверх» по доске → y уменьшается.
    assert abs(sub["from"][0] - sub["to"][0]) < 1e-6
    assert sub["from"][1] > sub["to"][1]
    # Координаты — доли стороны доски (0..1).
    for coord in (*sub["from"], *sub["to"]):
        assert 0.0 < coord < 1.0


def test_move_animation_castling_includes_rook():
    fen = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"
    anim = move_animation(fen, "e1g1")  # короткая рокировка белых
    assert anim is not None
    assert len(anim["moves"]) == 2
    assert sorted(m["pc"] for m in anim["moves"]) == ["K", "R"]


def test_move_animation_none_for_empty_or_invalid():
    assert move_animation(chess.STARTING_FEN, "e3e4") is None  # на e3 нет фигуры
    assert move_animation("totally not a fen", "e2e4") is None


def test_piece_svgs_cover_all_twelve():
    pieces = piece_svgs()
    assert len(pieces) == 12
    assert set(pieces) == set("PNBRQKpnbrqk")
    assert pieces["P"].lstrip().startswith("<svg")
    assert piece_svg("k").lstrip().startswith("<svg")
