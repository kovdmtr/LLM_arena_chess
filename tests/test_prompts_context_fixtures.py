"""Фикстурные тесты контекста хода (``test(prompts): context builder``).

Дополняют ``test_prompts_context.py`` сценариями «на фикстурах»: реальная завязка
партии, точный блок объяснений, валидность встроенного PGN-снимка (round-trip),
совпадение показанных легальных ходов с доской, порядок секций и комбинация
«подсказка + ретрай».
"""

import io
from datetime import datetime

import chess.pgn
import pytest

from arena.core import Board
from arena.models import (
    GameRecord,
    HintRecord,
    IllegalAttempt,
    MoveRecord,
    PlayerInfo,
    PlayerSettings,
)
from arena.prompts import build_context

# Завязка испанской партии (Ruy Lopez) — общий фикстур для нескольких тестов.
RUY_LOPEZ = [
    ("e4", "Захватываю центр и открываю линии."),
    ("e5", "Симметричный ответ в центре."),
    ("Nf3", "Развиваю коня с нападением на e5."),
    ("Nc6", "Защищаю пешку e5."),
    ("Bb5", "Испанская: давление на коня c6."),
]


def _player(side: str) -> PlayerInfo:
    return PlayerInfo(
        model_id=f"model-{side}", provider="openai", display_name=f"Model {side}"
    )


def _fixture(
    steps: list[tuple[str, str]], *, hints_used=None, hints_per_player: int = 3
) -> tuple[GameRecord, Board]:
    """Построить согласованные ``GameRecord`` и живой ``Board`` из SAN-ходов."""
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
    game = GameRecord(
        id="g1",
        created_at=datetime(2026, 6, 9, 12, 0, 0),
        players={"white": _player("white"), "black": _player("black")},
        settings=PlayerSettings(hints_per_player=hints_per_player),
        moves=records,
        hints_used=dict(hints_used or {"white": 0, "black": 0}),
    )
    return game, board


def test_explanations_block_is_exact_and_ordered():
    game, board = _fixture(RUY_LOPEZ)
    text = build_context(game, board)
    expected = "\n".join(
        [
            "Move explanations so far:",
            "1. White e4 — Захватываю центр и открываю линии.",
            "1. Black e5 — Симметричный ответ в центре.",
            "2. White Nf3 — Развиваю коня с нападением на e5.",
            "2. Black Nc6 — Защищаю пешку e5.",
            "3. White Bb5 — Испанская: давление на коня c6.",
        ]
    )
    assert expected in text


def test_embedded_pgn_snapshot_is_a_valid_game():
    game, board = _fixture(RUY_LOPEZ)
    text = build_context(game, board)
    # Вырезаем PGN-секцию (между её заголовком и следующим блоком) и парсим её
    # обратно как настоящую партию — снимок должен открываться как валидный PGN.
    marker = "Game so far (PGN):\n"
    rest = text.split(marker, 1)[1]
    pgn_text = rest.split("\n\nMove explanations so far:", 1)[0]
    parsed = chess.pgn.read_game(io.StringIO(pgn_text))
    assert parsed is not None
    assert len(list(parsed.mainline_moves())) == len(RUY_LOPEZ)


def test_listed_legal_moves_match_the_board_exactly():
    game, board = _fixture(RUY_LOPEZ)
    text = build_context(game, board)
    # В контекст попадает ровно множество легальных ходов доски (D-005): модель
    # выбирает строго из показанного списка.
    assert " ".join(board.legal_moves_san()) in text


def test_side_to_move_tracks_the_board_after_each_ply():
    # На каждом префиксе партии цвет в контексте совпадает с очередью на доске.
    for n in range(len(RUY_LOPEZ) + 1):
        game, board = _fixture(RUY_LOPEZ[:n])
        text = build_context(game, board)
        expected = "White" if board.turn == "white" else "Black"
        assert f"You are playing {expected}." in text


def test_section_order_color_fen_moves_pgn_history_hints():
    game, board = _fixture(RUY_LOPEZ)
    text = build_context(game, board)
    order = [
        "You are playing",
        "Current position (FEN):",
        "Legal moves (SAN):",
        "Game so far (PGN):",
        "Move explanations so far:",
        "Hints remaining:",
        "Reply with one JSON object",
    ]
    positions = [text.index(marker) for marker in order]
    assert positions == sorted(positions)


def test_hint_and_retry_present_together_and_ordered():
    game, board = _fixture(RUY_LOPEZ[:1])  # ходят чёрные
    hint = HintRecord(best_move="b8c6", eval_cp=20)
    retry = IllegalAttempt(raw="Qxz9", reason="ход нелегален")
    text = build_context(game, board, retry=retry, hint=hint)
    assert "Engine hint (requested earlier):" in text
    assert 'Your previous answer "Qxz9" was rejected: ход нелегален' in text
    # Подсказка идёт перед блоком коррекции и оба — перед финальным напоминанием.
    assert text.index("Engine hint") < text.index("was rejected")
    assert text.index("was rejected") < text.index("Reply with one JSON object")


def test_hints_remaining_reflects_side_to_move():
    # Белые израсходовали 3 (0 осталось), чёрные — 1 (2 осталось).
    used = {"white": 3, "black": 1}
    # После 1-го хода очередь чёрных → должно показать остаток чёрных (2).
    game_black, board_black = _fixture(RUY_LOPEZ[:1], hints_used=used)
    assert "Hints remaining: 2" in build_context(game_black, board_black)
    # Старт партии — очередь белых → остаток белых (0).
    game_white, board_white = _fixture([], hints_used=used)
    assert "Hints remaining: 0" in build_context(game_white, board_white)


def test_no_secrets_in_context():
    game, board = _fixture(RUY_LOPEZ)
    text = build_context(game, board).lower()
    assert "api_key" not in text
    assert "sk-" not in text
