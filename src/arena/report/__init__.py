"""Self-contained HTML-отчёт (Jinja2) и рендер доски (SVG/PNG)."""

from arena.report.board_image import (
    DEFAULT_SIZE,
    PngUnavailableError,
    png_available,
    render_board_svg,
    render_move_svg,
    svg_to_png,
)

__all__ = [
    "DEFAULT_SIZE",
    "PngUnavailableError",
    "png_available",
    "render_board_svg",
    "render_move_svg",
    "svg_to_png",
]
