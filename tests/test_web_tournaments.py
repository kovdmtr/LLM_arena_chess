"""Тесты фонового менеджера турниров ``TournamentManager`` (веб-UI турниров).

Фейковые игроки без сети (шов ``player_factory``): «чемпион» делает один ход за
белых, «слабак» сдаётся — чемпион всегда побеждает, итог детерминирован. Проверяем
фоновый прогон, прогресс/таблицу, сохранение артефактов, список (память+диск),
загрузку записи/таблицы и статус ошибки.
"""

from __future__ import annotations

from datetime import datetime, timezone

from arena.models import LLMResponse, PlayerInfo
from arena.web.games import STATUS_ERROR, STATUS_FINISHED
from arena.web.tournaments import TournamentManager

CLOCK = lambda: datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc)  # noqa: E731

_CHAMP = PlayerInfo(model_id="champ", provider="openai", display_name="Champion")
_WEAK = PlayerInfo(model_id="weak", provider="openai", display_name="Weakling")


class _ChampPlayer:
    def __init__(self, info: PlayerInfo):
        self._info = info

    @property
    def info(self) -> PlayerInfo:
        return self._info

    def respond(self, messages) -> LLMResponse:
        return LLMResponse(move="e4", reasoning="advance")


class _ResignPlayer:
    def __init__(self, info: PlayerInfo):
        self._info = info

    @property
    def info(self) -> PlayerInfo:
        return self._info

    def respond(self, messages) -> LLMResponse:
        return LLMResponse(resign=True, reasoning="gg")


def _factory(side, info: PlayerInfo):
    return _ChampPlayer(info) if info.model_id == "champ" else _ResignPlayer(info)


def _manager(tmp_path, *, factory=_factory, persist=True) -> TournamentManager:
    return TournamentManager(
        player_factory=factory,
        games_root=str(tmp_path),
        persist=persist,
        clock=CLOCK,
        engine_factory=lambda: None,
    )


def test_start_runs_in_background_and_finishes(tmp_path):
    manager = _manager(tmp_path)
    session = manager.start([_CHAMP, _WEAK], double=True, tournament_id="t1")
    assert session.join(timeout=10)
    assert session.status == STATUS_FINISHED
    assert session.total == 2 and session.played == 2
    # Таблица посчитана, чемпион первый.
    assert session.standings is not None
    assert session.standings.models[0].model_id == "champ"


def test_results_written_back_into_schedule(tmp_path):
    manager = _manager(tmp_path)
    session = manager.start([_CHAMP, _WEAK], tournament_id="t1")
    session.join(timeout=10)
    for game in session.record.games:
        assert game.result in {"1-0", "0-1"}
        assert game.game_id is not None


def test_persists_tournament_artifacts(tmp_path):
    manager = _manager(tmp_path)
    session = manager.start([_CHAMP, _WEAK], double=True, tournament_id="t1")
    session.join(timeout=10)
    out = tmp_path / "tournaments" / "t1"
    assert (out / "tournament.json").is_file()
    assert (out / "standings.html").is_file()
    assert (out / "tournament.pgn").is_file()
    # Партии турнира тоже сохранены.
    assert (tmp_path / "t1-g01" / "game.json").is_file()


def test_list_includes_memory_and_disk(tmp_path):
    manager = _manager(tmp_path)
    session = manager.start([_CHAMP, _WEAK], tournament_id="t1")
    session.join(timeout=10)

    infos = manager.list_tournaments()
    ids = {t.id for t in infos}
    assert "t1" in ids
    card = next(t for t in infos if t.id == "t1")
    assert card.total == 1 and card.played == 1
    assert "Champion" in card.participants


def test_load_record_and_standings_from_disk(tmp_path):
    # Менеджер 1 играет и сохраняет; менеджер 2 читает с диска (как новый процесс).
    _manager(tmp_path).start([_CHAMP, _WEAK], double=True, tournament_id="t1").join(
        timeout=10
    )
    fresh = _manager(tmp_path)
    record = fresh.load_record("t1")
    assert record is not None and len(record.games) == 2

    standings = fresh.load_standings("t1")
    assert standings is not None
    assert standings.models[0].model_id == "champ"


def test_unknown_tournament_returns_none(tmp_path):
    manager = _manager(tmp_path)
    assert manager.load_record("nope") is None
    assert manager.load_standings("nope") is None
    assert manager.get("nope") is None


def test_failure_sets_error_status(tmp_path):
    def _boom(side, info):
        class _BoomPlayer:
            info = info

            def respond(self, messages):
                raise RuntimeError("provider exploded")

        return _BoomPlayer()

    manager = _manager(tmp_path, factory=_boom)
    session = manager.start([_CHAMP, _WEAK], tournament_id="t1")
    assert session.join(timeout=10)
    assert session.status == STATUS_ERROR
    assert session.error is not None
