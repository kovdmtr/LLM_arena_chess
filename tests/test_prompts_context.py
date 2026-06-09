"""Тесты сборки per-turn контекста хода (спека 3.6, ``feat(prompts): context builder``).

Контекст собирается из ``GameRecord`` (история/игроки/лимиты) и живого ``Board``.
Проверяем присутствие и содержимое всех блоков: цвет+номер хода, FEN, легальные
ходы, PGN-снимок, объяснения обеих сторон, остаток подсказок, инъекция подсказки и
блок коррекции ретрая.
"""

from datetime import datetime

import pytest

from arena.core import Board, build_pgn
from arena.models import (
    GameRecord,
    HintRecord,
    IllegalAttempt,
    MessageRecord,
    MoveRecord,
    PlayerInfo,
    PlayerSettings,
)
from arena.prompts import build_context, context_message


def _player(side: str) -> PlayerInfo:
    return PlayerInfo(
        model_id=f"model-{side}", provider="openai", display_name=f"Model {side}"
    )


def _game(*, moves=None, hints_used=None, hints_per_player: int = 3) -> GameRecord:
    return GameRecord(
        id="g1",
        created_at=datetime(2026, 6, 9, 12, 0, 0),
        players={"white": _player("white"), "black": _player("black")},
        settings=PlayerSettings(hints_per_player=hints_per_player),
        moves=list(moves or []),
        hints_used=dict(hints_used or {"white": 0, "black": 0}),
    )


def _play(steps: list[tuple[str, str]]) -> tuple[Board, list[MoveRecord]]:
    """Сыграть SAN-ходы со старта; вернуть (живой board, записи ходов).

    ``steps`` — список ``(san, reasoning)``. SAN канонизируется через ``python-chess``,
    чтобы запись совпадала с тем, что отдаёт доска.
    """
    board = Board()
    records: list[MoveRecord] = []
    for i, (san, reasoning) in enumerate(steps, start=1):
        move = board.parse_san(san)
        san_canonical = board.san_of(move)
        fen_before = board.fen()
        board.push(move)
        records.append(
            MoveRecord(
                ply=i,
                side="white" if i % 2 == 1 else "black",
                san=san_canonical,
                uci=move.uci(),
                fen_before=fen_before,
                fen_after=board.fen(),
                reasoning=reasoning,
            )
        )
    return board, records


def test_color_and_move_number_at_start():
    text = build_context(_game(), Board())
    assert "You are playing White" in text
    assert "move 1, your turn" in text


def test_black_to_move_after_one_move():
    board, moves = _play([("e4", "Контроль центра.")])
    text = build_context(_game(moves=moves), board)
    assert "You are playing Black" in text
    assert "move 1, your turn" in text


def test_fen_and_legal_moves_listed():
    board = Board()
    text = build_context(_game(), board)
    assert board.fen() in text
    # Стартовые легальные ходы присутствуют в SAN-списке.
    assert "Legal moves (SAN):" in text
    assert "e4" in text
    assert "Nf3" in text


def test_pgn_snapshot_without_reasoning_comments():
    board, moves = _play([("e4", "центр"), ("e5", "симметрия"), ("Nf3", "развитие")])
    game = _game(moves=moves)
    text = build_context(game, board)
    assert "Game so far (PGN):" in text
    # Снимок — ровно канонический PGN без комментариев-рассуждений.
    assert build_pgn(game, include_reasoning=False) in text


def test_history_empty_on_first_move():
    text = build_context(_game(), Board())
    assert "this is the first move" in text


def test_history_lists_both_sides_with_reasoning():
    board, moves = _play([("e4", "Открываю центр."), ("c5", "Сицилианская.")])
    text = build_context(_game(moves=moves), board)
    assert "1. White e4 — Открываю центр." in text
    assert "1. Black c5 — Сицилианская." in text


def test_history_full_move_numbering():
    board, moves = _play(
        [("e4", "a"), ("e5", "b"), ("Nf3", "c"), ("Nc6", "d"), ("Bb5", "e")]
    )
    text = build_context(_game(moves=moves), board)
    # Пятый полуход (белые) — это уже 3-й полный ход.
    assert "3. White Bb5 — e" in text
    assert "2. White Nf3 — c" in text


def test_history_move_without_reasoning_has_no_dash():
    board, moves = _play([("e4", "")])
    text = build_context(_game(moves=moves), board)
    assert "1. White e4" in text
    assert "1. White e4 —" not in text


def test_hints_remaining_default():
    text = build_context(_game(), Board())
    assert "Hints remaining: 3" in text


def test_hints_remaining_after_use():
    board, moves = _play([("e4", "x")])  # ход белых сделан, ходят чёрные
    text = build_context(
        _game(moves=moves, hints_used={"white": 1, "black": 2}), board
    )
    # Остаток считается для стороны, чья очередь (чёрные): 3 - 2 = 1.
    assert "Hints remaining: 1" in text


def test_hints_remaining_clamped_at_zero():
    text = build_context(_game(hints_used={"white": 5, "black": 0}), Board())
    assert "Hints remaining: 0" in text


def test_no_retry_or_hint_sections_by_default():
    text = build_context(_game(), Board())
    assert "was rejected" not in text
    assert "Engine hint" not in text


def test_retry_section_present():
    retry = IllegalAttempt(raw="Zz9", reason="ход не распознан")
    text = build_context(_game(), Board(), retry=retry)
    assert 'Your previous answer "Zz9" was rejected: ход не распознан' in text
    assert "Choose one move from the legal moves listed above." in text


def test_hint_section_with_centipawns():
    hint = HintRecord(best_move="e2e4", eval_cp=35)
    text = build_context(_game(), Board(), hint=hint)
    assert "Engine hint (requested earlier):" in text
    assert "best move e2e4" in text
    assert "+0.35" in text


def test_hint_section_negative_eval_signed():
    hint = HintRecord(best_move="e2e4", eval_cp=-120)
    text = build_context(_game(), Board(), hint=hint)
    assert "-1.20" in text


def test_hint_section_with_mate():
    hint = HintRecord(best_move="d1h5", mate_in=2)
    text = build_context(_game(), Board(), hint=hint)
    assert "mate in 2" in text


def test_hint_section_unavailable_eval():
    hint = HintRecord(best_move="e2e4")
    text = build_context(_game(), Board(), hint=hint)
    assert "evaluation unavailable" in text


def test_reply_format_reminder_present():
    text = build_context(_game(), Board())
    assert '"reasoning"' in text
    assert '"move"' in text


def test_context_message_wraps_user_role():
    game, board = _game(), Board()
    msg = context_message(game, board)
    assert isinstance(msg, MessageRecord)
    assert msg.role == "user"
    assert msg.content == build_context(game, board)
