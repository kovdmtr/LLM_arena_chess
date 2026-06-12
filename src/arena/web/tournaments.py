"""★ Управление веб-турнирами: фоновый прогон ``TournamentRunner`` и реестр.

Аналог ``GameManager`` для турниров. Турнир — пакетная задача (много партий по
расписанию round-robin), поэтому ``TournamentManager`` запускает его в **фоновом
потоке**: ``TournamentRunner.run()`` по ходу проставляет ``game_id``/``result`` в
партии расписания (``TournamentRecord.games`` мутируется на месте), так что страница
турнира видит прогресс «вживую» — какие партии уже сыграны и текущую таблицу.

По завершении сохраняются артефакты турнира (``tournament.json`` + ``standings.html``
+ ``tournament.pgn``) в ``<games_root>/tournaments/<id>/`` через
``tournament.export_tournament``; отдельные партии пишет сам ``TournamentRunner``
(``games/<id>/``), как и одиночные.

Построение игроков вынесено в ``player_factory`` (шов для тестов: фейковые игроки без
сети). Дефолтная фабрика резолвит модель по каталогу и создаёт провайдера. ★ Движок и
пост-анализ подключаются теми же параметрами, что у ``GameManager``.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from arena.arena import ModelPlayer
from arena.config import AnalysisConfig, ModelCatalog
from arena.models import PlayerInfo, PlayerSettings, Side
from arena.obs import get_logger
from arena.providers import create_provider
from arena.stats import StatsTable, aggregate_stats
from arena.storage import DEFAULT_GAMES_ROOT, StorageError
from arena.tournament import (
    TournamentRecord,
    TournamentRunner,
    export_tournament,
    new_tournament_record,
)
from arena.web.games import STATUS_ERROR, STATUS_FINISHED, STATUS_RUNNING

_log = get_logger("web")

# Подпапка с артефактами турниров внутри games_root.
TOURNAMENTS_DIRNAME = "tournaments"
_TOURNAMENT_JSON = "tournament.json"

# Игрок строится фабрикой по стороне и участнику (``PlayerInfo`` без секретов, D-003).
TournamentPlayerFactory = Callable[[Side, PlayerInfo], object]
Clock = Callable[[], datetime]
EngineFactory = Callable[[], object | None]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class TournamentSession:
    """Состояние одного фонового турнира: запись (мутируется раннером), статус, таблица."""

    id: str
    record: TournamentRecord
    status: str = STATUS_RUNNING
    standings: StatsTable | None = None
    error: str | None = None
    _done: threading.Event = field(default_factory=threading.Event, repr=False)

    def join(self, timeout: float | None = None) -> bool:
        """Дождаться завершения турнира (для тестов/выключения)."""
        return self._done.wait(timeout)

    @property
    def done(self) -> bool:
        return self._done.is_set()

    @property
    def played(self) -> int:
        """Сколько партий расписания уже сыграно (есть результат)."""
        return sum(1 for g in self.record.games if g.result is not None)

    @property
    def total(self) -> int:
        return len(self.record.games)


@dataclass(frozen=True)
class TournamentInfo:
    """Краткая карточка турнира для списка ``GET /tournaments``."""

    id: str
    participants: list[str]
    double: bool
    status: str
    played: int
    total: int
    live: bool
    created_at: datetime


class TournamentManager:
    """Реестр и планировщик фоновых турниров (аналог ``GameManager``)."""

    def __init__(
        self,
        *,
        player_factory: TournamentPlayerFactory | None = None,
        catalog: ModelCatalog | None = None,
        games_root: str = DEFAULT_GAMES_ROOT,
        persist: bool = True,
        clock: Clock = _utcnow,
        engine_factory: EngineFactory | None = None,
        analysis_config: AnalysisConfig | None = None,
        analysis_depth: int | None = None,
        player_settings: PlayerSettings | None = None,
        max_plies: int | None = None,
    ) -> None:
        # ``player_factory`` — шов для тестов; без него строим реальных игроков по
        # каталогу (резолв ключа + провайдер). ``catalog`` обязателен в этом случае.
        self._player_factory = player_factory or self._default_player_factory
        self._catalog = catalog
        self._games_root = games_root
        self._persist = persist
        self._clock = clock
        self._engine_factory = engine_factory
        self._analysis_config = analysis_config
        self._analysis_depth = analysis_depth
        self._player_settings = player_settings
        self._max_plies = max_plies
        self._sessions: dict[str, TournamentSession] = {}
        self._lock = threading.Lock()

    def _default_player_factory(self, side: Side, info: PlayerInfo) -> ModelPlayer:
        """Реальный игрок: резолв модели по каталогу + провайдер (нужен ``catalog``)."""
        if self._catalog is None:
            raise RuntimeError("TournamentManager без catalog требует player_factory")
        return ModelPlayer(create_provider(self._catalog.resolve(info.model_id)))

    @property
    def sessions(self) -> list[TournamentSession]:
        with self._lock:
            return list(self._sessions.values())

    def get(self, tournament_id: str) -> TournamentSession | None:
        with self._lock:
            return self._sessions.get(tournament_id)

    def start(
        self,
        participants: list[PlayerInfo],
        *,
        double: bool = False,
        tournament_id: str | None = None,
    ) -> TournamentSession:
        """Создать турнир из участников и запустить его в фоновом потоке."""
        tournament_id = tournament_id or f"t-{uuid.uuid4().hex[:10]}"
        record = new_tournament_record(
            participants,
            tournament_id=tournament_id,
            created_at=self._clock(),
            double=double,
        )
        session = TournamentSession(id=tournament_id, record=record)
        with self._lock:
            self._sessions[tournament_id] = session
        _log.info(
            "tournament started",
            extra={
                "tournament_id": tournament_id,
                "participants": [p.model_id for p in participants],
                "games": len(record.games),
            },
        )
        thread = threading.Thread(target=self._run, args=(session,), daemon=True)
        thread.start()
        return session

    def _run(self, session: TournamentSession) -> None:
        """Фоновая работа: проиграть расписание, посчитать таблицу, сохранить артефакты."""
        try:
            outcome = TournamentRunner(
                session.record,
                player_factory=self._player_factory,
                games_root=self._games_root,
                persist=self._persist,
                clock=self._clock,
                engine_factory=self._engine_factory,
                analysis_config=self._analysis_config,
                analysis_depth=self._analysis_depth,
                player_settings=self._player_settings,
                max_plies=self._max_plies,
            ).run()
            session.standings = outcome.standings
            if self._persist:
                export_tournament(
                    outcome,
                    Path(self._games_root) / TOURNAMENTS_DIRNAME / session.id,
                )
            session.status = STATUS_FINISHED
            _log.info(
                "tournament finished",
                extra={"tournament_id": session.id, "games": session.total},
            )
        except Exception as exc:  # noqa: BLE001 — любой сбой турнира виден в сессии
            session.status = STATUS_ERROR
            session.error = str(exc)
            _log.error(
                "tournament failed",
                extra={"tournament_id": session.id},
                exc_info=True,
            )
        finally:
            session._done.set()

    def list_tournaments(self) -> list[TournamentInfo]:
        """Карточки турниров: идущие/завершённые из памяти + сохранённые на диске."""
        infos: dict[str, TournamentInfo] = {}
        for session in self.sessions:
            infos[session.id] = _info_from_session(session)
        root = Path(self._games_root) / TOURNAMENTS_DIRNAME
        if root.is_dir():
            for child in sorted(root.iterdir()):
                if child.name in infos or not (child / _TOURNAMENT_JSON).is_file():
                    continue
                record = _load_record_file(child / _TOURNAMENT_JSON)
                if record is not None:
                    infos[record.id] = _info_from_record(record)
        return sorted(
            infos.values(), key=lambda t: (not t.live, -t.created_at.timestamp())
        )

    def load_record(self, tournament_id: str) -> TournamentRecord | None:
        """Запись турнира: из памяти (живой) или с диска; ``None`` если нет."""
        session = self.get(tournament_id)
        if session is not None:
            return session.record
        try:
            path = (
                Path(self._games_root)
                / TOURNAMENTS_DIRNAME
                / _safe_id(tournament_id)
                / _TOURNAMENT_JSON
            )
        except StorageError:
            return None
        if not path.is_file():
            return None
        return _load_record_file(path)

    def load_standings(self, tournament_id: str) -> StatsTable | None:
        """Итоговая таблица турнира: из памяти или пересчётом из записи (по сыгранным)."""
        session = self.get(tournament_id)
        if session is not None and session.standings is not None:
            return session.standings
        record = self.load_record(tournament_id)
        if record is None:
            return None
        return aggregate_stats(_played_records(record, self._games_root))


def _info_from_session(session: TournamentSession) -> TournamentInfo:
    return TournamentInfo(
        id=session.id,
        participants=[p.display_name for p in session.record.participants],
        double=session.record.double,
        status=session.status,
        played=session.played,
        total=session.total,
        live=not session.done,
        created_at=session.record.created_at,
    )


def _info_from_record(record: TournamentRecord) -> TournamentInfo:
    played = sum(1 for g in record.games if g.result is not None)
    return TournamentInfo(
        id=record.id,
        participants=[p.display_name for p in record.participants],
        double=record.double,
        status=STATUS_FINISHED,
        played=played,
        total=len(record.games),
        live=False,
        created_at=record.created_at,
    )


def _load_record_file(path: Path) -> TournamentRecord | None:
    """Прочитать ``TournamentRecord`` из файла; ``None`` при ошибке (битый/нет)."""
    try:
        return TournamentRecord.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _played_records(record: TournamentRecord, games_root: str):
    """Загрузить сыгранные ``GameRecord`` турнира с диска (для пересчёта таблицы)."""
    from arena.storage import load_game

    records = []
    for game in record.games:
        if game.game_id is None:
            continue
        try:
            records.append(load_game(Path(games_root) / game.game_id))
        except StorageError:
            continue
    return records


def _safe_id(tournament_id: str) -> str:
    """Проверить ``id`` как безопасный сегмент пути (анти-traversal)."""
    if (
        not tournament_id
        or tournament_id in {".", ".."}
        or "/" in tournament_id
        or "\\" in tournament_id
    ):
        raise StorageError(f"некорректный id турнира: {tournament_id!r}")
    return tournament_id
