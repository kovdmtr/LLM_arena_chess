"""Тесты подключения движка к веб-партии (Phase 7, D-008/D-009/D-010).

Проверяют сквозной путь ``GameManager`` с движком: пост-анализ заполняет
``record.analysis``, подсказки выдаются, движок закрывается по окончании — и при
этом всё мягко деградирует без движка или при его отказе. Движок и игроки —
фейковые (без Stockfish и без сети).
"""

from __future__ import annotations

from arena.config import AnalysisConfig
from arena.engine import EngineUnavailableError
from arena.models import HintRecord, LLMResponse, PlayerInfo
from arena.web import GameManager
from arena.web.games import STATUS_FINISHED

_WHITE_MOVES = ["f3", "g4"]
_BLACK_MOVES = ["e5", "Qh4#"]


class _ScriptedPlayer:
    def __init__(self, info, moves, *, hint_on_first=False):
        self._info = info
        self._moves = list(moves)
        self._hint_on_first = hint_on_first
        self._hinted = False

    @property
    def info(self):
        return self._info

    def respond(self, messages):
        # Подсказка → раннер перезапрашивает тот же полуход (D-010): не сдвигаем ход
        # на запрос подсказки, возвращаем тот же; продвигаемся только при реальном ходе.
        if self._hint_on_first and not self._hinted:
            self._hinted = True
            return LLMResponse(reasoning="x", move=self._moves[0], request_hint=True)
        return LLMResponse(reasoning="x", move=self._moves.pop(0), request_hint=False)


class _FakeEngine:
    """Фейковый движок: лучший ход для подсказки + оценка 0; считает close()."""

    def __init__(self, *, eval_raises=False):
        self.closed = False
        self._eval_raises = eval_raises

    def best_move(self, fen, *, depth=None):
        return HintRecord(best_move="e2e4", eval_cp=15, mate_in=None)

    def evaluate(self, fen, *, depth=None):
        if self._eval_raises:
            raise EngineUnavailableError("engine died mid-analysis")
        return 0

    def close(self):
        self.closed = True


def _info(side):
    return PlayerInfo(model_id=f"{side}-model", provider="openai", display_name=side)


def _resolved():
    return {"white": _info("white"), "black": _info("black")}


def _players(*, hint_on_first=False):
    return {
        "white": _ScriptedPlayer(_info("white"), _WHITE_MOVES, hint_on_first=hint_on_first),
        "black": _ScriptedPlayer(_info("black"), _BLACK_MOVES),
    }


def _manager(tmp_path, *, engine=None, players=None, analysis=True):
    players = players or _players()
    return GameManager(
        player_factory=lambda side, resolved: players[side],
        games_root=str(tmp_path),
        persist=False,
        engine_factory=(lambda: engine) if engine is not None else None,
        analysis_config=AnalysisConfig(enabled=True) if analysis else None,
    )


def test_engine_enables_postgame_analysis_and_is_closed(tmp_path):
    engine = _FakeEngine()
    manager = _manager(tmp_path, engine=engine)
    session = manager.start(_resolved())
    assert session.join(timeout=5)

    assert session.status == STATUS_FINISHED
    assert session.record.analysis is not None  # ★ разметка прошла
    assert engine.closed  # процесс закрыт по окончании


def test_no_engine_means_no_analysis(tmp_path):
    manager = _manager(tmp_path, engine=None)
    session = manager.start(_resolved())
    assert session.join(timeout=5)

    assert session.status == STATUS_FINISHED
    assert session.record.analysis is None  # деградация без движка (D-008)


def test_analysis_degrades_when_engine_fails(tmp_path):
    engine = _FakeEngine(eval_raises=True)
    manager = _manager(tmp_path, engine=engine)
    session = manager.start(_resolved())
    assert session.join(timeout=5)

    assert session.status == STATUS_FINISHED  # партия доиграна
    assert session.record.analysis is None  # анализ деградировал, но артефакты валидны
    assert engine.closed


def test_hint_is_served_with_engine(tmp_path):
    engine = _FakeEngine()
    manager = _manager(tmp_path, engine=engine, players=_players(hint_on_first=True))
    session = manager.start(_resolved())
    assert session.join(timeout=5)

    assert any(event["type"] == "hint" for event in session.events)
    white_first = session.record.moves[0]
    assert white_first.hint_used is True
    assert white_first.hint is not None
