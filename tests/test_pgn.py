"""Тесты сборки PGN из GameRecord: теги, ходы SAN, комментарии-рассуждения."""

import io
from datetime import datetime, timezone

import chess
import chess.pgn

from arena import GameRecord, MoveRecord, PlayerInfo
from arena.core import build_pgn


def _player(model_id="gpt-4o", provider="openai", display_name="GPT-4o") -> PlayerInfo:
    return PlayerInfo(model_id=model_id, provider=provider, display_name=display_name)


def _move(ply, side, san, uci, fen_before, fen_after, reasoning="") -> MoveRecord:
    return MoveRecord(
        ply=ply,
        side=side,
        san=san,
        uci=uci,
        fen_before=fen_before,
        fen_after=fen_after,
        reasoning=reasoning,
    )


# Короткая партия 1.e4 e5 2.Qh5 — детерминированные FEN не нужны тестам PGN,
# поэтому fen_* заполнены формально (PGN строится из uci, а не из fen).
_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def _game(*, result="*", termination=None, reasonings=("", "", "")) -> GameRecord:
    moves = [
        _move(1, "white", "e4", "e2e4", _FEN, _FEN, reasonings[0]),
        _move(2, "black", "e5", "e7e5", _FEN, _FEN, reasonings[1]),
        _move(3, "white", "Qh5", "d1h5", _FEN, _FEN, reasonings[2]),
    ]
    game = GameRecord(
        id="game-1",
        created_at=datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc),
        players={
            "white": _player("gpt-4o", "openai", "GPT-4o"),
            "black": _player("claude-opus-4-8", "anthropic", "Claude Opus 4.8"),
        },
        moves=moves,
        result=result,
        termination=termination,
    )
    return game


def _parse(pgn_text: str) -> chess.pgn.Game:
    parsed = chess.pgn.read_game(io.StringIO(pgn_text))
    assert parsed is not None
    return parsed


def test_seven_tag_roster_is_present():
    pgn = build_pgn(_game(result="1-0", termination="checkmate"))
    parsed = _parse(pgn)
    h = parsed.headers
    assert h["Event"] == "LLM Chess Arena"
    assert h["Date"] == "2026.06.09"
    assert h["Round"] == "1"
    assert h["White"] == "GPT-4o"
    assert h["Black"] == "Claude Opus 4.8"
    assert h["Result"] == "1-0"


def test_service_tags_carry_model_and_provider_no_secrets():
    pgn = build_pgn(_game(termination="resign"))
    h = _parse(pgn).headers
    assert h["Termination"] == "resign"
    assert h["WhiteModel"] == "gpt-4o"
    assert h["BlackModel"] == "claude-opus-4-8"
    assert h["WhiteProvider"] == "openai"
    assert h["BlackProvider"] == "anthropic"
    # Никаких ключей в выводе (D-003).
    assert "api_key" not in pgn.lower() and "sk-" not in pgn


def test_moves_render_as_san_in_order():
    pgn = build_pgn(_game())
    parsed = _parse(pgn)
    sans = [node.san() for node in parsed.mainline()]
    assert sans == ["e4", "e5", "Qh5"]


def test_reasoning_becomes_move_comments():
    pgn = build_pgn(_game(reasonings=("захват центра", "симметрия", "ранний ферзь")))
    node = _parse(pgn)
    comments = []
    while node.variations:
        node = node.variation(0)
        comments.append(node.comment)
    assert comments == ["захват центра", "симметрия", "ранний ферзь"]


def test_reasoning_can_be_excluded():
    pgn = build_pgn(_game(reasonings=("a", "b", "c")), include_reasoning=False)
    node = _parse(pgn)
    while node.variations:
        node = node.variation(0)
        assert node.comment == ""


def test_braces_in_reasoning_are_sanitized():
    # Фигурные скобки в рассуждении не должны ломать структуру комментария PGN.
    pgn = build_pgn(_game(reasonings=("план {форк} и mate", "", "")))
    parsed = _parse(pgn)  # перечитывается без ошибок — структура цела
    first = parsed.variation(0)
    assert "{" not in first.comment and "}" not in first.comment
    assert "форк" in first.comment


def test_newlines_in_reasoning_are_collapsed():
    pgn = build_pgn(_game(reasonings=("строка1\nстрока2\n\nстрока3", "", "")))
    first = _parse(pgn).variation(0)
    assert "\n" not in first.comment
    assert first.comment == "строка1 строка2 строка3"


def test_pgn_round_trips_as_a_valid_game():
    pgn = build_pgn(_game(result="1-0", termination="checkmate"))
    parsed = _parse(pgn)
    # Перепроигрывание ходов на чистой доске не падает на легальности.
    board = chess.Board()
    for move in parsed.mainline_moves():
        assert move in board.legal_moves
        board.push(move)
    assert parsed.headers["Result"] == "1-0"


def test_empty_game_produces_headers_only():
    game = _game()
    game.moves = []
    pgn = build_pgn(game)
    parsed = _parse(pgn)
    assert list(parsed.mainline_moves()) == []
    assert parsed.headers["White"] == "GPT-4o"
