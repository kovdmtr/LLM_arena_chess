"""Тесты round-robin расписания и сборки ``TournamentRecord`` (Phase 8, бэклог-1).

Проверяем инварианты круга: каждая пара встречается нужное число раз, число
партий = C(n,2) (×2 при double), нечётное число участников обрабатывается через
bye, цвета примерно сбалансированы, нумерация туров корректна.
"""

from __future__ import annotations

from datetime import datetime, timezone
from itertools import combinations

from arena.models import PlayerInfo
from arena.tournament import (
    TournamentGame,
    TournamentRecord,
    new_tournament_record,
    round_robin,
)


def _unordered(games: list[TournamentGame]) -> list[frozenset]:
    return [frozenset((g.white, g.black)) for g in games]


def test_single_round_robin_each_pair_once():
    games = round_robin(["A", "B", "C", "D"])
    assert len(games) == 6  # C(4,2)
    pairs = _unordered(games)
    for combo in combinations(["A", "B", "C", "D"], 2):
        assert pairs.count(frozenset(combo)) == 1


def test_double_round_robin_each_pair_twice_reversed_colors():
    games = round_robin(["A", "B"], double=True)
    assert len(games) == 2
    # Один и тот же дуэт, но цвета поменялись местами.
    assert {(g.white, g.black) for g in games} == {("A", "B"), ("B", "A")}


def test_odd_number_uses_bye_and_drops_those_games():
    games = round_robin(["A", "B", "C"])
    assert len(games) == 3  # C(3,2); bye-партии отброшены
    assert "__bye__" not in {g.white for g in games}
    assert "__bye__" not in {g.black for g in games}
    pairs = _unordered(games)
    for combo in combinations(["A", "B", "C"], 2):
        assert pairs.count(frozenset(combo)) == 1


def test_fewer_than_two_players_is_empty():
    assert round_robin([]) == []
    assert round_robin(["A"]) == []


def test_round_numbers_are_sequential_and_cover_all():
    games = round_robin(["A", "B", "C", "D"])
    rounds = sorted({g.round_number for g in games})
    assert rounds == [1, 2, 3]  # n-1 туров
    # В каждом туре по 2 партии (n/2).
    for r in rounds:
        assert sum(1 for g in games if g.round_number == r) == 2


def test_double_continues_round_numbering():
    single = round_robin(["A", "B", "C", "D"])
    double = round_robin(["A", "B", "C", "D"], double=True)
    assert max(g.round_number for g in single) == 3
    assert max(g.round_number for g in double) == 6
    assert len(double) == 12


def test_colors_are_balanced_for_each_player():
    games = round_robin(["A", "B", "C", "D"])
    for player in ["A", "B", "C", "D"]:
        whites = sum(1 for g in games if g.white == player)
        blacks = sum(1 for g in games if g.black == player)
        # 3 партии у каждого → разница белых/чёрных не больше одной.
        assert abs(whites - blacks) <= 1


def test_unplayed_games_have_no_result_or_game_id():
    games = round_robin(["A", "B"])
    assert all(g.result is None and g.game_id is None for g in games)


def test_new_tournament_record_schedules_games():
    participants = [
        PlayerInfo(model_id=f"m{i}", provider="p", display_name=f"Model {i}")
        for i in range(4)
    ]
    record = new_tournament_record(
        participants,
        tournament_id="t1",
        created_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
        double=True,
    )
    assert isinstance(record, TournamentRecord)
    assert record.double is True
    assert len(record.participants) == 4
    assert len(record.games) == 12  # двойной круг C(4,2)*2
    # Пары составлены из model_id участников.
    ids = {p.model_id for p in participants}
    for game in record.games:
        assert game.white in ids and game.black in ids


def test_tournament_record_round_trips_through_json():
    participants = [
        PlayerInfo(model_id="a", provider="p", display_name="A"),
        PlayerInfo(model_id="b", provider="p", display_name="B"),
    ]
    record = new_tournament_record(
        participants,
        tournament_id="t1",
        created_at=datetime(2026, 6, 10, tzinfo=timezone.utc),
    )
    restored = TournamentRecord.model_validate_json(record.model_dump_json())
    assert restored == record
