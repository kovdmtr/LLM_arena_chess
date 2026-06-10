"""Тесты прогона турнира ``TournamentRunner`` (Phase 8, бэклог-1).

Фейковые игроки без сети: «чемпион» делает один легальный ход (``e4`` за белых),
«слабак» сразу сдаётся. Кто бы каким цветом ни играл, чемпион всегда побеждает
(слабак-белыми сдаётся первым ходом; слабак-чёрными сдаётся после ``e4``), поэтому
итог детерминирован — удобно проверять расписание, запись результатов, таблицу,
сохранение партий и экспорт артефактов.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

import chess.pgn

from arena.models import LLMResponse, PlayerInfo
from arena.storage import GAME_JSON_NAME, load_game
from arena.tournament import (
    TournamentRunner,
    export_tournament,
    new_tournament_record,
)

_CHAMP = PlayerInfo(model_id="champ", provider="openai", display_name="Champion")
_WEAK = PlayerInfo(model_id="weak", provider="openai", display_name="Weakling")
CLOCK = lambda: datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)  # noqa: E731


class _ChampPlayer:
    """Делает один легальный ход за белых (``e4``); за чёрных ходить не приходится."""

    def __init__(self, info: PlayerInfo):
        self._info = info

    @property
    def info(self) -> PlayerInfo:
        return self._info

    def respond(self, messages) -> LLMResponse:
        return LLMResponse(move="e4", reasoning="advance")


class _ResignPlayer:
    """Сдаётся первым же ходом."""

    def __init__(self, info: PlayerInfo):
        self._info = info

    @property
    def info(self) -> PlayerInfo:
        return self._info

    def respond(self, messages) -> LLMResponse:
        return LLMResponse(resign=True, reasoning="gg")


def _factory(side, info: PlayerInfo):
    return _ChampPlayer(info) if info.model_id == "champ" else _ResignPlayer(info)


def _tournament(double: bool = True):
    return new_tournament_record(
        [_CHAMP, _WEAK],
        tournament_id="t1",
        created_at=CLOCK(),
        double=double,
    )


def test_runner_plays_all_games_and_writes_results_back():
    record = _tournament(double=True)
    outcome = TournamentRunner(
        record, player_factory=_factory, persist=False, clock=CLOCK
    ).run()

    assert len(outcome.records) == 2
    for tgame, played in zip(record.games, outcome.records):
        assert tgame.game_id == played.id  # ссылка проставлена
        assert tgame.result == played.result  # результат скопирован
        assert tgame.result in {"1-0", "0-1"}


def test_champion_tops_the_standings():
    record = _tournament(double=True)
    outcome = TournamentRunner(
        record, player_factory=_factory, persist=False, clock=CLOCK
    ).run()

    standings = outcome.standings
    assert standings.total_games == 2
    assert standings.models[0].model_id == "champ"

    champ = next(r for r in standings.models if r.model_id == "champ")
    weak = next(r for r in standings.models if r.model_id == "weak")
    assert champ.wins == 2 and champ.losses == 0
    assert weak.losses == 2 and weak.wins == 0
    assert champ.points == 2.0 and weak.points == 0.0


def test_default_game_ids_are_sequential():
    record = _tournament(double=True)
    TournamentRunner(
        record, player_factory=_factory, persist=False, clock=CLOCK
    ).run()
    assert [g.game_id for g in record.games] == ["t1-g01", "t1-g02"]


def test_persist_writes_each_game_to_disk(tmp_path):
    record = _tournament(double=True)
    TournamentRunner(
        record,
        player_factory=_factory,
        games_root=str(tmp_path),
        persist=True,
        clock=CLOCK,
    ).run()

    for tgame in record.games:
        game_json = tmp_path / tgame.game_id / GAME_JSON_NAME
        assert game_json.is_file()
        loaded = load_game(game_json)
        assert loaded.result == tgame.result


def test_custom_game_id_factory_is_used():
    record = _tournament(double=False)
    TournamentRunner(
        record,
        player_factory=_factory,
        persist=False,
        clock=CLOCK,
        game_id_factory=lambda tg, i: f"custom-{i}",
    ).run()
    assert record.games[0].game_id == "custom-0"


def test_export_tournament_writes_artifacts(tmp_path):
    record = _tournament(double=True)
    outcome = TournamentRunner(
        record, player_factory=_factory, persist=False, clock=CLOCK
    ).run()

    out = export_tournament(outcome, tmp_path / "t1", title="Кубок")

    standings_html = (out / "standings.html").read_text(encoding="utf-8")
    assert "Кубок" in standings_html and "Champion" in standings_html

    pgn_text = (out / "tournament.pgn").read_text(encoding="utf-8")
    stream = io.StringIO(pgn_text)
    assert chess.pgn.read_game(stream) is not None
    assert chess.pgn.read_game(stream) is not None  # обе партии в файле

    assert (out / "tournament.json").is_file()


def test_single_participant_has_no_games():
    record = new_tournament_record(
        [_CHAMP], tournament_id="solo", created_at=CLOCK()
    )
    outcome = TournamentRunner(
        record, player_factory=_factory, persist=False, clock=CLOCK
    ).run()
    assert outcome.records == []
    assert outcome.standings.total_games == 0
