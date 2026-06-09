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

Границы этой задачи (один коммит = одна задача). Раннер ведёт **happy path**:
кооперативные игроки присылают легальные ходы. Намеренно НЕ реализованы здесь и
вынесены в следующие задачи Phase 3:

- ретрай нелегального хода и техническое поражение (D-006) —
  ``feat(arena): illegal move retry and technical loss``;
- проставление ``result``/``termination`` и обработка ``resign`` —
  ``feat(arena): game end and result/termination``.

Пока этих веток нет, нелегальный/пустой ход и заявленная сдача поднимают
``GameRunnerError`` — явный шов, который следующие задачи заменят корректной
обработкой. После окончания партии раннер возвращает ``GameRecord`` с ходами;
``result`` остаётся ``"*"`` до задачи финализации.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime

from arena.arena.player import ModelPlayer
from arena.core import Board, MoveParseError, ParsedMove, parse_move
from arena.models import (
    GameRecord,
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
EVENT_MOVE = "move"
EVENT_GAME_OVER = "game_over"

_SIDES: tuple[Side, Side] = ("white", "black")


class GameRunnerError(RuntimeError):
    """Игровой цикл не может продолжиться корректно.

    В этой задаче поднимается на ветках, реализуемых следующими задачами Phase 3
    (нелегальный/пустой ход — ретрай и техническое поражение D-006; заявленная
    сдача — финализация результата). Кооперативные игроки её не вызывают.
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

        Цикл идёт, пока партия не окончена (``Board.is_game_over`` с учётом D-012)
        и не достигнут ``max_plies``. ``result``/``termination`` здесь не проставляются
        (задача финализации) — раннер возвращает запись с накопленными ходами.
        """
        self._emit(
            EVENT_GAME_START,
            {"fen": self._board.fen(), "to_move": self._board.turn},
        )
        while not self._board.is_game_over():
            if self._max_plies is not None and len(self._game.moves) >= self._max_plies:
                break
            self._play_turn()
        self._emit(
            EVENT_GAME_OVER,
            {"fen": self._board.fen(), "plies": len(self._game.moves)},
        )
        return self._game

    def _play_turn(self) -> MoveRecord:
        """Провести один полуход: запрос модели → легальный ход → запись."""
        side: Side = self._board.turn  # type: ignore[assignment]
        player = self._players[side]
        self._emit(
            EVENT_TURN_START,
            {
                "side": side,
                "ply": len(self._game.moves) + 1,
                "fen": self._board.fen(),
            },
        )

        history = self._game.messages[side]
        if not history:  # системную реплику логируем один раз на сторону
            history.append(self._system_message)
        context = context_message(self._game, self._board)
        history.append(context)

        # Модель видит самодостаточный срез: статичный system + текущий контекст.
        response = player.respond([self._system_message, context])
        history.append(
            MessageRecord(role="assistant", content=response.model_dump_json())
        )

        parsed = self._resolve_move(side, response)
        return self._apply_move(side, parsed, response)

    def _resolve_move(self, side: Side, response: LLMResponse) -> ParsedMove:
        """Превратить ответ модели в легальный ход или поднять ``GameRunnerError``.

        Это шов для следующих задач Phase 3: ретрай нелегального хода и техническое
        поражение (D-006), обработка ``resign`` (финализация результата). Пока их нет
        — соответствующие ветки поднимают ошибку.
        """
        if response.resign:
            raise GameRunnerError(
                f"{side} заявил сдачу — обработка resign в этой задаче не реализована"
            )
        if response.move is None:
            raise GameRunnerError(
                f"{side} не дал ход — ретрай/техническое поражение (D-006) "
                "реализуются следующей задачей"
            )
        try:
            return parse_move(self._board, response.move)
        except MoveParseError as exc:
            raise GameRunnerError(
                f"{side} прислал нелегальный ход {response.move!r}: {exc.reason} — "
                "ретрай/техническое поражение (D-006) реализуются следующей задачей"
            ) from exc

    def _apply_move(
        self, side: Side, parsed: ParsedMove, response: LLMResponse
    ) -> MoveRecord:
        """Применить ход к доске и дописать ``MoveRecord`` в лог; испустить событие."""
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

    def _emit(self, event_type: str, payload: dict) -> None:
        """Передать событие в ``on_event`` (если задан)."""
        if self._on_event is not None:
            self._on_event(GameEvent(type=event_type, payload=payload))
