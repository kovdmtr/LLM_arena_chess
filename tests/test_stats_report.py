"""Тесты stats-отчёта и многопартийного PGN (Phase 8, бэклог-2).

Проверяем ``render_stats_html`` (standings-таблица, self-contained, экранирование,
пустой случай) и storage-экспорт: ``export_combined_pgn`` (несколько партий в одном
файле, нумерация раундов, перечитывается python-chess) + ``export_stats_report``.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

import chess
import chess.pgn

from arena.models import (
    AnalysisSummary,
    GameRecord,
    MoveRecord,
    PlayerAnalysis,
    PlayerInfo,
)
from arena.report import render_stats_html
from arena.stats import aggregate_stats
from arena.storage import export_combined_pgn, export_stats_report

_WHITE = PlayerInfo(model_id="gpt-x", provider="openai", display_name="GPT")
_BLACK = PlayerInfo(model_id="claude-x", provider="anthropic", display_name="Claude")


def _played_game(game_id: str, sans: list[str], result: str) -> GameRecord:
    """``GameRecord`` с согласованными uci/fen из списка SAN-ходов (через python-chess)."""
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
            )
        )
    return GameRecord(
        id=game_id,
        created_at=datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc),
        players={"white": _WHITE, "black": _BLACK},
        moves=moves,
        result=result,
        termination="checkmate" if result != "1/2-1/2" else "stalemate",
    )


_SCHOLARS = ["e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6", "Qxf7#"]


# --- render_stats_html ----------------------------------------------------


def test_render_stats_html_is_self_contained_with_rows():
    table = aggregate_stats(
        [_played_game("g1", _SCHOLARS, "1-0"), _played_game("g2", _SCHOLARS, "1-0")]
    )
    html = render_stats_html(table, title="Турнир")

    assert html.lstrip().startswith("<!DOCTYPE html>")
    assert "Турнир" in html
    assert "GPT" in html and "Claude" in html
    assert "Score %" in html  # заголовок таблицы
    assert "<img" not in html  # ничего внешнего
    assert "Учтённых партий: 2" in html


def test_render_stats_html_shows_accuracy_and_dash():
    a = AnalysisSummary(
        white=PlayerAnalysis(accuracy=0.75),
        black=PlayerAnalysis(accuracy=None),
    )
    game = _played_game("g1", _SCHOLARS, "1-0")
    game.analysis = a
    html = render_stats_html(aggregate_stats([game]))

    assert "75.0%" in html  # точность белых
    assert "—" in html  # у чёрных точности нет


def test_render_stats_html_empty_table_placeholder():
    html = render_stats_html(aggregate_stats([]))
    assert "Нет данных" in html
    assert "<table" not in html


def test_render_stats_html_escapes_display_name():
    evil = PlayerInfo(
        model_id="x", provider="p", display_name="<script>alert(1)</script>"
    )
    game = GameRecord(
        id="g1",
        created_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
        players={"white": evil, "black": _BLACK},
        result="1-0",
    )
    html = render_stats_html(aggregate_stats([game]))
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


# --- export_combined_pgn --------------------------------------------------


def test_export_combined_pgn_writes_multiple_games(tmp_path):
    records = [
        _played_game("g1", _SCHOLARS, "1-0"),
        _played_game("g2", _SCHOLARS, "1-0"),
    ]
    target = tmp_path / "all.pgn"
    path = export_combined_pgn(records, target)

    assert path == target
    text = path.read_text(encoding="utf-8")

    # Два отдельных раунда в одном файле.
    assert '[Round "1"]' in text
    assert '[Round "2"]' in text

    # Файл перечитывается python-chess как две последовательные партии.
    stream = io.StringIO(text)
    first = chess.pgn.read_game(stream)
    second = chess.pgn.read_game(stream)
    third = chess.pgn.read_game(stream)
    assert first is not None and second is not None
    assert third is None  # ровно две партии
    assert first.headers["White"] == "GPT"
    assert list(first.mainline_moves())  # ходы доиграны


def test_export_combined_pgn_empty_writes_empty_file(tmp_path):
    target = tmp_path / "none.pgn"
    path = export_combined_pgn([], target)
    assert path.read_text(encoding="utf-8") == ""


# --- export_stats_report --------------------------------------------------


def test_export_stats_report_writes_self_contained_file(tmp_path):
    table = aggregate_stats([_played_game("g1", _SCHOLARS, "1-0")])
    target = tmp_path / "stats.html"
    path = export_stats_report(table, target, title="Итоги")

    assert path == target
    html = path.read_text(encoding="utf-8")
    assert html.lstrip().startswith("<!DOCTYPE html>")
    assert "Итоги" in html and "GPT" in html
    assert not (tmp_path / "stats.html.tmp").exists()  # без временного файла
