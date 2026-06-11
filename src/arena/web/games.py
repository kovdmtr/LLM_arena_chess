"""★ Управление веб-партиями: фоновый запуск ``GameRunner`` и реестр сессий.

Веб-слой не может играть партию синхронно в обработчике запроса — ходы делаются
LLM-вызовами и партия идёт долго. Поэтому ``GameManager`` запускает каждую партию в
**фоновом потоке**, накапливает события (`GameEvent`) в ``GameSession`` (их читает
live-просмотр по WebSocket) и по окончании сохраняет артефакты (`game.json` + PGN +
HTML-отчёт) через слой ``storage``.

Раннер — чистая оркестрация (см. ``arena.GameRunner``); этот модуль добавляет к нему
жизненный цикл «запустить в фоне, наблюдать, разметить ★, сохранить». Построение
игроков из резолвленных моделей вынесено в ``player_factory`` — это шов для тестов
(подменяемый фейковыми игроками без сети).

★ Движок подключается через ``engine_factory`` (единый путь ``engine.build_engine``):
на партию строится открытый Stockfish **или** ``None``. С движком раннер выдаёт
подсказки (D-010), а по окончании ``analyze_game`` размечает ходы и заполняет
``record.analysis`` (D-009); без движка партия играется на базовом уровне без
подсказок/анализа (деградация D-008). Движок закрывается по завершении партии.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from arena.analysis import ClassificationThresholds, analyze_game
from arena.arena import GameEvent, GameRunner, ModelPlayer, new_game_record
from arena.config import AnalysisConfig, ResolvedModel
from arena.engine import EngineUnavailableError
from arena.models import GameRecord, PlayerInfo, PlayerSettings, Side
from arena.obs import get_logger
from arena.providers import create_provider
from arena.storage import (
    DEFAULT_GAMES_ROOT,
    GAME_JSON_NAME,
    StorageError,
    export_pgn,
    export_report,
    game_dir,
    load_game,
    save_game,
)

_log = get_logger("web")

# Статусы фоновой партии.
STATUS_RUNNING = "running"
STATUS_FINISHED = "finished"
STATUS_ERROR = "error"

_SIDES: tuple[Side, Side] = ("white", "black")

# Игрок — утиный тип: достаточно ``.info`` (несекретное описание) и ``.respond``
# (как у ``ModelPlayer``); раннер больше ничего не требует.
PlayerFactory = Callable[[Side, ResolvedModel], object]
Clock = Callable[[], datetime]
# Фабрика движка на партию: возвращает открытый движок (★ подсказки/анализ) или
# ``None`` (★ отключены/недоступны — единый путь деградации, см. ``engine.build_engine``).
EngineFactory = Callable[[], object | None]


def default_player_factory(side: Side, resolved: ResolvedModel) -> ModelPlayer:
    """Построить реального игрока: провайдер по резолвленной модели + ``ModelPlayer``."""
    return ModelPlayer(create_provider(resolved))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class GameSession:
    """Состояние одной фоновой партии: статус, накопленные события, лог партии.

    ``record`` — тот же ``GameRecord``, что ведёт раннер (мутируется на месте), поэтому
    ``result``/``termination`` читаются «вживую». ``events`` пополняется колбэком раннера
    и служит источником для WebSocket-трансляции (replay уже накопленного + стрим новых).
    """

    id: str
    players: dict[Side, PlayerInfo]
    record: GameRecord
    status: str = STATUS_RUNNING
    events: list[dict] = field(default_factory=list)
    error: str | None = None
    _done: threading.Event = field(default_factory=threading.Event, repr=False)

    def add_event(self, event: GameEvent) -> None:
        """Колбэк раннера: сохранить событие как сериализуемый словарь."""
        self.events.append({"type": event.type, "payload": event.payload})

    def join(self, timeout: float | None = None) -> bool:
        """Дождаться завершения фоновой партии (для тестов/выключения). ``True`` — успели."""
        return self._done.wait(timeout)

    @property
    def done(self) -> bool:
        return self._done.is_set()

    @property
    def result(self) -> str:
        return self.record.result

    @property
    def termination(self) -> str | None:
        return self.record.termination


@dataclass(frozen=True)
class GameInfo:
    """Краткая карточка партии для списка ``GET /games`` (память или диск)."""

    id: str
    white: str
    black: str
    status: str
    result: str
    live: bool
    created_at: datetime


class GameManager:
    """Реестр и планировщик фоновых партий.

    Партии стартуют в потоках-демонах и регистрируются по ``id``; их можно
    перечислить (``sessions``) и получить по ``id`` (``get``). По завершении партии
    артефакты сохраняются в ``games_root`` (если ``persist``).
    """

    def __init__(
        self,
        *,
        player_factory: PlayerFactory = default_player_factory,
        games_root: str = DEFAULT_GAMES_ROOT,
        max_plies: int | None = None,
        persist: bool = True,
        clock: Clock = _utcnow,
        engine_factory: EngineFactory | None = None,
        analysis_config: AnalysisConfig | None = None,
        analysis_depth: int | None = None,
        player_settings: PlayerSettings | None = None,
    ) -> None:
        self._player_factory = player_factory
        self._games_root = games_root
        self._max_plies = max_plies
        self._persist = persist
        self._clock = clock
        # Срез настроек партии из конфига (в т.ч. фича «стратегия»); ``None`` →
        # дефолтные ``PlayerSettings``.
        self._player_settings = player_settings
        # ★ Движок и пост-анализ (Phase 7). ``engine_factory`` строит на партию
        # движок-или-``None`` (единый путь деградации, см. ``engine.build_engine``):
        # ``None`` → партия играется без подсказок/анализа (D-008). ``analysis_config``
        # включает пост-анализ при наличии движка.
        self._engine_factory = engine_factory
        self._analysis_config = analysis_config
        self._analysis_depth = analysis_depth
        self._sessions: dict[str, GameSession] = {}
        self._lock = threading.Lock()

    @property
    def sessions(self) -> list[GameSession]:
        """Сессии в порядке появления (самые новые — в конце)."""
        with self._lock:
            return list(self._sessions.values())

    def get(self, game_id: str) -> GameSession | None:
        """Сессия по ``id`` или ``None``."""
        with self._lock:
            return self._sessions.get(game_id)

    def start(
        self,
        resolved: Mapping[Side, ResolvedModel],
        *,
        game_id: str | None = None,
    ) -> GameSession:
        """Создать партию из резолвленных моделей и запустить её в фоновом потоке.

        ``resolved`` — модели по сторонам (с ключами, уже прошедшие fail-fast в
        каталоге). Игроки строятся через ``player_factory``. Возвращает
        зарегистрированную ``GameSession`` сразу (партия играется в фоне).
        """
        players = {side: self._player_factory(side, resolved[side]) for side in _SIDES}
        game_id = game_id or uuid.uuid4().hex[:12]
        record = new_game_record(
            players,
            game_id=game_id,
            created_at=self._clock(),
            settings=self._player_settings,
        )
        session = GameSession(
            id=game_id, players=dict(record.players), record=record
        )
        with self._lock:
            self._sessions[game_id] = session
        _log.info(
            "game started",
            extra={
                "game_id": game_id,
                "white": record.players["white"].model_id,
                "black": record.players["black"].model_id,
            },
        )
        thread = threading.Thread(
            target=self._run, args=(session, players, record), daemon=True
        )
        thread.start()
        return session

    def list_games(self) -> list[GameInfo]:
        """Карточки всех партий: идущие/завершённые из памяти + сохранённые на диске.

        Память имеет приоритет над диском (живой статус); записи дедуплицируются по
        ``id``. Сортировка: идущие партии первыми, затем по времени создания (новые
        раньше).
        """
        infos: dict[str, GameInfo] = {}
        for session in self.sessions:
            infos[session.id] = GameInfo(
                id=session.id,
                white=session.players["white"].display_name,
                black=session.players["black"].display_name,
                status=session.status,
                result=session.result,
                live=not session.done,
                created_at=session.record.created_at,
            )
        root = Path(self._games_root)
        if root.is_dir():
            for child in sorted(root.iterdir()):
                if child.name in infos or not (child / GAME_JSON_NAME).is_file():
                    continue
                try:
                    record = load_game(child)
                except StorageError:
                    continue
                infos[record.id] = GameInfo(
                    id=record.id,
                    white=record.players["white"].display_name,
                    black=record.players["black"].display_name,
                    status=STATUS_FINISHED,
                    result=record.result,
                    live=False,
                    created_at=record.created_at,
                )
        return sorted(
            infos.values(), key=lambda g: (not g.live, -g.created_at.timestamp())
        )

    def load_record(self, game_id: str) -> GameRecord | None:
        """Вернуть ``GameRecord`` партии: из памяти (живой) или с диска; ``None`` если нет."""
        session = self.get(game_id)
        if session is not None:
            return session.record
        try:
            path = game_dir(game_id, games_root=self._games_root)
        except StorageError:
            return None  # некорректный id (анти-traversal)
        if not (path / GAME_JSON_NAME).is_file():
            return None
        try:
            return load_game(path)
        except StorageError:
            return None

    def _run(
        self, session: GameSession, players: dict[Side, object], record: GameRecord
    ) -> None:
        """Фоновая работа потока: доиграть партию, разметить ★ и сохранить артефакты."""
        # Единый путь деградации (D-008): фабрика отдаёт открытый движок или ``None``;
        # при ``None`` партия идёт без подсказок/анализа, остальное — как обычно.
        engine = self._engine_factory() if self._engine_factory else None
        try:
            runner = GameRunner(
                players,  # type: ignore[arg-type]  # утиный тип игрока
                record,
                max_plies=self._max_plies,
                on_event=session.add_event,
                engine=engine,  # type: ignore[arg-type]  # утиный тип HintEngine
            )
            runner.play()
            self._analyze(record, engine)
            if self._persist:
                save_game(record, games_root=self._games_root)
                export_pgn(record, games_root=self._games_root)
                export_report(record, games_root=self._games_root)
            session.status = STATUS_FINISHED
            _log.info(
                "game finished",
                extra={
                    "game_id": session.id,
                    "result": record.result,
                    "termination": record.termination,
                    "analyzed": record.analysis is not None,
                },
            )
        except Exception as exc:  # noqa: BLE001 — любой сбой партии виден в сессии
            session.status = STATUS_ERROR
            session.error = str(exc)
            # exc_info=True кладёт трейсбек; форматтер замаскирует возможный ключ (D-003).
            _log.error(
                "game failed", extra={"game_id": session.id}, exc_info=True
            )
        finally:
            if engine is not None:
                engine.close()  # type: ignore[attr-defined]
            session._done.set()

    def _analyze(self, record: GameRecord, engine: object | None) -> None:
        """★ Пост-анализ партии движком (D-009), если движок и анализ включены.

        Размечает ходы и заполняет ``record.analysis``. Деградирует мягко: без
        движка/при выключенном анализе — no-op; ``EngineUnavailableError`` в процессе
        → партия остаётся без разметки, но артефакты валидны (D-008).
        """
        if engine is None or self._analysis_config is None or not self._analysis_config.enabled:
            return
        try:
            record.analysis = analyze_game(
                record,
                engine,  # type: ignore[arg-type]  # утиный тип EvalEngine
                thresholds=ClassificationThresholds.from_config(self._analysis_config),
                depth=self._analysis_depth,
            )
        except EngineUnavailableError:
            pass  # движок отвалился в анализе — без разметки, артефакты валидны
