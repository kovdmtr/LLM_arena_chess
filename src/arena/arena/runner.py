"""GameRunner: главный игровой цикл арены — чередование сторон, ведение
``Board``+``GameRecord``, события.

Это «сердце» Phase 3. Раннер собирает вместе ранее построенные слои:

- ``ModelPlayer`` (по одному на сторону) — источник ходов;
- ``prompts.system``/``prompts.context`` — сообщения, которые видит модель;
- ``core.Board`` — позиция и легальность (D-005);
- ``core.parse_move`` — извлечение хода из ответа;
- ``GameRecord`` — канонический лог (D-004), куда пишутся ходы и сообщения.

На каждом полуходе сторона, чья очередь, получает **самодостаточный** контекст
``[system, context]`` (контекст уже несёт FEN, легальные ходы, PGN и объяснения
обеих сторон — спека 3.6), отвечает по протоколу D-007, и её легальный ход
применяется к доске и записывается в ``GameRecord``. Параллельно раннер
испускает события (``on_event``) — их позже потребляет live-просмотр (Phase 6).

Подсказки движка (★, D-010). Если в ответе ``request_hint: true`` и у стороны
остался лимит подсказок (``hints_per_player`` минус израсходованное) и подключён
движок, раннер тратит одну подсказку: ``engine.best_move(fen)`` → ``HintRecord``,
и **перезапрашивает** ход с инъекцией подсказки в контекст. Подсказка остаётся в
контексте до конца этого полухода (в т.ч. при ретраях нелегального хода) и
записывается в итоговый ``MoveRecord`` (``hint_used``/``hint``). На один полуход
выдаётся не более одной подсказки: повторный ``request_hint`` в том же ходу
игнорируется (бюджет не «прожигается» на одной позиции, цикл ограничен). Если
движка нет или лимит исчерпан — запрос подсказки игнорируется (подсказка не
тратится), ход обрабатывается обычным порядком.

Нелегальный/нераспознанный ход обрабатывается по D-006: попытка фиксируется в
``IllegalAttempt``, модели возвращается коррекция (причина + легальные ходы) через
``context(retry=...)``, и она ходит заново. ``illegal_move_retries`` нелегальных
попыток подряд на одном ходу → техническое поражение (``termination=
technical_loss``); счётчик попыток локален ходу и сбрасывается после успешного
хода. Удачные попытки складываются в ``MoveRecord.illegal_attempts``.

Окончание партии (D-020). После остановки цикла ``result``/``termination``
проставляются из ``Board.outcome()`` для обычных исходов (мат, пат, ничьи —
с учётом D-012); коды повторения сводятся к ``repetition``. Технические исходы
(техническое поражение, сдача) фиксируются сразу в момент события и не
перезаписываются. ``resign: true`` в ответе (D-007) — добровольная сдача:
``termination=resign``, победа соперника. Если партия оборвана по ``max_plies``,
``result`` остаётся ``"*"``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from arena.arena.player import ModelPlayer
from arena.core import Board, MoveParseError, ParsedMove, parse_move
from arena.engine import EngineUnavailableError
from arena.models import (
    GameRecord,
    HintRecord,
    IllegalAttempt,
    LLMResponse,
    MessageRecord,
    MoveRecord,
    PlayerSettings,
    Side,
)
from arena.prompts import context_message, system_message


class HintEngine(Protocol):
    """Минимальный контракт движка для подсказок (★, D-010): лучший ход по FEN.

    Раннеру достаточно ``best_move`` — этого хватает и реальному
    ``StockfishEngine``, и фейку в тестах. Полный анализ (``evaluate``) нужен
    отдельному слою пост-анализа, не здесь.
    """

    def best_move(self, fen: str) -> HintRecord: ...

# Типы событий игрового цикла. Это часть контракта с потребителями (live-просмотр,
# CLI, тесты), поэтому значения стабильны.
EVENT_GAME_START = "game_start"
EVENT_TURN_START = "turn_start"
EVENT_ILLEGAL = "illegal_attempt"
EVENT_HINT = "hint"
EVENT_MOVE = "move"
EVENT_GAME_OVER = "game_over"

_SIDES: tuple[Side, Side] = ("white", "black")

# PGN-результат при поражении стороны (победа соперника).
_LOSS_RESULT: dict[Side, str] = {"white": "0-1", "black": "1-0"}

# Финализация причины окончания → словарь спеки 5.3 / D-012: оба варианта
# повторения сводятся к ``repetition`` (различие 3-/5-кратного несущественно).
_REPETITION_TERMINATIONS = frozenset({"threefold_repetition", "fivefold_repetition"})


def _normalize_termination(code: str) -> str:
    """Свести код причины окончания к документированному словарю (D-012/D-020)."""
    return "repetition" if code in _REPETITION_TERMINATIONS else code


class GameRunnerError(RuntimeError):
    """Неустранимая ошибка оркестрации игрового цикла.

    Зарезервированный тип ошибки раннера для будущих неустранимых ситуаций
    (например, отказ движка при обязательной подсказке). На штатных путях —
    нелегальный ход, сдача, обычное окончание — не поднимается.
    """


@dataclass(frozen=True)
class GameEvent:
    """Событие игрового цикла: тип (одна из ``EVENT_*``) и полезная нагрузка."""

    type: str
    payload: dict


def new_game_record(
    players: Mapping[Side, ModelPlayer],
    *,
    game_id: str,
    created_at: datetime,
    settings: PlayerSettings | None = None,
) -> GameRecord:
    """Построить пустой ``GameRecord`` из пары игроков (DRY для CLI/web/тестов).

    ``players`` — игроки по сторонам (``"white"``/``"black"``); их несекретное
    описание (``ModelPlayer.info``, D-003) кладётся в ``players`` записи. ``game_id``
    и ``created_at`` задаёт вызывающий (детерминизм в тестах, отсутствие обращения
    к часам внутри раннера).
    """
    return GameRecord(
        id=game_id,
        created_at=created_at,
        players={side: players[side].info for side in _SIDES},
        settings=settings if settings is not None else PlayerSettings(),
    )


class GameRunner:
    """Главный игровой цикл: чередует стороны, ведёт ``Board``+``GameRecord``, шлёт события.

    Раннер — чистая оркестрация: позицию и лог ему передаёт вызывающий, часов и
    генерации id внутри нет (детерминируемо для тестов). Системный промпт строится
    один раз из лимитов партии (``settings``) — он статичен в пределах игры (D-019).
    """

    def __init__(
        self,
        players: Mapping[Side, ModelPlayer],
        game: GameRecord,
        *,
        board: Board | None = None,
        on_event: Callable[[GameEvent], None] | None = None,
        max_plies: int | None = None,
        engine: HintEngine | None = None,
    ) -> None:
        """Создать раннер на паре игроков и ``GameRecord``.

        ``board`` — стартовая позиция (по умолчанию новая партия); режим заявляемых
        ничьих (D-012) задаётся на самой доске вызывающим. ``on_event`` — колбэк для
        событий цикла. ``max_plies`` — защитный предел числа полуходов (``None`` —
        без предела; партия и так конечна по правилам ничьих). ``engine`` —
        опциональный движок для подсказок (★, D-010); без него ``request_hint``
        игнорируется (база работает без Stockfish, D-008).
        """
        self._players = dict(players)
        self._game = game
        self._board = board if board is not None else Board()
        self._on_event = on_event
        self._max_plies = max_plies
        self._engine = engine
        # Статичный системный промпт под лимиты партии (D-019) — один на всю игру.
        self._system_message = system_message(
            hints_per_player=game.settings.hints_per_player,
            illegal_move_retries=game.settings.illegal_move_retries,
            include_legal_moves=game.settings.include_legal_moves,
            include_strategy=game.settings.strategy_enabled,
        )

    @property
    def board(self) -> Board:
        """Текущая доска (для наблюдения извне)."""
        return self._board

    @property
    def game(self) -> GameRecord:
        """Ведущийся лог партии."""
        return self._game

    def play(self) -> GameRecord:
        """Доиграть партию из текущей позиции и вернуть заполненный ``GameRecord``.

        Цикл идёт, пока партия не окончена — по правилам доски (``Board.is_game_over``
        с учётом D-012) или зафиксированным исходом (техпоражение/сдача) — и пока не
        достигнут ``max_plies``. По выходе ``_finalize`` проставляет ``result``/
        ``termination`` для обычных окончаний (D-020).
        """
        self._emit(
            EVENT_GAME_START,
            {"fen": self._board.fen(), "to_move": self._board.turn},
        )
        while not self._is_over():
            if self._max_plies is not None and len(self._game.moves) >= self._max_plies:
                break
            self._play_turn()
        self._finalize()
        self._emit(
            EVENT_GAME_OVER,
            {
                "fen": self._board.fen(),
                "plies": len(self._game.moves),
                "result": self._game.result,
                "termination": self._game.termination,
            },
        )
        return self._game

    def _is_over(self) -> bool:
        """Окончена ли партия: по правилам доски или уже зафиксированным исходом."""
        return self._game.termination is not None or self._board.is_game_over()

    def _play_turn(self) -> MoveRecord | None:
        """Провести один полуход с ретраями нелегального хода (D-006).

        Возвращает ``MoveRecord`` при успешном ходе либо ``None``, если ход закончился
        техническим поражением (исчерпан лимит ``illegal_move_retries``).
        """
        side: Side = self._board.turn  # type: ignore[assignment]
        self._emit(
            EVENT_TURN_START,
            {
                "side": side,
                "ply": len(self._game.moves) + 1,
                "fen": self._board.fen(),
            },
        )

        limit = self._game.settings.illegal_move_retries
        attempts: list[IllegalAttempt] = []
        retry: IllegalAttempt | None = None
        hint: HintRecord | None = None  # подсказка, выданная на этом ходу (D-010)
        while True:
            response = self._query(side, retry, hint)
            if response.resign:
                self._resign(side)
                return None

            # Запрос подсказки (★, D-010): не более одной за ход. Если выдана —
            # перезапрашиваем ход с инъекцией подсказки (это не коррекция → retry
            # снимаем); иначе (нет движка/лимита) запрос игнорируем и идём дальше.
            if response.request_hint and hint is None:
                served = self._serve_hint(side)
                if served is not None:
                    hint = served
                    retry = None
                    continue

            parsed, rejected = self._resolve_move(response)
            if parsed is not None:
                return self._apply_move(side, parsed, response, attempts, hint)

            # Нелегальный/нераспознанный ход: фиксируем попытку и просим переходить.
            attempts.append(rejected)
            self._emit(
                EVENT_ILLEGAL,
                {
                    "side": side,
                    "ply": len(self._game.moves) + 1,
                    "attempt": len(attempts),
                    "raw": rejected.raw,
                    "reason": rejected.reason,
                },
            )
            if len(attempts) >= limit:
                self._technical_loss(side, attempts)
                return None
            retry = rejected  # коррекция уйдёт в контекст следующей попытки (D-006)

    def _query(
        self,
        side: Side,
        retry: IllegalAttempt | None,
        hint: HintRecord | None = None,
    ) -> LLMResponse:
        """Спросить модель за ``side`` (опц. с коррекцией ``retry`` и подсказкой ``hint``).

        Модель видит самодостаточный срез ``[system, context]``; в ``GameRecord``
        пишется per-side история (system один раз, затем пары context/assistant).
        ``hint`` (если выдан на этом ходу, D-010) инъектируется в контекст.
        """
        history = self._game.messages[side]
        if not history:  # системную реплику логируем один раз на сторону
            history.append(self._system_message)
        context = context_message(
            self._game,
            self._board,
            retry=retry,
            hint=hint,
            include_legal_moves=self._game.settings.include_legal_moves,
            include_strategy=self._game.settings.strategy_enabled,
        )
        history.append(context)

        response = self._players[side].respond([self._system_message, context])
        history.append(
            MessageRecord(role="assistant", content=response.model_dump_json())
        )
        return response

    def _hints_remaining(self, side: Side) -> int:
        """Остаток подсказок стороны: лимит партии минус израсходованное (не ниже 0)."""
        used = self._game.hints_used.get(side, 0)
        return max(0, self._game.settings.hints_per_player - used)

    def _serve_hint(self, side: Side) -> HintRecord | None:
        """Выдать подсказку движка стороне ``side``, израсходовав одну (★, D-010).

        Возвращает ``HintRecord`` и инкрементирует ``hints_used[side]`` только при
        успешной выдаче. Если движка нет, лимит исчерпан или движок отказал
        (``EngineUnavailableError``) — возвращает ``None`` и подсказку не тратит
        (база работает без Stockfish, D-008).
        """
        if self._engine is None or self._hints_remaining(side) <= 0:
            return None
        try:
            hint = self._engine.best_move(self._board.fen())
        except EngineUnavailableError:
            return None
        self._game.hints_used[side] += 1
        self._emit(
            EVENT_HINT,
            {
                "side": side,
                "ply": len(self._game.moves) + 1,
                "best_move": hint.best_move,
                "eval_cp": hint.eval_cp,
                "mate_in": hint.mate_in,
                "hints_remaining": self._hints_remaining(side),
            },
        )
        return hint

    def _resolve_move(
        self, response: LLMResponse
    ) -> tuple[ParsedMove | None, IllegalAttempt | None]:
        """Распознать ход из ответа.

        Возвращает ``(ParsedMove, None)`` для легального хода, иначе
        ``(None, IllegalAttempt)`` с причиной отклонения для коррекции (D-006).
        Доску не меняет.
        """
        if response.move is None:
            return None, IllegalAttempt(raw="", reason="ход не указан в ответе")
        try:
            parsed = parse_move(self._board, response.move)
        except MoveParseError as exc:
            return None, IllegalAttempt(raw=exc.raw, reason=exc.reason)
        return parsed, None

    def _apply_move(
        self,
        side: Side,
        parsed: ParsedMove,
        response: LLMResponse,
        attempts: list[IllegalAttempt],
        hint: HintRecord | None = None,
    ) -> MoveRecord:
        """Применить ход к доске и дописать ``MoveRecord`` в лог; испустить событие.

        ``attempts`` — нелегальные попытки, предшествовавшие этому (легальному) ходу;
        они сохраняются в ``MoveRecord.illegal_attempts`` (спека 3.5). ``hint`` —
        подсказка, выданная на этом ходу (★, D-010), если была.
        """
        fen_before = self._board.fen()
        self._board.push(parsed.move)
        fen_after = self._board.fen()

        record = MoveRecord(
            ply=len(self._game.moves) + 1,
            side=side,
            san=parsed.san,
            uci=parsed.uci,
            fen_before=fen_before,
            fen_after=fen_after,
            reasoning=response.reasoning,
            # Фича «стратегия»: план, заявленный на этом ходу, и его статус — чтобы
            # вернуть его этой же стороне на следующем ходу (D-025). Пуст/``start``,
            # когда фича выключена или модель план не прислала.
            strategy=response.strategy,
            plan_status=response.plan_status,
            illegal_attempts=attempts,
            hint_used=hint is not None,
            hint=hint,
        )
        self._game.moves.append(record)
        self._emit(
            EVENT_MOVE,
            {
                "side": side,
                "ply": record.ply,
                "san": record.san,
                "uci": record.uci,
                "fen": fen_after,
            },
        )
        return record

    def _technical_loss(self, side: Side, attempts: list[IllegalAttempt]) -> None:
        """Зафиксировать техническое поражение ``side`` (D-006): ``result``/``termination``.

        Ход не сделан (легального так и не пришло); все попытки уже в истории
        сообщений (коррекции и ответы модели) и в событиях ``EVENT_ILLEGAL``.
        Партию завершит ``play``: установленный ``termination`` остановит цикл, а
        итоговый ``EVENT_GAME_OVER`` понесёт ``result``/``termination`` в нагрузке.
        """
        self._game.result = _LOSS_RESULT[side]
        self._game.termination = "technical_loss"

    def _resign(self, side: Side) -> None:
        """Зафиксировать добровольную сдачу ``side`` (D-007): ``result``/``termination``.

        Сдача завершает партию вне зависимости от позиции: ``termination=resign``,
        победа соперника. Цикл остановит установленный ``termination``.
        """
        self._game.result = _LOSS_RESULT[side]
        self._game.termination = "resign"

    def _finalize(self) -> None:
        """Проставить ``result``/``termination`` для обычного окончания (D-020).

        Технические исходы (техпоражение, сдача) уже зафиксированы — не трогаем их.
        Если партия не окончена по правилам доски (обрыв по ``max_plies``) —
        ``result`` остаётся ``"*"``. Коды повторения сводятся к ``repetition``.
        """
        if self._game.termination is not None:
            return
        outcome = self._board.outcome()
        if outcome is None:
            return
        self._game.result = outcome.result
        self._game.termination = _normalize_termination(outcome.termination)

    def _emit(self, event_type: str, payload: dict) -> None:
        """Передать событие в ``on_event`` (если задан)."""
        if self._on_event is not None:
            self._on_event(GameEvent(type=event_type, payload=payload))
