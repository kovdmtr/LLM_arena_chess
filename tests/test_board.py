"""Тесты обёртки доски: состояние, легальные ходы, применение, исход партии.

Базовое покрытие board wrapper. Глубокие краевые случаи окончания (повторения,
50-ходовое правило, недостаток материала) — в отдельной задаче
``test(core): board and endgame detection``.
"""

import chess
import pytest

from arena.core import Board, GameOutcome


def test_initial_state():
    board = Board()
    assert board.fen() == chess.STARTING_FEN
    assert board.turn == "white"
    assert board.fullmove_number == 1
    assert board.ply == 0
    assert board.is_game_over() is False
    assert board.outcome() is None


def test_initial_legal_moves_count():
    board = Board()
    assert len(board.legal_moves_san()) == 20
    assert len(board.legal_moves_uci()) == 20
    assert "e4" in board.legal_moves_san()
    assert "e2e4" in board.legal_moves_uci()


def test_push_san_advances_turn_and_clock():
    board = Board()
    move = board.push_san("e4")
    assert isinstance(move, chess.Move)
    assert move.uci() == "e2e4"
    assert board.turn == "black"
    assert board.fullmove_number == 1
    board.push_san("e5")
    assert board.turn == "white"
    assert board.fullmove_number == 2
    assert board.ply == 2


def test_push_san_rejects_illegal_and_garbage():
    board = Board()
    with pytest.raises(ValueError):
        board.push_san("e5")  # нелегальный первый ход пешкой через клетку
    with pytest.raises(ValueError):
        board.push_san("zz9")  # мусор
    # Состояние не должно измениться после неудачных попыток.
    assert board.fen() == chess.STARTING_FEN


def test_push_move_validates_legality():
    board = Board()
    legal = chess.Move.from_uci("e2e4")
    board.push(legal)
    assert board.turn == "black"
    # Ход, легальный по форме, но не в этой позиции.
    with pytest.raises(ValueError, match="нелегальный ход"):
        board.push(chess.Move.from_uci("e2e4"))


def test_copy_is_independent():
    board = Board()
    board.push_san("e4")
    clone = board.copy()
    clone.push_san("e5")
    # Изменение копии не трогает оригинал.
    assert board.turn == "black"
    assert clone.turn == "white"
    assert board.fen() != clone.fen()


def test_checkmate_outcome():
    board = Board()
    # «Дурацкий мат»: чёрные ставят мат на 2-м ходу.
    for san in ["f3", "e5", "g4", "Qh4#"]:
        board.push_san(san)
    assert board.is_game_over() is True
    outcome = board.outcome()
    assert outcome == GameOutcome(result="0-1", winner="black", termination="checkmate")


def test_stalemate_outcome():
    # Классическая патовая позиция: ход чёрных, у них нет ходов, но нет шаха.
    board = Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    assert board.is_game_over() is True
    outcome = board.outcome()
    assert outcome is not None
    assert outcome.result == "1/2-1/2"
    assert outcome.winner is None
    assert outcome.termination == "stalemate"


def test_auto_claim_draws_toggle_for_fifty_move_rule():
    # Позиция на пороге 50-ходового правила (halfmove clock = 100). Ладьи на
    # доске, чтобы исключить раннее окончание по недостатку материала.
    fen = "8/8/8/4k3/8/4K3/R7/r7 w - - 100 80"
    claimed = Board(fen, auto_claim_draws=True)
    assert claimed.is_game_over() is True
    assert claimed.outcome().termination == "fifty_moves"
    # С выключенным авто-claim партия формально продолжается.
    open_game = Board(fen, auto_claim_draws=False)
    assert open_game.is_game_over() is False
    assert open_game.outcome() is None
