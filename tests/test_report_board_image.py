"""Тесты рендера доски в картинку: SVG из FEN/MoveRecord, опц. PNG (D-005)."""

import chess
import pytest

from arena import MoveRecord
from arena.report import (
    DEFAULT_SIZE,
    PngUnavailableError,
    png_available,
    render_board_svg,
    render_move_svg,
    svg_to_png,
)

_START_FEN = chess.STARTING_FEN
# Позиция после 1.e4 — чёрные ходят.
_AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"


def _e4_move() -> MoveRecord:
    return MoveRecord(
        ply=1,
        side="white",
        san="e4",
        uci="e2e4",
        fen_before=_START_FEN,
        fen_after=_AFTER_E4,
        reasoning="контроль центра",
    )


# --- render_board_svg -------------------------------------------------------


def test_render_board_svg_returns_svg_markup():
    svg = render_board_svg(_START_FEN)
    assert svg.lstrip().startswith("<svg")
    assert "</svg>" in svg


def test_render_board_svg_respects_size():
    svg = render_board_svg(_START_FEN, size=512)
    assert 'width="512"' in svg


def test_render_board_svg_default_size_is_used():
    svg = render_board_svg(_START_FEN)
    assert f'width="{DEFAULT_SIZE}"' in svg


def test_render_board_svg_highlights_lastmove():
    # Подсветка последнего хода добавляет заливку клеток e2/e4 (которых нет без неё).
    plain = render_board_svg(_AFTER_E4)
    highlighted = render_board_svg(_AFTER_E4, lastmove_uci="e2e4")
    assert highlighted != plain
    assert len(highlighted) > len(plain)


def test_render_board_svg_lastmove_highlight_is_green():
    # Клетки сыгранного хода подсвечены зелёным (e2/e4 — светлые клетки),
    # а не дефолтным жёлто-оливковым python-chess.
    svg = render_board_svg(_AFTER_E4, lastmove_uci="e2e4")
    assert "#a3d977" in svg
    assert "#cdd16a" not in svg  # дефолтная светлая подсветка
    assert "#aaa23b" not in svg  # дефолтная тёмная подсветка


def test_render_board_svg_marks_check():
    # «Детский мат»: после Qxf7# чёрный король под шахом → клетка короля подсвечена.
    board = chess.Board()
    for san in ["e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6", "Qxf7#"]:
        board.push_san(san)
    svg = render_board_svg(board.fen())
    assert "check" in svg  # python-chess помечает клетку короля градиентом "check"


def test_render_board_svg_orientation_black_flips():
    white_view = render_board_svg(_START_FEN, orientation="white")
    black_view = render_board_svg(_START_FEN, orientation="black")
    assert white_view != black_view


def test_render_board_svg_rejects_invalid_fen():
    with pytest.raises(ValueError):
        render_board_svg("not a fen")


# --- render_move_svg --------------------------------------------------------


def test_render_move_svg_uses_fen_after_and_highlights_move():
    move = _e4_move()
    from_move = render_move_svg(move)
    # Совпадает с прямым рендером позиции после хода с подсветкой этого хода.
    expected = render_board_svg(move.fen_after, lastmove_uci=move.uci)
    assert from_move == expected
    assert from_move.lstrip().startswith("<svg")


def test_render_move_svg_orientation_passes_through():
    move = _e4_move()
    assert render_move_svg(move, orientation="black") == render_board_svg(
        move.fen_after, orientation="black", lastmove_uci=move.uci
    )


# --- PNG (опциональная зависимость cairosvg) --------------------------------


def test_png_unavailable_raises_informative_error():
    if png_available():
        pytest.skip("cairosvg установлен — деградация не проверяется")
    with pytest.raises(PngUnavailableError):
        svg_to_png(render_board_svg(_START_FEN))


@pytest.mark.skipif(not png_available(), reason="cairosvg не установлен")
def test_svg_to_png_produces_png_bytes():
    png = svg_to_png(render_board_svg(_START_FEN))
    assert png[:8] == b"\x89PNG\r\n\x1a\n"  # сигнатура PNG
