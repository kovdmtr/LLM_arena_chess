"""Тесты GameRunner — главного игрового цикла (Phase 3).

Игроки подменяются детерминированным ``_ScriptedPlayer``: он отдаёт заранее
заданную последовательность ходов (без сети, без провайдера). Проверяем:
чередование сторон и заполнение ``GameRecord`` (ходы, FEN, рассуждения), запись
истории сообщений по сторонам, последовательность событий, защитный ``max_plies``;
ретрай нелегального хода и техническое поражение (D-006); финализацию
``result``/``termination`` для обычных окончаний (мат/пат/ничья) и обработку
``resign`` (D-020); протокол подсказок движка (★, D-010): расход лимита, инъекция
в контекст, запись ``HintRecord``, деградация без движка.
"""

from __future__ import annotations

from datetime import datetime

from arena.arena import (
    EVENT_GAME_OVER,
    EVENT_GAME_START,
    EVENT_HINT,
    EVENT_ILLEGAL,
    EVENT_MOVE,
    EVENT_TURN_START,
    GameEvent,
    GameRunner,
    new_game_record,
)
from arena.arena.runner import _normalize_termination
from arena.core import Board
from arena.engine import EngineUnavailableError
from arena.models import HintRecord, LLMResponse, PlayerInfo, PlayerSettings, Side

CREATED_AT = datetime(2026, 6, 9, 12, 0, 0)


class _ScriptedPlayer:
    """Детерминированный игрок: отдаёт ходы из скрипта по очереди.

    Дублирует утиный контракт ``ModelPlayer`` для раннера: свойство ``info`` и метод
    ``respond`` (возвращает ``LLMResponse``). Фиксирует переданные сообщения в
    ``seen`` — для проверки самодостаточного среза ``[system, context]``.
    """

    def __init__(self, model_id: str, moves, *, resign_after: int | None = None):
        self._info = PlayerInfo(
            model_id=model_id, provider="fake", display_name=model_id.upper()
        )
        self._moves = list(moves)
        self._idx = 0
        self._resign_after = resign_after
        self.seen: list[list] = []

    @property
    def info(self) -> PlayerInfo:
        return self._info

    def respond(self, messages):
        self.seen.append(list(messages))
        if self._resign_after is not None and self._idx >= self._resign_after:
            return LLMResponse(reasoning="lost position", move=None, resign=True)
        move = self._moves[self._idx]
        self._idx += 1
        return LLMResponse(reasoning=f"play {move}", move=move)


# Детский мат (fool's mate): белые играют слабо, чёрные матуют на 2-м ходу.
FOOLS_MATE_WHITE = ["f3", "g4"]
FOOLS_MATE_BLACK = ["e5", "Qh4#"]


def _runner(
    white_moves, black_moves, *, on_event=None, max_plies=None, settings=None, **pkw
):
    players = {
        "white": _ScriptedPlayer("white-model", white_moves, **pkw.get("white", {})),
        "black": _ScriptedPlayer("black-model", black_moves, **pkw.get("black", {})),
    }
    game = new_game_record(
        players, game_id="g1", created_at=CREATED_AT, settings=settings
    )
    runner = GameRunner(players, game, board=Board(), on_event=on_event, max_plies=max_plies)
    return runner, players, game


# --- сборка записи и чередование --------------------------------------------

def test_new_game_record_uses_player_info():
    players = {
        "white": _ScriptedPlayer("gpt", []),
        "black": _ScriptedPlayer("claude", []),
    }
    game = new_game_record(players, game_id="abc", created_at=CREATED_AT)

    assert game.id == "abc"
    assert game.created_at == CREATED_AT
    assert game.players["white"].model_id == "gpt"
    assert game.players["black"].model_id == "claude"
    assert game.result == "*"
    assert game.moves == []


def test_plays_fools_mate_and_records_moves():
    runner, _, game = _runner(FOOLS_MATE_WHITE, FOOLS_MATE_BLACK)
    result = runner.play()

    assert result is game
    assert len(game.moves) == 4
    assert [m.side for m in game.moves] == ["white", "black", "white", "black"]
    assert [m.san for m in game.moves] == ["f3", "e5", "g4", "Qh4#"]
    assert [m.ply for m in game.moves] == [1, 2, 3, 4]
    # Партия закончена матом → финализация результата (чёрные заматовали белых).
    assert runner.board.is_game_over()
    assert game.result == "0-1"
    assert game.termination == "checkmate"


def test_move_records_carry_fen_uci_and_reasoning():
    runner, _, game = _runner(FOOLS_MATE_WHITE, FOOLS_MATE_BLACK)
    runner.play()

    first = game.moves[0]
    assert first.uci == "f2f3"
    assert first.fen_before == Board().fen()
    # fen_after первого хода — это fen_before второго.
    assert first.fen_after == game.moves[1].fen_before
    assert first.reasoning == "play f3"
    assert game.moves[-1].san == "Qh4#"


# --- история сообщений -------------------------------------------------------

def test_message_history_logs_system_once_then_context_and_replies():
    runner, _, game = _runner(FOOLS_MATE_WHITE, FOOLS_MATE_BLACK)
    runner.play()

    white_hist = game.messages["white"]
    # система один раз, затем (context, assistant) на каждый из двух ходов белых.
    assert [m.role for m in white_hist] == [
        "system",
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    # ассистентская реплика — это сериализованный протокол D-007.
    assert '"move":"f3"' in white_hist[2].content
    black_hist = game.messages["black"]
    assert [m.role for m in black_hist] == [
        "system",
        "user",
        "assistant",
        "user",
        "assistant",
    ]


def test_player_receives_self_contained_system_plus_context():
    runner, players, _ = _runner(FOOLS_MATE_WHITE, FOOLS_MATE_BLACK)
    runner.play()

    # каждый запрос к модели — ровно [system, context], независимо от номера хода.
    for sent in players["white"].seen:
        assert [m.role for m in sent] == ["system", "user"]
    assert len(players["white"].seen) == 2  # два хода белых


# --- события -----------------------------------------------------------------

def test_emits_events_in_order():
    events: list[GameEvent] = []
    runner, _, _ = _runner(FOOLS_MATE_WHITE, FOOLS_MATE_BLACK, on_event=events.append)
    runner.play()

    types = [e.type for e in events]
    assert types[0] == EVENT_GAME_START
    assert types[-1] == EVENT_GAME_OVER
    assert types.count(EVENT_TURN_START) == 4
    assert types.count(EVENT_MOVE) == 4
    # turn_start всегда непосредственно перед соответствующим move.
    move_events = [e for e in events if e.type == EVENT_MOVE]
    assert [e.payload["san"] for e in move_events] == ["f3", "e5", "g4", "Qh4#"]
    assert move_events[0].payload["side"] == "white"
    assert move_events[-1].payload["ply"] == 4


def test_game_over_event_reports_ply_count():
    events: list[GameEvent] = []
    runner, _, _ = _runner(FOOLS_MATE_WHITE, FOOLS_MATE_BLACK, on_event=events.append)
    runner.play()

    over = next(e for e in events if e.type == EVENT_GAME_OVER)
    assert over.payload["plies"] == 4


# --- остановка и пределы -----------------------------------------------------

def test_max_plies_caps_the_game():
    # Длинный скрипт, но обрезаем на 2 полухода.
    runner, _, game = _runner(["e4", "Nf3"], ["e5", "Nc6"], max_plies=2)
    runner.play()

    assert len(game.moves) == 2
    assert [m.san for m in game.moves] == ["e4", "e5"]
    assert not runner.board.is_game_over()


# --- ретрай нелегального хода и техническое поражение (D-006) ----------------

def test_illegal_then_legal_retries_and_records_attempt():
    # Белые сперва шлют мусор, затем легальный ход — ретрай, попытка записана.
    runner, _, game = _runner(["Zzz", "e4"], ["e5"], max_plies=2)
    runner.play()

    assert game.termination is None
    assert [m.san for m in game.moves] == ["e4", "e5"]
    attempts = game.moves[0].illegal_attempts
    assert len(attempts) == 1
    assert attempts[0].raw == "Zzz"
    assert attempts[0].reason  # непустая причина для коррекции


def test_retry_context_carries_correction_to_model():
    # На повторном запросе модель видит коррекцию (причина отклонения, D-006).
    runner, players, _ = _runner(["Zzz", "e4"], ["e5"], max_plies=2)
    runner.play()

    # второй запрос к белым — это повторная попытка с блоком коррекции.
    retry_sent = players["white"].seen[1]
    context = retry_sent[-1].content  # последний — user-контекст
    assert "was rejected" in context
    assert "Zzz" in context


def test_three_illegal_attempts_lose_on_technical_grounds():
    runner, _, game = _runner(["Zzz", "Zzz", "Zzz"], [])
    runner.play()

    assert game.termination == "technical_loss"
    assert game.result == "0-1"  # белые проиграли → победа чёрных
    assert game.moves == []  # легального хода так и не случилось
    assert runner._is_over()


def test_black_technical_loss_awards_white():
    runner, _, game = _runner(["e4"], ["Zzz", "Zzz", "Zzz"])
    runner.play()

    assert game.termination == "technical_loss"
    assert game.result == "1-0"
    assert [m.san for m in game.moves] == ["e4"]  # ход белых остался в логе


def test_technical_loss_respects_custom_retry_limit():
    runner, _, game = _runner(
        ["Zzz", "Zzz"], [], settings=PlayerSettings(illegal_move_retries=2)
    )
    runner.play()

    assert game.termination == "technical_loss"
    assert game.result == "0-1"


def test_counter_resets_after_a_legal_move():
    # По одной нелегальной попытке на ход, но не три подряд → партия продолжается.
    runner, _, game = _runner(
        ["Zzz", "e4", "Zzz", "Nf3"], ["e5", "Nc6"], max_plies=4
    )
    runner.play()

    assert game.termination is None
    assert [m.san for m in game.moves] == ["e4", "e5", "Nf3", "Nc6"]
    assert len(game.moves[0].illegal_attempts) == 1  # первый ход белых
    assert len(game.moves[2].illegal_attempts) == 1  # второй ход белых
    assert game.moves[1].illegal_attempts == []  # ходы чёрных — без попыток


def test_illegal_event_emitted_per_attempt():
    events: list[GameEvent] = []
    runner, _, _ = _runner(["Zzz", "Zzz", "Zzz"], [], on_event=events.append)
    runner.play()

    illegal = [e for e in events if e.type == EVENT_ILLEGAL]
    assert [e.payload["attempt"] for e in illegal] == [1, 2, 3]
    assert all(e.payload["side"] == "white" for e in illegal)


def test_game_over_event_reports_result_and_termination():
    events: list[GameEvent] = []
    runner, _, _ = _runner(["Zzz", "Zzz", "Zzz"], [], on_event=events.append)
    runner.play()

    over = next(e for e in events if e.type == EVENT_GAME_OVER)
    assert over.payload["termination"] == "technical_loss"
    assert over.payload["result"] == "0-1"


# --- окончание партии: result/termination и resign (D-020) -------------------

def test_white_resign_awards_black():
    runner, _, game = _runner([], [], white={"resign_after": 0})
    runner.play()

    assert game.termination == "resign"
    assert game.result == "0-1"
    assert game.moves == []  # ход не сделан, сдача до хода


def test_black_resign_awards_white():
    # Белые ходят e4, чёрные тут же сдаются.
    runner, _, game = _runner(["e4"], [], black={"resign_after": 0})
    runner.play()

    assert game.termination == "resign"
    assert game.result == "1-0"
    assert [m.san for m in game.moves] == ["e4"]


def test_resign_emitted_in_game_over_event():
    events: list[GameEvent] = []
    runner, _, _ = _runner([], [], white={"resign_after": 0}, on_event=events.append)
    runner.play()

    over = next(e for e in events if e.type == EVENT_GAME_OVER)
    assert over.payload["termination"] == "resign"
    assert over.payload["result"] == "0-1"


def test_insufficient_material_is_drawn_immediately():
    # Король против короля — партия окончена сразу, цикл не делает ходов.
    players = {
        "white": _ScriptedPlayer("w", []),
        "black": _ScriptedPlayer("b", []),
    }
    game = new_game_record(players, game_id="kk", created_at=CREATED_AT)
    runner = GameRunner(players, game, board=Board("7k/8/8/8/8/8/8/7K w - - 0 1"))
    runner.play()

    assert game.moves == []
    assert game.termination == "insufficient_material"
    assert game.result == "1/2-1/2"


def test_stalemate_is_drawn_after_the_move():
    # Один ход белых ставит чёрному пат.
    players = {
        "white": _ScriptedPlayer("w", ["Kg6"]),
        "black": _ScriptedPlayer("b", []),
    }
    game = new_game_record(players, game_id="stale", created_at=CREATED_AT)
    runner = GameRunner(players, game, board=Board("7k/5Q2/8/6K1/8/8/8/8 w - - 0 1"))
    runner.play()

    assert [m.san for m in game.moves] == ["Kg6"]
    assert game.termination == "stalemate"
    assert game.result == "1/2-1/2"


def test_max_plies_break_leaves_result_open():
    # Обрыв по пределу — партия не окончена, результат остаётся "*".
    runner, _, game = _runner(["e4", "Nf3"], ["e5", "Nc6"], max_plies=2)
    runner.play()

    assert game.result == "*"
    assert game.termination is None


def test_normalize_termination_collapses_repetition():
    assert _normalize_termination("threefold_repetition") == "repetition"
    assert _normalize_termination("fivefold_repetition") == "repetition"
    # прочие коды проходят без изменений.
    assert _normalize_termination("checkmate") == "checkmate"
    assert _normalize_termination("fifty_moves") == "fifty_moves"
    assert _normalize_termination("stalemate") == "stalemate"


# --- протокол подсказок движка (★, D-010) ------------------------------------

class _ResponsePlayer:
    """Игрок, отдающий заранее заданные ``LLMResponse`` по очереди.

    В отличие от ``_ScriptedPlayer`` (только ходы), здесь скрипт — полные ответы
    протокола D-007, поэтому можно выразить ``request_hint``/``resign`` и
    несколько запросов на одном ходу (перезапрос после выдачи подсказки).
    """

    def __init__(self, model_id: str, responses):
        self._info = PlayerInfo(
            model_id=model_id, provider="fake", display_name=model_id.upper()
        )
        self._responses = list(responses)
        self._idx = 0
        self.seen: list[list] = []

    @property
    def info(self) -> PlayerInfo:
        return self._info

    def respond(self, messages):
        self.seen.append(list(messages))
        resp = self._responses[self._idx]
        self._idx += 1
        return resp


class _FakeEngine:
    """Фейковый движок подсказок: отдаёт фиксированный ``HintRecord`` (★, D-010).

    Считает вызовы ``best_move``; при ``error=True`` имитирует отказ движка
    (``EngineUnavailableError``) для проверки деградации.
    """

    def __init__(self, hint: HintRecord | None = None, *, error: bool = False):
        self.hint = hint or HintRecord(best_move="d2d4", eval_cp=35)
        self.error = error
        self.calls: list[str] = []

    def best_move(self, fen: str) -> HintRecord:
        self.calls.append(fen)
        if self.error:
            raise EngineUnavailableError("движок недоступен")
        return self.hint


def _hint_runner(
    white_responses, *, engine=None, max_plies=1, settings=None, on_event=None
):
    players = {
        "white": _ResponsePlayer("white-model", white_responses),
        "black": _ResponsePlayer("black-model", []),
    }
    game = new_game_record(
        players, game_id="h1", created_at=CREATED_AT, settings=settings
    )
    runner = GameRunner(
        players,
        game,
        board=Board(),
        max_plies=max_plies,
        engine=engine,
        on_event=on_event,
    )
    return runner, players, game


def test_request_hint_consumes_one_and_records_hint():
    engine = _FakeEngine(HintRecord(best_move="e2e4", eval_cp=30))
    runner, _, game = _hint_runner(
        [LLMResponse(request_hint=True), LLMResponse(move="e4")], engine=engine
    )
    runner.play()

    assert engine.calls == [Board().fen()]  # движок спрошен по стартовой позиции
    assert game.hints_used["white"] == 1
    move = game.moves[0]
    assert move.san == "e4"
    assert move.hint_used is True
    assert move.hint == HintRecord(best_move="e2e4", eval_cp=30)


def test_hint_injected_into_requery_context():
    engine = _FakeEngine(HintRecord(best_move="d2d4", eval_cp=35))
    runner, players, _ = _hint_runner(
        [LLMResponse(request_hint=True), LLMResponse(move="d4")], engine=engine
    )
    runner.play()

    # белых спросили дважды: запрос подсказки, затем перезапрос с подсказкой.
    assert len(players["white"].seen) == 2
    requery_context = players["white"].seen[1][-1].content
    assert "Engine hint" in requery_context
    assert "d2d4" in requery_context
    # остаток подсказок в перезапросе уже уменьшён (1 из 3 израсходована).
    assert "Hints remaining: 2" in requery_context


def test_hint_emits_event():
    engine = _FakeEngine(HintRecord(best_move="e2e4", eval_cp=30))
    events: list[GameEvent] = []
    runner, _, _ = _hint_runner(
        [LLMResponse(request_hint=True), LLMResponse(move="e4")],
        engine=engine,
        on_event=events.append,
    )
    runner.play()

    hint_events = [e for e in events if e.type == EVENT_HINT]
    assert len(hint_events) == 1
    payload = hint_events[0].payload
    assert payload["side"] == "white"
    assert payload["best_move"] == "e2e4"
    assert payload["eval_cp"] == 30
    assert payload["hints_remaining"] == 2


def test_hint_ignored_without_engine():
    # Запрос подсказки без движка: подсказка не тратится, ход обрабатывается обычно.
    runner, players, game = _hint_runner(
        [LLMResponse(request_hint=True, move="e4")], engine=None
    )
    runner.play()

    assert game.hints_used["white"] == 0
    assert len(players["white"].seen) == 1  # перезапроса не было
    move = game.moves[0]
    assert move.san == "e4"
    assert move.hint_used is False
    assert move.hint is None


def test_hint_ignored_when_limit_exhausted():
    engine = _FakeEngine()
    runner, _, game = _hint_runner(
        [LLMResponse(request_hint=True, move="e4")],
        engine=engine,
        settings=PlayerSettings(hints_per_player=0),
    )
    runner.play()

    assert engine.calls == []  # движок даже не спрошен — лимит 0
    assert game.hints_used["white"] == 0
    assert game.moves[0].hint_used is False


def test_only_one_hint_per_turn():
    # Подсказка выдана; повторный request_hint в том же ходу игнорируется.
    engine = _FakeEngine()
    runner, players, game = _hint_runner(
        [LLMResponse(request_hint=True), LLMResponse(request_hint=True, move="e4")],
        engine=engine,
    )
    runner.play()

    assert len(engine.calls) == 1  # движок спрошен ровно один раз
    assert game.hints_used["white"] == 1
    assert game.moves[0].san == "e4"


def test_engine_failure_during_hint_degrades():
    # Движок отказывает на запросе подсказки: подсказка не тратится, ход играется.
    engine = _FakeEngine(error=True)
    runner, _, game = _hint_runner(
        [LLMResponse(request_hint=True, move="e4")], engine=engine
    )
    runner.play()

    assert engine.calls  # попытка была
    assert game.hints_used["white"] == 0
    assert game.moves[0].hint_used is False
    assert game.moves[0].san == "e4"
