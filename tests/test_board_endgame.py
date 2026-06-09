"""Краевые случаи окончания партии: повторения, недостаток материала, 75 ходов.

Дополняет базовое покрытие из ``test_board.py`` (мат/пат/50-ходовое правило).
Здесь проверяется, что ``Board`` корректно отдаёт исход для всех «тихих» ничьих
``python-chess`` и что заявляемые ничьи зависят от флага ``auto_claim_draws`` (D-012),
а автоматические (75 ходов, пятикратное повторение) — нет.
"""

import pytest

from arena.core import Board, GameOutcome

# Бесконечное «шарканье» конями: после каждого блока из 4 полуходов на доске
# снова стартовая позиция, что наращивает счётчик её повторений.
_KNIGHT_SHUFFLE = ["Nf3", "Nf6", "Ng1", "Ng8"]


@pytest.mark.parametrize(
    "fen",
    [
        "8/8/4k3/8/8/4K3/8/8 w - - 0 1",      # одинокие короли
        "8/8/4k3/8/8/4KB2/8/8 w - - 0 1",     # король и слон против короля
        "8/8/4k3/8/8/4KN2/8/8 w - - 0 1",     # король и конь против короля
    ],
)
def test_insufficient_material_is_a_draw(fen):
    # Недостаток материала — автоматическая ничья, не зависит от auto_claim_draws.
    board = Board(fen, auto_claim_draws=False)
    assert board.is_game_over() is True
    assert board.outcome() == GameOutcome(
        result="1/2-1/2", winner=None, termination="insufficient_material"
    )


def test_seventyfive_move_rule_is_automatic():
    # halfmove clock = 150: партия заканчивается без всякого заявления о ничьей.
    board = Board("8/8/8/4k3/8/4K3/R7/r7 w - - 150 120", auto_claim_draws=False)
    assert board.is_game_over() is True
    outcome = board.outcome()
    assert outcome is not None
    assert outcome.result == "1/2-1/2"
    assert outcome.winner is None
    assert outcome.termination == "seventyfive_moves"


def test_threefold_repetition_requires_claim():
    # Два полных цикла шарканья => стартовая позиция встречается в третий раз.
    moves = _KNIGHT_SHUFFLE * 2
    claimed = Board(auto_claim_draws=True)
    for san in moves:
        claimed.push_san(san)
    assert claimed.is_game_over() is True
    assert claimed.outcome() == GameOutcome(
        result="1/2-1/2", winner=None, termination="threefold_repetition"
    )
    # Без авто-claim троекратное повторение само по себе не завершает партию.
    open_game = Board(auto_claim_draws=False)
    for san in moves:
        open_game.push_san(san)
    assert open_game.is_game_over() is False
    assert open_game.outcome() is None


def test_fivefold_repetition_is_automatic():
    # Четыре цикла => стартовая позиция в пятый раз: автоматическая ничья даже
    # при выключенном auto_claim_draws.
    board = Board(auto_claim_draws=False)
    for san in _KNIGHT_SHUFFLE * 4:
        board.push_san(san)
    assert board.is_game_over() is True
    outcome = board.outcome()
    assert outcome is not None
    assert outcome.result == "1/2-1/2"
    assert outcome.winner is None
    assert outcome.termination == "fivefold_repetition"
