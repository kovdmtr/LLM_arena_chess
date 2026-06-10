"""Тесты агрегированной статистики моделей (Phase 8, бэклог-2).

Строим компактные ``GameRecord``-ы напрямую (без шахматного движка/ходов — для
статистики важны только ``players``/``result``/``analysis``/``hints_used``) и
проверяем свёртку: очки, W/L/D, score%, средняя точность, счётчики ошибок,
подсказки, сортировку и загрузку из каталога.
"""

from __future__ import annotations

from datetime import datetime, timezone

from arena.models import (
    AnalysisSummary,
    GameRecord,
    PlayerAnalysis,
    PlayerInfo,
)
from arena.stats import ModelStats, StatsTable, aggregate_stats, load_records
from arena.storage import save_game

_WHITE = PlayerInfo(model_id="gpt-x", provider="openai", display_name="GPT")
_BLACK = PlayerInfo(model_id="claude-x", provider="anthropic", display_name="Claude")


def _game(
    game_id: str,
    result: str,
    *,
    white: PlayerInfo = _WHITE,
    black: PlayerInfo = _BLACK,
    analysis: AnalysisSummary | None = None,
    hints: dict | None = None,
) -> GameRecord:
    return GameRecord(
        id=game_id,
        created_at=datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc),
        players={"white": white, "black": black},
        result=result,
        analysis=analysis,
        hints_used=hints or {"white": 0, "black": 0},
    )


def _row(table: StatsTable, model_id: str) -> ModelStats:
    return next(r for r in table.models if r.model_id == model_id)


def test_win_loss_draw_and_points():
    table = aggregate_stats(
        [
            _game("g1", "1-0"),  # white побеждает
            _game("g2", "0-1"),  # black побеждает
            _game("g3", "1/2-1/2"),  # ничья
        ]
    )
    assert table.total_games == 3
    white = _row(table, "gpt-x")
    black = _row(table, "claude-x")

    assert (white.wins, white.losses, white.draws) == (1, 1, 1)
    assert (black.wins, black.losses, black.draws) == (1, 1, 1)
    assert white.games == 3 and black.games == 3
    assert white.points == 1.5 and black.points == 1.5  # 1 + 0.5
    assert white.score_pct == 50.0


def test_unfinished_game_is_not_counted_but_model_appears():
    table = aggregate_stats([_game("g1", "*")])
    assert table.total_games == 0
    white = _row(table, "gpt-x")
    assert white.games == 0 and white.points == 0.0
    assert white.score_pct == 0.0
    assert white.avg_accuracy is None


def test_score_pct_and_ordering_by_points():
    # white выигрывает 2 из 2 → 100%; black 0 → 0%. white должен быть выше.
    table = aggregate_stats([_game("g1", "1-0"), _game("g2", "1-0")])
    assert [r.model_id for r in table.models] == ["gpt-x", "claude-x"]
    assert _row(table, "gpt-x").score_pct == 100.0
    assert _row(table, "claude-x").score_pct == 0.0


def test_same_model_both_colors_merges_into_one_row():
    other = PlayerInfo(model_id="gpt-x", provider="openai", display_name="GPT")
    # gpt-x играет за чёрных против себя? нет — против Claude за обе стороны в разных партиях
    table = aggregate_stats(
        [
            _game("g1", "1-0", white=_WHITE, black=_BLACK),  # gpt-x (W) выигрывает
            _game("g2", "1-0", white=_BLACK, black=other),  # gpt-x (B) проигрывает
        ]
    )
    gpt = _row(table, "gpt-x")
    assert gpt.games == 2
    assert gpt.wins == 1 and gpt.losses == 1


def test_analysis_counters_and_average_accuracy():
    a1 = AnalysisSummary(
        white=PlayerAnalysis(accuracy=0.8, blunders=1, mistakes=2, inaccuracies=3),
        black=PlayerAnalysis(accuracy=0.6, blunders=0, mistakes=1, inaccuracies=0),
    )
    a2 = AnalysisSummary(
        white=PlayerAnalysis(accuracy=0.6, blunders=1, mistakes=0, inaccuracies=1),
        black=PlayerAnalysis(accuracy=None),  # нет точности — не входит в среднее
    )
    table = aggregate_stats(
        [_game("g1", "1-0", analysis=a1), _game("g2", "0-1", analysis=a2)]
    )
    white = _row(table, "gpt-x")
    assert white.blunders == 2 and white.mistakes == 2 and white.inaccuracies == 4
    assert white.avg_accuracy == 0.7  # (0.8 + 0.6) / 2

    black = _row(table, "claude-x")
    assert black.avg_accuracy == 0.6  # только одна доступная точность


def test_hints_used_summed_across_sides():
    table = aggregate_stats(
        [
            _game("g1", "1-0", hints={"white": 2, "black": 1}),
            _game("g2", "0-1", hints={"white": 1, "black": 3}),
        ]
    )
    assert _row(table, "gpt-x").hints_used == 3
    assert _row(table, "claude-x").hints_used == 4


def test_empty_records_give_empty_table():
    table = aggregate_stats([])
    assert table.models == [] and table.total_games == 0


def test_table_round_trips_through_json():
    table = aggregate_stats([_game("g1", "1-0")])
    restored = StatsTable.model_validate_json(table.model_dump_json())
    assert restored == table


def test_load_records_reads_saved_games(tmp_path):
    save_game(_game("g1", "1-0"), games_root=tmp_path)
    save_game(_game("g2", "0-1"), games_root=tmp_path)
    (tmp_path / "not-a-game").mkdir()  # папка без game.json — игнор

    records = load_records(games_root=tmp_path)
    assert {r.id for r in records} == {"g1", "g2"}

    table = aggregate_stats(records)
    assert table.total_games == 2


def test_load_records_missing_dir_returns_empty(tmp_path):
    assert load_records(games_root=tmp_path / "nope") == []
