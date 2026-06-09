"""★ Управление веб-партиями: фоновый запуск ``GameRunner`` и реестр сессий.

Веб-слой не может играть партию синхронно в обработчике запроса — ходы делаются
LLM-вызовами и партия идёт долго. Поэтому ``GameManager`` запускает каждую партию в
**фоновом потоке**, накапливает события (`GameEvent`) в ``GameSession`` (их читает
live-просмотр по WebSocket) и по окончании сохраняет артефакты (`game.json` + PGN +
HTML-отчёт) через слой ``storage``.

Раннер — чистая оркестрация (см. ``arena.GameRunner``); этот модуль добавляет к нему
жизненный цикл «запустить в фоне, наблюдать, сохранить». Построение игроков из
резолвленных моделей вынесено в ``player_factory`` — это шов для тестов
(подменяемый фейковыми игроками без сети) и место будущей инъекции движка/подсказок.

Движок (★ подсказки/анализ) в веб-партиях пока не подключён: партии играются на
базовом уровне (без Stockfish, D-008). Подключение движка в веб — задача Phase 7
(`chore: graceful degradation without engine`).
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone

from arena.arena import GameEvent, GameRunner, ModelPlayer, new_game_record
from arena.config import ResolvedModel
from arena.models import GameRecord, PlayerInfo, Side
from arena.providers import create_provider
from arena.storage import DEFAULT_GAMES_ROOT, export_pgn, export_report, save_game

# Статусы фоновой партии.
STATUS_RUNNING = "running"
STATUS_FINISHED = "finished"
STATUS_ERROR = "error"

_SIDES: tuple[Side, Side] = ("white", "black")

# Игрок — утиный тип: достаточно ``.info`` (несекретное описание) и ``.respond``
# (как у ``ModelPlayer``); раннер больше ничего не требует.
PlayerFactory = Callable[[Side, ResolvedModel], object]
Clock = Callable[[], datetime]


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
    ) -> None:
        self._player_factory = player_factory
        self._games_root = games_root
        self._max_plies = max_plies
        self._persist = persist
        self._clock = clock
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
            players, game_id=game_id, created_at=self._clock()
        )
        session = GameSession(
            id=game_id, players=dict(record.players), record=record
        )
        with self._lock:
            self._sessions[game_id] = session
        thread = threading.Thread(
            target=self._run, args=(session, players, record), daemon=True
        )
        thread.start()
        return session

    def _run(
        self, session: GameSession, players: dict[Side, object], record: GameRecord
    ) -> None:
        """Фоновая работа потока: доиграть партию и сохранить артефакты."""
        try:
            runner = GameRunner(
                players,  # type: ignore[arg-type]  # утиный тип игрока
                record,
                max_plies=self._max_plies,
                on_event=session.add_event,
            )
            runner.play()
            if self._persist:
                save_game(record, games_root=self._games_root)
                export_pgn(record, games_root=self._games_root)
                export_report(record, games_root=self._games_root)
            session.status = STATUS_FINISHED
        except Exception as exc:  # noqa: BLE001 — любой сбой партии виден в сессии
            session.status = STATUS_ERROR
            session.error = str(exc)
        finally:
            session._done.set()
