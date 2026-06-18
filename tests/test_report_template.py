"""Тесты HTML-отчёта (Jinja2): шапка, ходы, доски, рассуждения, итог."""

from datetime import datetime, timezone

import chess

from arena import (
    AnalysisSummary,
    GameRecord,
    HintRecord,
    MoveRecord,
    PlayerAnalysis,
    PlayerInfo,
)
from arena.report import render_report_html

_SCHOLARS_MATE = ["e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6", "Qxf7#"]


def _game(
    sans=_SCHOLARS_MATE,
    *,
    result="1-0",
    termination="checkmate",
    reasonings=None,
    white=("gpt-x", "openai", "GPT"),
    black=("claude-x", "anthropic", "Claude"),
) -> GameRecord:
    """``GameRecord`` из SAN-ходов (согласованные uci/fen через python-chess)."""
    board = chess.Board()
    moves = []
    for index, san in enumerate(sans, start=1):
        move = board.parse_san(san)
        fen_before = board.fen()
        uci = move.uci()
        board.push(move)
        moves.append(
            MoveRecord(
                ply=index,
                side="white" if index % 2 == 1 else "black",
                san=san,
                uci=uci,
                fen_before=fen_before,
                fen_after=board.fen(),
                reasoning=(reasonings[index - 1] if reasonings else f"ход {san}"),
            )
        )
    return GameRecord(
        id="g-report",
        created_at=datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc),
        players={
            "white": PlayerInfo(model_id=white[0], provider=white[1], display_name=white[2]),
            "black": PlayerInfo(model_id=black[0], provider=black[1], display_name=black[2]),
        },
        moves=moves,
        result=result,
        termination=termination,
    )


# --- структура и шапка ------------------------------------------------------


def test_report_is_html_document():
    html = render_report_html(_game())
    assert html.lstrip().startswith("<!DOCTYPE html>")
    assert "</html>" in html


def test_report_header_shows_players_and_models():
    html = render_report_html(_game())
    assert "GPT" in html and "Claude" in html
    assert "gpt-x" in html and "claude-x" in html
    assert "openai" in html and "anthropic" in html


def test_report_shows_result_and_termination():
    html = render_report_html(_game(result="1-0", termination="checkmate"))
    assert "Победа белых" in html
    assert "1-0" in html
    assert "checkmate" in html


def test_report_draw_result_text():
    html = render_report_html(_game(["e4", "e5"], result="1/2-1/2", termination="stalemate"))
    assert "Ничья" in html


# --- ходы и рассуждения -----------------------------------------------------


def test_report_lists_all_moves_in_san():
    html = render_report_html(_game())
    for san in _SCHOLARS_MATE:
        assert san in html


def test_report_includes_reasoning_text():
    html = render_report_html(_game(reasonings=["развиваю центр"] + [""] * 6))
    assert "развиваю центр" in html


def test_report_marks_empty_reasoning():
    html = render_report_html(_game(["e4"], reasonings=[""]))
    assert "без объяснения" in html


# --- доски (inline SVG) -----------------------------------------------------


def test_report_embeds_board_svgs_by_default():
    html = render_report_html(_game())
    assert "<svg" in html
    # По одной доске на ход + стартовая позиция (кадр 0 плеера).
    assert html.count("<svg") == len(_SCHOLARS_MATE) + 1


def test_report_can_omit_boards():
    html = render_report_html(_game(), include_boards=False)
    assert "<svg" not in html
    # Ходы при этом всё равно перечислены.
    assert "Qxf7#" in html


# --- интерактивный плеер (одна доска + перемотка ходов) ---------------------


def test_report_renders_replay_player():
    html = render_report_html(_game())
    # Контейнер плеера и элементы навигации (шаг назад/вперёд + слайдер).
    assert 'id="replay"' in html
    assert 'data-nav="prev"' in html
    assert 'data-nav="next"' in html
    assert 'class="replay-slider"' in html
    # Кнопки «в начало/в конец» убраны.
    assert 'data-nav="first"' not in html
    assert 'data-nav="last"' not in html
    # Встроенный JS навигации (self-contained, без сети).
    assert "function show(frame)" in html


def test_report_move_list_is_paired():
    # Ходы идут парами: строка пары + ячейки с data-frame.
    html = render_report_html(_game(["e4", "e5", "Nf3"]))
    assert 'class="mv-row"' in html
    assert 'class="mv-cell"' in html
    # У нечётного числа ходов последняя строка добивается пустой ячейкой.
    assert 'class="mv-cell empty"' in html


def test_report_player_has_start_frame_and_one_board_per_move():
    html = render_report_html(_game())
    # Кадр 0 — стартовая позиция, далее по кадру на каждый ход.
    assert 'data-frame="0"' in html
    assert html.count('class="frame-board') == len(_SCHOLARS_MATE) + 1
    # Слайдер охватывает все ходы (max = число полуходов).
    assert 'max="{}"'.format(len(_SCHOLARS_MATE)) in html


def test_report_player_move_list_is_navigable():
    html = render_report_html(_game(["e4", "e5"]))
    # Список ходов — кликабельные кадры (data-frame на каждом ходе).
    assert 'class="replay-moves"' in html
    assert 'data-frame="1"' in html
    assert 'data-frame="2"' in html


def test_report_move_cells_are_colored_by_classification():
    # Каждый размеченный ход несёт класс оценки (g-<class>) → CSS красит его цветом.
    game = _game(["e4", "e5", "Bc4"])
    game.moves[0].classification = "brilliant"
    game.moves[1].classification = "blunder"
    game.moves[2].classification = "normal"
    html = render_report_html(game)
    assert 'class="mv-cell g-brilliant"' in html
    assert 'class="mv-cell g-blunder"' in html
    assert 'class="mv-cell g-normal"' in html  # просто ход тоже помечен (нейтральный цвет)
    # CSS определяет цвета классов (включая синий для блестящего).
    assert ".g-brilliant { color: #1d4ed8; }" in html


def test_report_player_without_boards_keeps_navigation():
    html = render_report_html(_game(["e4", "e5"]), include_boards=False)
    # Без досок плеер всё равно перематывает ходы (детали + список), но без SVG.
    assert "<svg" not in html
    assert 'class="frame-board' not in html
    assert 'class="replay-moves"' in html
    assert 'data-nav="next"' in html


# --- бейджи ★ (классификация / оценка) появляются только при наличии --------


def test_report_omits_badges_without_analysis():
    html = render_report_html(_game(["e4"]))
    # Нет отрендеренных бейджей/оценки (само слово badge есть в CSS — проверяем элементы).
    assert '<span class="badge' not in html
    assert "cp</span>" not in html


def test_report_shows_classification_and_eval_when_present():
    game = _game(["e4"])
    game.moves[0].classification = "blunder"
    game.moves[0].engine_eval_cp = -250
    html = render_report_html(game)
    assert "blunder" in html
    assert "-250 cp" in html


def test_report_shows_chesscom_glyphs_for_classifications():
    # глифы-аннотации рядом с per-move бейджами.
    game = _game()
    game.moves[0].classification = "brilliant"
    game.moves[-1].classification = "blunder"
    html = render_report_html(game)
    assert 'class="glyph"' in html
    assert "!!" in html  # brilliant
    assert "??" in html  # blunder


def test_report_omits_glyph_for_unmarked_moves():
    # без классификации — ни бейджа, ни глифа.
    html = render_report_html(_game(["e4"]))
    assert 'class="glyph"' not in html


# --- сводка пост-анализа ★ (AnalysisSummary) -------------------------------


def test_report_omits_analysis_summary_without_analysis():
    html = render_report_html(_game(["e4"]))
    assert "Анализ партии" not in html
    assert "точность" not in html


def test_report_shows_analysis_summary_when_present():
    game = _game(["e4", "e5"])
    game.analysis = AnalysisSummary(
        white=PlayerAnalysis(accuracy=1.0, blunders=0, mistakes=0, inaccuracies=1),
        black=PlayerAnalysis(accuracy=0.5, blunders=2, mistakes=1, inaccuracies=0),
    )
    html = render_report_html(game)
    assert "Анализ партии" in html
    # Точность как проценты по обеим сторонам.
    assert "100%" in html
    assert "50%" in html
    # Счётчики ошибок чёрных.
    assert "2 зевков" in html
    assert "1 ошибок" in html


def test_report_shows_dash_for_missing_accuracy():
    game = _game(["e4"])
    game.analysis = AnalysisSummary(white=PlayerAnalysis(accuracy=None))
    html = render_report_html(game)
    assert "Анализ партии" in html
    assert "—" in html


def test_report_shows_hint_when_present():
    game = _game(["e4"])
    game.moves[0].hint = HintRecord(best_move="d2d4", eval_cp=20)
    html = render_report_html(game)
    assert "d2d4" in html
    assert "Подсказка" in html


# --- безопасность: пользовательский текст экранируется ----------------------


def test_report_escapes_html_in_reasoning():
    html = render_report_html(_game(["e4"], reasonings=["<script>alert(1)</script>"]))
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_report_escapes_html_in_player_name():
    html = render_report_html(_game(["e4"], white=("m", "openai", "<b>Hacker</b>")))
    assert "<b>Hacker</b>" not in html
    assert "&lt;b&gt;Hacker" in html


def test_report_has_no_secrets():
    html = render_report_html(_game()).lower()
    assert "api_key" not in html
    assert "sk-" not in html


# --- фича «стратегия»: подписанные блоки «мысли модели» / «план» ------------


def test_report_shows_labeled_thoughts_and_plan_blocks():
    game = _game(["e4"])
    game.moves[0].reasoning = "Хочу захватить центр"
    game.moves[0].strategy = "Захватить центр и рокировать"
    game.moves[0].plan_status = "adapt"
    html = render_report_html(game)
    # Мысли модели и план — в отдельных подписанных блоках.
    assert "Мысли модели" in html
    assert "Хочу захватить центр" in html
    assert "План" in html
    assert "Захватить центр и рокировать" in html
    assert 'class="detail-block plan-block"' in html
    # Статус-бейдж убран (мешал восприятию): ни рендера, ни CSS-класса.
    assert "plan-status" not in html
    assert "status-adapt" not in html


def test_report_omits_plan_block_when_strategy_empty():
    html = render_report_html(_game(["e4"]))  # strategy="" по умолчанию
    # Блок плана не рендерится (строка plan-block есть только в CSS),
    # блок мыслей — всегда есть.
    assert 'class="detail-block plan-block"' not in html
    assert "Мысли модели" in html


def test_report_escapes_html_in_strategy():
    game = _game(["e4"])
    game.moves[0].strategy = "<b>evil</b>"
    html = render_report_html(game)
    assert "<b>evil</b>" not in html
    assert "&lt;b&gt;evil" in html


# --- кнопка «Скачать PGN» (self-contained) ----------------------------------


def test_report_has_download_pgn_button():
    html = render_report_html(_game())
    assert 'id="download-pgn"' in html
    assert "Скачать PGN" in html
    # имя файла = <id>.pgn, безопасно сериализовано в JS.
    assert '"g-report.pgn"' in html


def test_report_embeds_pgn_inline():
    html = render_report_html(_game())
    assert 'id="pgn-data"' in html
    # В отчёт встроен именно PGN (теги партии); без сети/внешних файлов.
    assert "[Event " in html
    assert "[White " in html
    assert "[Result " in html
    assert "<img" not in html  # self-contained


def test_report_embedded_pgn_matches_build_pgn():
    from markupsafe import escape

    from arena.core import build_pgn

    game = _game()
    html = render_report_html(game)
    expected = build_pgn(game, event="LLM Chess Arena")
    # Внутри <textarea> PGN HTML-экранирован — сверяем экранированную форму.
    assert str(escape(expected)) in html


# --- ссылка «На главную» -----------------------------------------------------


def test_report_shows_home_link_when_url_given():
    html = render_report_html(_game(), home_url="/")
    assert 'href="/"' in html
    assert "На главную" in html


def test_report_has_no_home_link_by_default():
    # Без home_url (например, offline-файл отчёта) ссылки на сайт нет.
    html = render_report_html(_game())
    assert "На главную" not in html
