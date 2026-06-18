"""Рендер шахматной доски в картинку для HTML-отчёта (поверх ``python-chess``).

Доска рисуется из FEN в SVG через ``chess.svg`` (D-005): SVG — текст, поэтому он
вставляется прямо в self-contained отчёт без внешних файлов. Опционально SVG можно
конвертировать в PNG через ``cairosvg`` — это **необязательная** зависимость
(extra ``report-png``); при её отсутствии ``svg_to_png`` деградирует понятной
ошибкой ``PngUnavailableError``, а SVG-путь продолжает работать.

Публичное:

- ``render_board_svg`` — SVG позиции из FEN (с подсветкой последнего хода и шаха);
- ``render_move_svg`` — то же из ``MoveRecord`` (позиция после хода, ход подсвечен);
- ``png_available`` / ``svg_to_png`` — опциональная конвертация SVG → PNG.
"""

from __future__ import annotations

import importlib.util

import chess
import chess.svg

from arena.models import MoveRecord, Side

# Размер стороны доски в пикселях по умолчанию.
DEFAULT_SIZE = 360

# Зелёная подсветка последнего хода (вместо дефолтной жёлто-оливковой
# ``python-chess``): сыгранная фигура стоит под зелёной клеткой. Переопределяем
# только клетки хода — остальные цвета берутся из дефолтов ``chess.svg``.
_LASTMOVE_COLORS = {
    "square light lastmove": "#a3d977",
    "square dark lastmove": "#74b34a",
}


class PngUnavailableError(RuntimeError):
    """PNG-рендер недоступен: не установлена опциональная зависимость ``cairosvg``."""


def _orientation_color(orientation: Side) -> chess.Color:
    """Перевести сторону отчёта (``"white"``/``"black"``) в ``chess.Color``."""
    return chess.WHITE if orientation == "white" else chess.BLACK


def render_board_svg(
    fen: str,
    *,
    size: int = DEFAULT_SIZE,
    orientation: Side = "white",
    lastmove_uci: str | None = None,
    coordinates: bool = True,
) -> str:
    """Вернуть SVG-разметку позиции ``fen``.

    ``lastmove_uci`` (если задан) подсвечивает последний ход; шах подсвечивается
    автоматически (клетка короля ходящей стороны). ``orientation`` задаёт, снизу
    какой стороны рисуется доска. Некорректный FEN/UCI поднимет ``ValueError`` из
    ``python-chess``.
    """
    board = chess.Board(fen)
    lastmove = chess.Move.from_uci(lastmove_uci) if lastmove_uci else None
    check = board.king(board.turn) if board.is_check() else None
    return chess.svg.board(
        board,
        size=size,
        orientation=_orientation_color(orientation),
        lastmove=lastmove,
        check=check,
        coordinates=coordinates,
        colors=_LASTMOVE_COLORS,
    )


def render_move_svg(
    move: MoveRecord,
    *,
    size: int = DEFAULT_SIZE,
    orientation: Side = "white",
) -> str:
    """Вернуть SVG позиции **после** хода ``move`` с подсветкой самого хода.

    Удобная обёртка над ``render_board_svg`` для рендера ленты ходов отчёта:
    берёт ``fen_after`` и подсвечивает сыгранный ``uci``.
    """
    return render_board_svg(
        move.fen_after,
        size=size,
        orientation=orientation,
        lastmove_uci=move.uci,
    )


def png_available() -> bool:
    """Установлена ли опциональная зависимость ``cairosvg`` для PNG-рендера."""
    return importlib.util.find_spec("cairosvg") is not None


def svg_to_png(svg: str, *, output_width: int | None = None) -> bytes:
    """Сконвертировать SVG-строку в PNG-байты через ``cairosvg``.

    PNG — опциональный артефакт: при отсутствии ``cairosvg`` (extra ``report-png``)
    поднимается ``PngUnavailableError`` с подсказкой по установке. ``output_width``
    масштабирует результат по ширине (высота — пропорционально).
    """
    if not png_available():
        raise PngUnavailableError(
            "PNG-рендер требует пакет cairosvg; установите extra 'report-png' "
            "(pip install -e '.[report-png]')"
        )
    import cairosvg  # импорт отложен: зависимость опциональна

    return cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=output_width)
