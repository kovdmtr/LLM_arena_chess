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

Нелегальный/нераспознанный ход обрабатывается по D-006: попытка фиксируется в
``IllegalAttempt``, модели возвращается коррекция (причина + легальные ходы) через
``context(retry=...)``, и она ходит заново. ``illegal_move_retries`` нелегальных
попыток подряд на одном ходу → техническое поражение (``termination=
technical_loss``); счётчик попыток локален ходу и сбрасывается после успешного
хода. Удачные попытки складываются в ``MoveRecord.illegal_attempts``.

Границы этой задачи. Заявленная сдача (``resign``) и проставление
``result``/``termination`` для **обычных** окончаний (мат/пат/ничьи из
``Board.outcome``) вынесены в следующую задачу Phase 3
(``feat(arena): game end and result/termination``); пока ``resign`` поднимает
``GameRunnerError``, а после обычного окончания ``result`` остаётся ``"*"``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime

from arena.arena.player import ModelPlayer
from arena.core import Board, MoveParseError, ParsedMove, parse_move
from arena.models import (
    GameRecord,
    IllegalAttempt,
    LLMResponse,
    MessageRecord,
    MoveRecord,
    PlayerSettings,
    Side,
)
from arena.prompts import context_message, system_message

# Типы событий игрового цикла. Это часть контракта с потребителями (live-просмотр,
# CLI, тесты), поэтому значения стабильны.
EVENT_GAME_START = "game_start"
EVENT_TURN_START = "turn_start"
EVENT_ILLEGAL = "illegal_attempt"
EVENT_MOVE = "move"
EVENT_GAME_OVER = "game_over"

_SIDES: tuple[Side, Side] = ("white", "black")

# PGN-результат при поражении стороны (победа соперника).
_LOSS_RESULT: dict[Side, str] = {"white": "0-1", "black": "1-0"}


class GameRunnerError(RuntimeError):
    """Игровой цикл не может продолжиться корректно.

    В этой задаче поднимается только на ветке заявленной сдачи (``resign``) —
    её обработка реализуется следующей задачей Phase 3. Кооперативные игроки её
    не вызывают.
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
    ) -> None:
        """Создать раннер на паре игроков и ``GameRecord``.

        ``board`` — стартовая позиция (по умолчанию новая партия); режим заявляемых
        ничьих (D-012) задаётся на самой доске вызывающим. ``on_event`` — колбэк для
        событий цикла. ``max_plies`` — защитный предел числа полуходов (``None`` —
        без предела; партия и так конечна по правилам ничьих).
        """
        self._players = dict(players)
        self._game = game
        self._board = board if board is not None else Board()
        self._on_event = on_event
        self._max_plies = max_plies
        # Статичный системный промпт под лимиты партии (D-019) — один на всю игру.
        self._system_message = system_message(
            hints_per_player=game.settings.hints_per_player,
            illegal_move_retries=game.settings.illegal_move_retries,
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
        с учётом D-012) или техническим поражением (``termination`` уже выставлен) —
        и пока не достигнут ``max_plies``. ``result``/``termination`` для обычных
        окончаний здесь не проставляются (задача финализации); техническое поражение
        проставляет их само.
        """
        self._emit(
            EVENT_GAME_START,
            {"fen": self._board.fen(), "to_move": self._board.turn},
        )
        while not self._is_over():
            if self._max_plies is not None and len(self._game.moves) >= self._max_plies:
                break
            self._play_turn()
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
        while True:
            response = self._query(side, retry)
            if response.resign:
                # Обработка сдачи — следующая задача Phase 3 (финализация результата).
                raise GameRunnerError(
                    f"{side} заявил сдачу — обработка resign в этой задаче не реализована"
                )

            parsed, rejected = self._resolve_move(response)
            if parsed is not None:
                return self._apply_move(side, parsed, response, attempts)

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

    def _query(self, side: Side, retry: IllegalAttempt | None) -> LLMResponse:
        """Спросить модель за ``side`` (опц. с коррекцией ``retry``); залогировать диалог.

        Модель видит самодостаточный срез ``[system, context]``; в ``GameRecord``
        пишется per-side история (system один раз, затем пары context/assistant).
        """
        history = self._game.messages[side]
        if not history:  # системную реплику логируем один раз на сторону
            history.append(self._system_message)
        context = context_message(self._game, self._board, retry=retry)
        history.append(context)

        response = self._players[side].respond([self._system_message, context])
        history.append(
            MessageRecord(role="assistant", content=response.model_dump_json())
        )
        return response

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
    ) -> MoveRecord:
        """Применить ход к доске и дописать ``MoveRecord`` в лог; испустить событие.

        ``attempts`` — нелегальные попытки, предшествовавшие этому (легальному) ходу;
        они сохраняются в ``MoveRecord.illegal_attempts`` (спека 3.5).
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
            illegal_attempts=attempts,
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

    def _emit(self, event_type: str, payload: dict) -> None:
        """Передать событие в ``on_event`` (если задан)."""
        if self._on_event is not None:
            self._on_event(GameEvent(type=event_type, payload=payload))
