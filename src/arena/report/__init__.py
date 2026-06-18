"""Self-contained HTML-отчёт (Jinja2) и рендер доски (SVG/PNG)."""

from arena.report.animation import (
    SQUARE_FRACTION,
    move_animation,
    piece_svg,
    piece_svgs,
)
from arena.report.board_image import (
    DEFAULT_SIZE,
    PngUnavailableError,
    png_available,
    render_board_svg,
    render_move_svg,
    svg_to_png,
)
from arena.report.stats_template import render_stats_html
from arena.report.template import render_report_html

__all__ = [
    "DEFAULT_SIZE",
    "PngUnavailableError",
    "SQUARE_FRACTION",
    "move_animation",
    "piece_svg",
    "piece_svgs",
    "png_available",
    "render_board_svg",
    "render_move_svg",
    "render_report_html",
    "render_stats_html",
    "svg_to_png",
]
