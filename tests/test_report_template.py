"""Тесты HTML-отчёта (Jinja2): шапка, ходы, доски, рассуждения, итог."""

from datetime import datetime, timezone

import chess

from arena import (
    AnalysisSummary,
    GameRecord,
    HintRecord,
    KeyMoment,
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
    # По одной доске на ход.
    assert html.count("<svg") == len(_SCHOLARS_MATE)


def test_report_can_omit_boards():
    html = render_report_html(_game(), include_boards=False)
    assert "<svg" not in html
    # Ходы при этом всё равно перечислены.
    assert "Qxf7#" in html


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


def test_report_shows_key_moments():
    game = _game(["e4", "e5", "Bc4"])
    game.analysis = AnalysisSummary(
        key_moments=[
            KeyMoment(ply=1, classification="brilliant", comment="сильный центр"),
            KeyMoment(ply=2, classification="blunder"),
        ]
    )
    html = render_report_html(game)
    assert "brilliant" in html
    assert "blunder" in html
    # Комментарий ключевого момента отображается (и экранируется как обычный текст).
    assert "сильный центр" in html
    # Нумерация: 1-й полуход белых → "1.", 2-й чёрных → "1...".
    assert "1." in html
    assert "1..." in html


def test_report_escapes_html_in_key_moment_comment():
    game = _game(["e4"])
    game.analysis = AnalysisSummary(
        key_moments=[KeyMoment(ply=1, classification="mistake", comment="<i>x</i>")]
    )
    html = render_report_html(game)
    assert "<i>x</i>" not in html
    assert "&lt;i&gt;x" in html


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
