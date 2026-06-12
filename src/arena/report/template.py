"""Сборка self-contained HTML-отчёта из ``GameRecord`` через Jinja2.

Отчёт — производный артефакт из ``game.json`` (D-004): шапка (игроки/итог),
сводка пост-анализа (★ ``AnalysisSummary``: точность и счётчики ошибок по сторонам
+ ключевые моменты, если заполнена), интерактивный плеер партии (одна доска +
перемотка ходов: кнопки/слайдер/клавиши/клик по ходу) с панелью текущего хода
(рассуждение, бейджи классификации/оценки ★, подсказка). Доски — inline SVG
(``board_image``), навигация — встроенным JS, поэтому HTML самодостаточен (внешних
файлов и сети нет).

Публичное:

- ``render_report_html`` — собрать строку HTML из ``GameRecord``.

Запись в файл (``report.html``) — задача следующего шага (слой ``storage``/CLI);
здесь только генерация строки, чтобы её было удобно тестировать.
"""

from __future__ import annotations

from jinja2 import Environment, PackageLoader, select_autoescape
from markupsafe import Markup

from arena.analysis import classification_glyph
from arena.core import build_pgn
from arena.models import GameRecord
from arena.report.board_image import DEFAULT_SIZE, render_board_svg, render_move_svg

# Имя шаблона отчёта внутри ``templates/``.
_TEMPLATE_NAME = "report.html.j2"

# Человекочитаемый итог по PGN-результату.
_RESULT_TEXT = {
    "1-0": "Победа белых",
    "0-1": "Победа чёрных",
    "1/2-1/2": "Ничья",
    "*": "Партия не завершена",
}

# Единый Jinja-Environment с автоэкранированием HTML (SVG помечается safe явно).
_ENV = Environment(
    loader=PackageLoader("arena.report", "templates"),
    autoescape=select_autoescape(["html", "html.j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)
# Фильтр для аннотационных глифов классификации (``blunder`` → ``??`` и т.п.).
_ENV.filters["glyph"] = classification_glyph


def _move_views(game: GameRecord, *, include_boards: bool, board_size: int, orientation):
    """Подготовить по-ходовую модель для шаблона (номер хода + inline SVG доски)."""
    views = []
    for record in game.moves:
        board_svg = None
        if include_boards:
            # SVG доверенный (сгенерирован нами) — помечаем safe, чтобы не экранировать.
            board_svg = Markup(
                render_move_svg(record, size=board_size, orientation=orientation)
            )
        views.append(
            {
                "record": record,
                # Номер хода в записи (1. для белых, тот же номер с «...» для чёрных).
                "move_number": (record.ply + 1) // 2,
                "board_svg": board_svg,
            }
        )
    return views


def render_report_html(
    game: GameRecord,
    *,
    event: str = "LLM Chess Arena",
    include_boards: bool = True,
    board_size: int = DEFAULT_SIZE,
    orientation: str = "white",
) -> str:
    """Собрать строку HTML-отчёта из ``game``.

    Доски рисуются с точки зрения ``orientation`` и встраиваются как inline SVG
    (``include_boards=False`` отключает их — полезно для лёгких отчётов/тестов).
    Сводка анализа, а также бейджи классификации и оценки появляются только если
    заполнены пост-анализом (``game.analysis`` / поля ``MoveRecord``).
    """
    # Стартовая позиция — кадр 0 плеера (одна доска + перемотка ходов). Берём FEN
    # до первого хода, чтобы доска совпадала с записью; без ходов плеера нет.
    start_board = None
    if include_boards and game.moves:
        start_board = Markup(
            render_board_svg(
                game.moves[0].fen_before, size=board_size, orientation=orientation
            )
        )

    # PGN встраивается в отчёт (а не тянется по сети), чтобы кнопка «Скачать PGN»
    # работала и на сайте, и в сохранённом offline-отчёте (self-contained, D-013).
    pgn = build_pgn(game, event=event)

    template = _ENV.get_template(_TEMPLATE_NAME)
    return template.render(
        game=game,
        event=event,
        white=game.players["white"],
        black=game.players["black"],
        date=game.created_at.strftime("%Y-%m-%d %H:%M UTC"),
        result_text=_RESULT_TEXT.get(game.result, game.result),
        moves=_move_views(
            game,
            include_boards=include_boards,
            board_size=board_size,
            orientation=orientation,
        ),
        start_board=start_board,
        board_size=board_size,
        pgn=pgn,
        pgn_filename=f"{game.id}.pgn",
    )
