"""Тесты разбора хода из ответа модели: SAN/UCI, нормализация, причины отказа.

Покрывает контракт ``parse_move``: легальные ходы в обеих нотациях, снятие
обёртки вокруг хода, и понятную ``reason`` при пустом/мусорном/неоднозначном/
нелегальном входе. Доска не должна меняться при разборе.
"""

import chess
import pytest

from arena.core import Board, MoveParseError, ParsedMove, parse_move

# --- Легальные ходы и нормализация в (san, uci) ---------------------------


def test_parse_san_legal_normalizes_both_notations():
    board = Board()
    parsed = parse_move(board, "Nf3")
    assert isinstance(parsed, ParsedMove)
    assert parsed.san == "Nf3"
    assert parsed.uci == "g1f3"
    assert parsed.move == chess.Move.from_uci("g1f3")


def test_parse_uci_legal_normalizes_to_san():
    board = Board()
    parsed = parse_move(board, "e2e4")
    assert parsed.san == "e4"
    assert parsed.uci == "e2e4"


def test_parse_does_not_mutate_board():
    board = Board()
    parse_move(board, "e4")
    parse_move(board, "e2e4")
    assert board.fen() == chess.STARTING_FEN
    assert board.turn == "white"


def test_parse_castling_san():
    board = Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    parsed = parse_move(board, "O-O")
    assert parsed.san == "O-O"
    assert parsed.uci == "e1g1"


def test_parse_promotion_uci_lowercase():
    board = Board("8/4P3/8/8/8/8/8/4K2k w - - 0 1")
    parsed = parse_move(board, "e7e8q")
    assert parsed.uci == "e7e8q"
    assert parsed.san == "e8=Q"


# --- Снятие обёртки вокруг хода -------------------------------------------


@pytest.mark.parametrize("raw", ['"e4"', "**Nf3**", "e4.", "  e4  ", "`e2e4`"])
def test_parse_strips_wrapping_noise(raw):
    board = Board()
    parsed = parse_move(board, raw)
    assert parsed.san in {"e4", "Nf3"}


def test_parse_keeps_check_and_mate_markers():
    # Символы шаха/мата — часть SAN, их снимать нельзя.
    board = Board()
    for san in ["f3", "e5", "g4"]:
        board.push_san(san)
    parsed = parse_move(board, "Qh4#")
    assert parsed.san == "Qh4#"


# --- Отказы с понятной причиной -------------------------------------------


@pytest.mark.parametrize("raw", ["", "   ", "\n\t "])
def test_empty_input_rejected(raw):
    board = Board()
    with pytest.raises(MoveParseError, match="пустой ход"):
        parse_move(board, raw)


def test_none_input_rejected():
    board = Board()
    with pytest.raises(MoveParseError, match="пустой ход"):
        parse_move(board, None)


def test_garbage_not_recognized():
    board = Board()
    with pytest.raises(MoveParseError, match="не распознан"):
        parse_move(board, "zz9")


def test_illegal_san_reports_illegal():
    board = Board()
    with pytest.raises(MoveParseError, match="нелегален"):
        parse_move(board, "e5")  # пешка через клетку первым ходом — нелегально


def test_illegal_uci_reports_illegal():
    board = Board()
    with pytest.raises(MoveParseError, match="нелегален"):
        parse_move(board, "e2e5")


def test_ambiguous_san_reports_ambiguity():
    # Оба коня (d2 и f2) ходят на e4 → "Ne4" неоднозначен.
    board = Board("4k3/8/8/8/8/8/3N1N2/4K3 w - - 0 1")
    with pytest.raises(MoveParseError, match="неоднозначный"):
        parse_move(board, "Ne4")


def test_error_preserves_raw():
    board = Board()
    with pytest.raises(MoveParseError) as exc_info:
        parse_move(board, "  garbage??  ")
    assert exc_info.value.raw == "  garbage??  "
    assert exc_info.value.reason


# --- Краевые входы: en passant, регистр UCI, неоднозначность, null-move -----


def test_parse_en_passant_uci_normalizes_to_san():
    # Белая пешка e5 бьёт на проходе чёрную f5 → UCI e5f6, SAN exf6.
    board = Board("rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3")
    parsed = parse_move(board, "e5f6")
    assert parsed.uci == "e5f6"
    assert parsed.san == "exf6"


def test_parse_en_passant_san():
    # Та же позиция, но ход дан в SAN — должен нормализоваться в тот же UCI.
    board = Board("rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3")
    parsed = parse_move(board, "exf6")
    assert parsed.uci == "e5f6"
    assert parsed.san == "exf6"


def test_parse_uci_uppercase_is_normalized():
    # Модель может прислать UCI в верхнем регистре — приводим к нижнему.
    board = Board()
    parsed = parse_move(board, "G1F3")
    assert parsed.uci == "g1f3"
    assert parsed.san == "Nf3"


def test_parse_promotion_uci_uppercase_piece():
    # Буква фигуры в продвижении тоже может прийти заглавной (E7E8Q).
    board = Board("8/4P3/8/8/8/8/8/4K2k w - - 0 1")
    parsed = parse_move(board, "E7E8Q")
    assert parsed.uci == "e7e8q"
    assert parsed.san == "e8=Q"


def test_disambiguation_by_file():
    # Кони d2 и f2 ходят на e4; "Nde4" снимает неоднозначность файлом.
    board = Board("4k3/8/8/8/8/8/3N1N2/4K3 w - - 0 1")
    parsed = parse_move(board, "Nde4")
    assert parsed.uci == "d2e4"
    assert parsed.san == "Nde4"


def test_disambiguation_by_rank():
    # Ладьи a1 и a6 на одной вертикали ходят на a3; уточнение рангом: "R1a3".
    board = Board("4k3/8/R7/8/8/8/8/R3K3 w - - 0 1")
    parsed = parse_move(board, "R1a3")
    assert parsed.uci == "a1a3"
    assert parsed.san == "R1a3"


def test_null_move_rejected():
    # "0000" — формальный null-move в UCI; пропуск хода в шахматах невозможен.
    board = Board()
    with pytest.raises(MoveParseError, match="не распознан"):
        parse_move(board, "0000")


def test_null_move_does_not_mutate_board():
    board = Board()
    with pytest.raises(MoveParseError):
        parse_move(board, "0000")
    assert board.fen() == chess.STARTING_FEN


def test_same_square_uci_reports_illegal():
    # "e2e2" — синтаксически валидный UCI, но это не ход (та же клетка).
    board = Board()
    with pytest.raises(MoveParseError, match="нелегален"):
        parse_move(board, "e2e2")


def test_short_uci_not_recognized():
    # Усечённый UCI (нет клетки назначения) — не SAN и не валидный UCI.
    board = Board()
    with pytest.raises(MoveParseError, match="не распознан"):
        parse_move(board, "e2e")


def test_wrong_case_san_piece_falls_through_to_illegal():
    # "NF3" — не валидный SAN (фигура заглавная, но клетка тоже), и не UCI.
    # Должен дать понятную причину, не молча пройти.
    board = Board()
    with pytest.raises(MoveParseError):
        parse_move(board, "NF3")
