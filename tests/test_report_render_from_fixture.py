"""Smoke-тест рендера отчёта: ``export_report`` пишет self-contained ``report.html``.

Отличие от ``test_report_template.py``: там проверяется строка ``render_report_html``;
здесь — что именно **файл** ``games/<id>/report.html``, записанный слоем ``storage``
из ``GameRecord`` (фикстура «детского мата»), самодостаточен и согласован с записью
(D-004, D-013).
"""

from datetime import datetime, timezone

import chess
import pytest

from arena import GameRecord, MoveRecord, PlayerInfo
from arena.storage import (
    GAME_JSON_NAME,
    REPORT_NAME,
    StorageError,
    export_report,
    load_game,
    save_game,
)

# Классический «детский мат»: 1.e4 e5 2.Bc4 Nc6 3.Qh5 Nf6?? 4.Qxf7#.
_SCHOLARS_MATE = ["e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6", "Qxf7#"]


def _record(game_id: str = "g-report") -> GameRecord:
    """``GameRecord`` из SAN-ходов (согласованные uci/fen через python-chess)."""
    board = chess.Board()
    moves = []
    for index, san in enumerate(_SCHOLARS_MATE, start=1):
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
                reasoning=f"ход {san}",
            )
        )
    return GameRecord(
        id=game_id,
        created_at=datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc),
        players={
            "white": PlayerInfo(model_id="gpt-x", provider="openai", display_name="GPT"),
            "black": PlayerInfo(
                model_id="claude-x", provider="anthropic", display_name="Claude"
            ),
        },
        moves=moves,
        result="1-0",
        termination="checkmate",
    )


def test_export_report_writes_html_in_id_folder(tmp_path):
    target = export_report(_record("g-001"), games_root=tmp_path)
    assert target == tmp_path / "g-001" / REPORT_NAME
    assert target.is_file()


def test_exported_report_is_self_contained_html(tmp_path):
    target = export_report(_record(), games_root=tmp_path)
    html = target.read_text(encoding="utf-8")

    assert html.lstrip().startswith("<!DOCTYPE html>")
    assert "</html>" in html
    # Доски встроены как inline SVG (D-013) — внешних файлов нет.
    assert "<svg" in html
    assert "<img" not in html


def test_exported_report_shows_players_moves_and_result(tmp_path):
    html = export_report(_record(), games_root=tmp_path).read_text(encoding="utf-8")

    assert "GPT" in html and "Claude" in html
    assert "Qxf7" in html  # последний ход — мат
    assert "Победа белых" in html


def test_export_report_can_omit_boards(tmp_path):
    target = export_report(_record("g-light"), games_root=tmp_path, include_boards=False)
    html = target.read_text(encoding="utf-8")
    assert "<svg" not in html
    assert "Qxf7" in html  # ходы остаются даже без картинок


def test_export_report_sits_alongside_game_json(tmp_path):
    save_game(_record("g-001"), games_root=tmp_path)
    export_report(_record("g-001"), games_root=tmp_path)
    folder = tmp_path / "g-001"
    assert (folder / GAME_JSON_NAME).is_file()
    assert (folder / REPORT_NAME).is_file()


def test_export_report_leaves_no_tmp_file(tmp_path):
    export_report(_record("g-001"), games_root=tmp_path)
    assert list((tmp_path / "g-001").glob("*.tmp")) == []


def test_export_report_validates_id_from_record(tmp_path):
    bad = _record()
    bad.id = "../escape"
    with pytest.raises(StorageError):
        export_report(bad, games_root=tmp_path)


def test_exported_report_has_no_secrets(tmp_path):
    html = export_report(_record(), games_root=tmp_path).read_text(encoding="utf-8")
    assert "api_key" not in html


def test_report_renders_after_save_load_round_trip(tmp_path):
    # game.json — источник истины: пишем, читаем обратно, из загруженной записи
    # рендерим отчёт, и он самодостаточен (D-004).
    original = _record("g-rt")
    save_game(original, games_root=tmp_path)
    loaded = load_game(tmp_path / "g-rt")
    html = export_report(loaded, games_root=tmp_path).read_text(encoding="utf-8")
    assert html.lstrip().startswith("<!DOCTYPE html>")
    assert "Qxf7" in html
