"""Тесты GameRunner — главного игрового цикла (Phase 3, happy path).

Игроки подменяются детерминированным ``_ScriptedPlayer``: он отдаёт заранее
заданную последовательность ходов (без сети, без провайдера). Проверяем:
чередование сторон и заполнение ``GameRecord`` (ходы, FEN, рассуждения),
запись истории сообщений по сторонам, последовательность событий, остановку при
окончании партии, защитный ``max_plies`` и швы под следующие задачи (нелегальный
ход и сдача → ``GameRunnerError``). Финализация ``result``/``termination`` — задача
следующего коммита, поэтому здесь ``result`` остаётся ``"*"``.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from arena.arena import (
    EVENT_GAME_OVER,
    EVENT_GAME_START,
    EVENT_MOVE,
    EVENT_TURN_START,
    GameEvent,
    GameRunner,
    GameRunnerError,
    new_game_record,
)
from arena.core import Board
from arena.models import LLMResponse, PlayerInfo, PlayerSettings, Side

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


def _runner(white_moves, black_moves, *, on_event=None, max_plies=None, **pkw):
    players = {
        "white": _ScriptedPlayer("white-model", white_moves, **pkw.get("white", {})),
        "black": _ScriptedPlayer("black-model", black_moves, **pkw.get("black", {})),
    }
    game = new_game_record(players, game_id="g1", created_at=CREATED_AT)
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
    # Партия закончена матом, но финализация результата — следующая задача.
    assert runner.board.is_game_over()
    assert game.result == "*"
    assert game.termination is None


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


# --- швы под следующие задачи ------------------------------------------------

def test_illegal_move_raises_game_runner_error():
    # Белые присылают нелегальный ход — ретрай/техпоражение ещё не реализованы.
    runner, _, _ = _runner(["e5"], ["e5"])  # e5 нелегален за белых из старта
    with pytest.raises(GameRunnerError, match="нелегальный ход"):
        runner.play()


def test_resign_raises_game_runner_error():
    # Белые сразу заявляют сдачу — обработка resign ещё не реализована.
    runner, _, _ = _runner([], [], white={"resign_after": 0})
    with pytest.raises(GameRunnerError, match="сдач"):
        runner.play()
