"""Расширенные тесты PGN-экспорта: валидность и совместимость (lichess/chess.com).

Дополняют ``test_pgn.py`` (базовое поведение) проверками на «настоящих» партиях и
кромочных ходах. Партии собираются через ``python-chess``: последовательность SAN
проигрывается на доске, из неё берутся согласованные ``uci``/``fen_before``/
``fen_after`` — поэтому ``MoveRecord`` всегда соответствует легальной позиции, а тест
сам себя валидирует (нелегальный SAN поднимет ошибку при сборке фикстуры).
"""

import io
import re
from datetime import datetime, timezone

import chess
import chess.pgn

from arena import GameRecord, MoveRecord, PlayerInfo
from arena.core import build_pgn


def _build_game(
    sans,
    *,
    result="*",
    termination=None,
    reasonings=None,
    white=("gpt-4o", "openai", "GPT-4o"),
    black=("claude-opus-4-8", "anthropic", "Claude Opus 4.8"),
):
    """Собрать ``GameRecord`` из списка SAN-ходов через ``python-chess``."""
    board = chess.Board()
    moves = []
    for index, san in enumerate(sans, start=1):
        move = board.parse_san(san)
        fen_before = board.fen()
        uci = move.uci()
        board.push(move)
        reasoning = reasonings[index - 1] if reasonings else ""
        moves.append(
            MoveRecord(
                ply=index,
                side="white" if index % 2 == 1 else "black",
                san=san,
                uci=uci,
                fen_before=fen_before,
                fen_after=board.fen(),
                reasoning=reasoning,
            )
        )
    return GameRecord(
        id="game-1",
        created_at=datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc),
        players={
            "white": PlayerInfo(model_id=white[0], provider=white[1], display_name=white[2]),
            "black": PlayerInfo(model_id=black[0], provider=black[1], display_name=black[2]),
        },
        moves=moves,
        result=result,
        termination=termination,
    )


def _parse(pgn_text: str) -> chess.pgn.Game:
    parsed = chess.pgn.read_game(io.StringIO(pgn_text))
    assert parsed is not None
    return parsed


# Классический «детский мат»: 1.e4 e5 2.Bc4 Nc6 3.Qh5 Nf6?? 4.Qxf7#.
_SCHOLARS_MATE = ["e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6", "Qxf7#"]


def test_full_game_round_trips_to_checkmate():
    pgn = build_pgn(_build_game(_SCHOLARS_MATE, result="1-0", termination="checkmate"))
    parsed = _parse(pgn)

    # Все ходы перепроигрываются легально и позиция действительно матовая.
    board = chess.Board()
    for move in parsed.mainline_moves():
        assert move in board.legal_moves
        board.push(move)
    assert board.is_checkmate()
    assert [n.san() for n in parsed.mainline()] == _SCHOLARS_MATE
    assert parsed.headers["Result"] == "1-0"


def test_seven_tag_roster_appears_in_standard_order():
    # Совместимость: STR должен идти в каноническом порядке до служебных тегов.
    pgn = build_pgn(_build_game(_SCHOLARS_MATE, result="1-0", termination="checkmate"))
    order = ["Event", "Site", "Date", "Round", "White", "Black", "Result"]
    positions = [pgn.index(f'[{tag} ') for tag in order]
    assert positions == sorted(positions)
    assert all(p != -1 for p in positions)


def test_all_headers_survive_reparse():
    game = _build_game(_SCHOLARS_MATE, result="1-0", termination="checkmate")
    h = _parse(build_pgn(game)).headers
    assert h["Event"] == "LLM Chess Arena"
    assert h["Site"] == "LLM Chess Arena"
    assert h["Date"] == "2026.06.09"
    assert h["Round"] == "1"
    assert h["White"] == "GPT-4o"
    assert h["Black"] == "Claude Opus 4.8"
    assert h["Result"] == "1-0"
    assert h["Termination"] == "checkmate"
    assert h["WhiteModel"] == "gpt-4o"
    assert h["BlackModel"] == "claude-opus-4-8"
    assert h["WhiteProvider"] == "openai"
    assert h["BlackProvider"] == "anthropic"


def test_castling_renders_as_san():
    sans = ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "O-O"]
    parsed = _parse(build_pgn(_build_game(sans)))
    assert [n.san() for n in parsed.mainline()] == sans
    # Рокировка перепарсивается именно как рокировочный ход в своей позиции.
    board = chess.Board()
    moves = list(parsed.mainline_moves())
    for mv in moves[:-1]:
        board.push(mv)
    assert board.is_castling(moves[-1])


def test_en_passant_renders_as_san():
    # 1.e4 a6 2.e5 d5 3.exd6 e.p.
    sans = ["e4", "a6", "e5", "d5", "exd6"]
    parsed = _parse(build_pgn(_build_game(sans)))
    assert [n.san() for n in parsed.mainline()] == sans
    board = chess.Board()
    moves = list(parsed.mainline_moves())
    for mv in moves[:-1]:
        board.push(mv)
    assert board.is_en_passant(moves[-1])


def test_promotion_renders_as_san():
    # Доводим белую пешку до 8-й горизонтали с превращением в ферзя (со взятием).
    sans = [
        "e4", "d5", "exd5", "c6", "dxc6", "Nf6",  # белая пешка прорывается по диагонали
        "cxb7", "e6", "bxa8=Q",
    ]
    parsed = _parse(build_pgn(_build_game(sans)))
    rendered = [n.san() for n in parsed.mainline()]
    assert rendered == sans
    assert rendered[-1].endswith("=Q")


def test_each_result_token_terminates_movetext():
    for result in ("1-0", "0-1", "1/2-1/2", "*"):
        pgn = build_pgn(_build_game(["e4", "e5"], result=result))
        assert pgn.rstrip().endswith(result)


def test_termination_tag_absent_when_none():
    pgn = build_pgn(_build_game(["e4", "e5"], termination=None))
    assert "Termination" not in _parse(pgn).headers


def test_event_site_and_round_overrides_apply():
    pgn = build_pgn(
        _build_game(["e4", "e5"]),
        event="World LLM Cup",
        site="https://example.test/arena",
        round_="7",
    )
    h = _parse(pgn).headers
    assert h["Event"] == "World LLM Cup"
    assert h["Site"] == "https://example.test/arena"
    assert h["Round"] == "7"


def test_move_numbering_is_correct_in_text():
    pgn = build_pgn(_build_game(_SCHOLARS_MATE, result="1-0"))
    movetext = pgn.split("\n\n", 1)[1]  # после блока заголовков
    assert "1. e4 e5" in movetext
    assert "2. Bc4 Nc6" in movetext
    assert "4. Qxf7#" in movetext


def test_unicode_in_names_and_reasoning_survive_round_trip():
    game = _build_game(
        ["e4", "e5"],
        reasonings=("захват центра ♟ — план «итальянка»", "симметричный ответ"),
        white=("custom-model", "openai", "Шахматный Гроссмейстер ♞"),
    )
    parsed = _parse(build_pgn(game))
    assert parsed.headers["White"] == "Шахматный Гроссмейстер ♞"
    first = parsed.variation(0)
    assert "♟" in first.comment and "итальянка" in first.comment


def test_draw_game_is_compatible():
    # Ничейный результат с корректным токеном и перепроигрыванием ходов.
    pgn = build_pgn(
        _build_game(["e4", "e5", "Nf3", "Nf6"], result="1/2-1/2", termination="stalemate"),
    )
    parsed = _parse(pgn)
    assert parsed.headers["Result"] == "1/2-1/2"
    assert parsed.headers["Termination"] == "stalemate"
    board = chess.Board()
    for move in parsed.mainline_moves():
        assert move in board.legal_moves
        board.push(move)


def test_no_secret_material_leaks_into_export():
    pgn = build_pgn(_build_game(_SCHOLARS_MATE, result="1-0", termination="checkmate"))
    low = pgn.lower()
    assert "api_key" not in low
    assert "sk-" not in pgn
    assert not re.search(r"\bsecret\b", low)
