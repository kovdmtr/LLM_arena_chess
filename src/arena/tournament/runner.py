"""★ Прогон турнира: играем расписание, считаем таблицу, рендерим отчёт (Phase 8).

``TournamentRunner`` берёт ``TournamentRecord`` с расписанием (``round_robin``) и
проигрывает каждую пару обычным ``GameRunner``-ом — синхронно, по очереди (в отличие
от веб-партий, турнир гоняется как пакетная задача). После каждой партии в
``TournamentGame`` проставляются ``game_id`` и ``result``; сыгранные ``GameRecord``-ы
сворачиваются в ``StatsTable`` (через слой ``stats``) — это и есть итоговая таблица.

Построение игроков вынесено в ``player_factory`` (шов для тестов): по
``(side, PlayerInfo)`` он возвращает игрока (утиный тип ``ModelPlayer`` — ``.info`` +
``.respond``). В продакшене фабрика резолвит модель по каталогу и создаёт провайдера;
в тестах — отдаёт скриптованного игрока без сети.

★ Движок (подсказки/пост-анализ) опционален и подключается тем же путём, что в веб
(``engine_factory`` → открытый Stockfish или ``None``; деградация D-008/D-009).
``export_tournament`` пишет итоговые артефакты: ``tournament.json`` (с результатами),
``standings.html`` (таблица) и ``tournament.pgn`` (все партии одним файлом).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from arena.analysis import ClassificationThresholds, analyze_game
from arena.arena import GameRunner, new_game_record
from arena.config import AnalysisConfig
from arena.engine import EngineUnavailableError
from arena.models import GameRecord, PlayerInfo, PlayerSettings, Side
from arena.stats import StatsTable, aggregate_stats
from arena.storage import (
    DEFAULT_GAMES_ROOT,
    export_combined_pgn,
    export_pgn,
    export_report,
    export_stats_report,
    save_game,
)
from arena.tournament.models import TournamentGame, TournamentRecord

# Игрок строится фабрикой по стороне и участнику (``PlayerInfo`` без секретов, D-003).
PlayerFactory = Callable[[Side, PlayerInfo], object]
Clock = Callable[[], datetime]
# Id партии из пары и её порядкового номера (детерминизм/уникальность в каталоге).
GameIdFactory = Callable[[TournamentGame, int], str]
# Движок на партию: открытый Stockfish (★) или ``None`` (деградация, D-008).
EngineFactory = Callable[[], object | None]

# Имена итоговых артефактов турнира внутри его папки.
TOURNAMENT_JSON_NAME = "tournament.json"
STANDINGS_NAME = "standings.html"
TOURNAMENT_PGN_NAME = "tournament.pgn"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class TournamentOutcome:
    """Итог прогона: обновлённая запись турнира, таблица и сыгранные партии."""

    record: TournamentRecord
    standings: StatsTable
    records: list[GameRecord]


class TournamentRunner:
    """Синхронный прогон расписания турнира + подсчёт итоговой таблицы.

    Каждая партия из ``record.games`` играется ``GameRunner``-ом; результат и
    ``game_id`` записываются обратно в ``TournamentGame``. По окончании
    ``aggregate_stats`` сворачивает сыгранные партии в ``StatsTable``.
    """

    def __init__(
        self,
        record: TournamentRecord,
        *,
        player_factory: PlayerFactory,
        games_root: str = DEFAULT_GAMES_ROOT,
        max_plies: int | None = None,
        persist: bool = True,
        clock: Clock = _utcnow,
        game_id_factory: GameIdFactory | None = None,
        engine_factory: EngineFactory | None = None,
        analysis_config: AnalysisConfig | None = None,
        analysis_depth: int | None = None,
        player_settings: PlayerSettings | None = None,
    ) -> None:
        self._record = record
        self._player_factory = player_factory
        self._games_root = games_root
        self._max_plies = max_plies
        self._persist = persist
        self._clock = clock
        self._game_id_factory = game_id_factory or self._default_game_id
        self._engine_factory = engine_factory
        self._analysis_config = analysis_config
        self._analysis_depth = analysis_depth
        # Срез настроек партии (лимиты/флаги, в т.ч. фича «стратегия»); ``None`` →
        # дефолтные ``PlayerSettings`` (стратегия включена по умолчанию).
        self._player_settings = player_settings

    def _default_game_id(self, tgame: TournamentGame, index: int) -> str:
        """Стабильный id партии: ``<tournament>-g<NN>`` (порядок в расписании)."""
        return f"{self._record.id}-g{index + 1:02d}"

    def run(self) -> TournamentOutcome:
        """Проиграть всё расписание и вернуть итог (запись + таблица + партии)."""
        participants: Mapping[str, PlayerInfo] = {
            p.model_id: p for p in self._record.participants
        }
        records: list[GameRecord] = []
        for index, tgame in enumerate(self._record.games):
            record = self._play_one(tgame, index, participants)
            tgame.game_id = record.id
            tgame.result = record.result
            records.append(record)
        standings = aggregate_stats(records)
        return TournamentOutcome(
            record=self._record, standings=standings, records=records
        )

    def _play_one(
        self,
        tgame: TournamentGame,
        index: int,
        participants: Mapping[str, PlayerInfo],
    ) -> GameRecord:
        """Сыграть одну пару и (при ``persist``) сохранить артефакты партии."""
        players = {
            "white": self._player_factory("white", participants[tgame.white]),
            "black": self._player_factory("black", participants[tgame.black]),
        }
        game_id = self._game_id_factory(tgame, index)
        record = new_game_record(
            players,  # type: ignore[arg-type]  # утиный тип игрока (.info/.respond)
            game_id=game_id,
            created_at=self._clock(),
            settings=self._player_settings,
        )
        engine = self._engine_factory() if self._engine_factory else None
        try:
            GameRunner(
                players,  # type: ignore[arg-type]
                record,
                max_plies=self._max_plies,
                engine=engine,  # type: ignore[arg-type]
            ).play()
            self._analyze(record, engine)
            if self._persist:
                save_game(record, games_root=self._games_root)
                export_pgn(record, games_root=self._games_root)
                export_report(record, games_root=self._games_root)
        finally:
            if engine is not None:
                engine.close()  # type: ignore[attr-defined]
        return record

    def _analyze(self, record: GameRecord, engine: object | None) -> None:
        """★ Пост-анализ партии движком (D-009), если движок и анализ включены."""
        if (
            engine is None
            or self._analysis_config is None
            or not self._analysis_config.enabled
        ):
            return
        try:
            record.analysis = analyze_game(
                record,
                engine,  # type: ignore[arg-type]
                thresholds=ClassificationThresholds.from_config(self._analysis_config),
                depth=self._analysis_depth,
            )
        except EngineUnavailableError:
            pass  # движок отвалился в анализе — без разметки, артефакты валидны


def export_tournament(
    outcome: TournamentOutcome,
    out_dir: str | Path,
    *,
    title: str | None = None,
) -> Path:
    """Записать итоговые артефакты турнира в ``out_dir`` и вернуть путь к папке.

    Пишет ``tournament.json`` (запись с результатами), ``standings.html`` (таблица
    через ``report.render_stats_html``) и ``tournament.pgn`` (все партии одним
    файлом). Папка создаётся при необходимости.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    heading = title or f"Турнир {outcome.record.id}"

    (out / TOURNAMENT_JSON_NAME).write_text(
        outcome.record.model_dump_json(indent=2), encoding="utf-8"
    )
    export_stats_report(outcome.standings, out / STANDINGS_NAME, title=heading)
    export_combined_pgn(outcome.records, out / TOURNAMENT_PGN_NAME)
    return out
