"""Полный сквозной прогон Phase 7: база + ★ на фейках (``test: full e2e run``).

Дополняет базовый ``test_arena_e2e`` (там — партия→диск→round-trip) проверкой всего
★-конвейера в одном тесте: фейковые игроки доигрывают мат Шольяра, по ходу одному
из них выдаётся **подсказка** (фейковый движок, D-010); затем **пост-анализ**
(``analyze_game``) размечает ходы и собирает сводку с ключевым моментом (D-009);
**LLM-комментарий** (фейковый комментатор) заполняет этот момент (D-009 опц.);
наконец артефакты (``game.json`` + ``game.pgn`` + ``report.html``) экспортируются и
проверяются — отчёт self-contained, показывает анализ/подсказку/комментарий и не
содержит секретов (D-003).

Всё детерминировано: ходы скриптованы, оценки движка скриптованы так, чтобы 2-й
полуход стал «зевком» (ключевой момент), сеть/Stockfish не используются.
"""

from __future__ import annotations

from datetime import datetime, timezone

from arena.analysis import analyze_game, comment_key_moments
from arena.arena import GameRunner, new_game_record
from arena.core import Board
from arena.models import HintRecord, LLMResponse, PlayerInfo
from arena.storage import (
    GAME_JSON_NAME,
    PGN_NAME,
    REPORT_NAME,
    export_pgn,
    export_report,
    save_game,
)

CREATED_AT = datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc)

# Мат Шольяра: белые матуют на 4-м ходу (7 полуходов).
WHITE_MOVES = ["e4", "Bc4", "Qh5", "Qxf7#"]
BLACK_MOVES = ["e5", "Nc6", "Nf6"]

# Скрипт оценок движка для analyze_game (по 2 вызова evaluate на не-терминальный ход:
# before/after; у матующего хода — только before). Индексы 2,3 → 2-й полуход (чёрные
# e5): best=300, after=0 ⇒ cpl=300 ⇒ «зевок» (ключевой момент). Остальные ⇒ cpl=0.
ENGINE_EVALS = [0, 0, 300, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]


class _FakePlayer:
    """Детерминированный игрок: ходы из скрипта; опц. просит подсказку на 1-м ходу.

    При запросе подсказки раннер перезапрашивает ход (D-010), т.е. ``respond``
    вызывается на тот же полуход дважды. Поэтому индекс продвигается только когда
    ход реально отдаётся (``request_hint=False``), а на запрос подсказки возвращается
    тот же ход — как поступила бы и реальная модель, переосмыслив с подсказкой.
    """

    def __init__(self, model_id, moves, *, hint_on_first=False):
        self._info = PlayerInfo(
            model_id=model_id, provider="fake", display_name=model_id.upper()
        )
        self._moves = list(moves)
        self._idx = 0
        self._hint_on_first = hint_on_first
        self._hinted = False

    @property
    def info(self):
        return self._info

    def respond(self, messages):
        move = self._moves[self._idx]
        if self._hint_on_first and not self._hinted:
            self._hinted = True
            return LLMResponse(reasoning=f"play {move}", move=move, request_hint=True)
        self._idx += 1
        return LLMResponse(reasoning=f"play {move}", move=move, request_hint=False)


class _FakeEngine:
    """Фейковый Stockfish: скриптованные оценки для анализа + фикс. лучший ход."""

    def __init__(self, evals):
        self._evals = list(evals)
        self._i = 0

    def evaluate(self, fen, *, depth=None):
        value = self._evals[self._i] if self._i < len(self._evals) else 0
        self._i += 1
        return value

    def best_move(self, fen, *, depth=None):
        return HintRecord(best_move="d2d4", eval_cp=25, mate_in=None)


class _FakeCommenter:
    """Фейковый комментатор (контракт ``LLMProvider.complete``)."""

    SENTENCE = "Black drops material with this careless pawn push."

    def __init__(self):
        self.calls = 0

    def complete(self, messages, params):
        self.calls += 1
        return self.SENTENCE


def _run_full_pipeline(tmp_path, game_id="full-e2e-001"):
    """Доиграть партию с движком, разметить, прокомментировать, экспортировать."""
    players = {
        "white": _FakePlayer("white-model", WHITE_MOVES, hint_on_first=True),
        "black": _FakePlayer("black-model", BLACK_MOVES),
    }
    game = new_game_record(players, game_id=game_id, created_at=CREATED_AT)
    engine = _FakeEngine(ENGINE_EVALS)
    events = []
    runner = GameRunner(players, game, board=Board(), on_event=events.append, engine=engine)
    runner.play()

    summary = analyze_game(game, engine)
    game.analysis = summary
    commenter = _FakeCommenter()
    filled = comment_key_moments(game, commenter, engine=engine)

    save_game(game, games_root=tmp_path)
    export_pgn(game, games_root=tmp_path)
    export_report(game, games_root=tmp_path)
    return game, events, filled


def test_full_pipeline_plays_hints_analyzes_and_exports(tmp_path):
    game, events, filled = _run_full_pipeline(tmp_path)

    # --- база: партия доиграна до мата ---
    assert game.result == "1-0"
    assert game.termination == "checkmate"
    assert [m.san for m in game.moves] == [
        "e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6", "Qxf7#",
    ]

    # --- ★ подсказка (D-010): выдана белым на 1-м ходу ---
    assert any(e.type == "hint" for e in events)
    assert game.moves[0].hint_used is True
    assert game.moves[0].hint is not None
    assert game.hints_used["white"] == 1

    # --- ★ анализ (D-009): ходы размечены, ключевой момент — зевок на 2-м полуходе ---
    assert game.analysis is not None
    assert all(m.classification is not None for m in game.moves)
    assert all(m.engine_eval_cp is not None for m in game.moves)
    assert game.analysis.black.blunders == 1
    key = game.analysis.key_moments
    assert [(k.ply, k.classification) for k in key] == [(2, "blunder")]

    # --- ★ комментарий (D-009 опц.): ключевой момент прокомментирован ---
    assert filled == 1
    assert key[0].comment == _FakeCommenter.SENTENCE


def test_full_pipeline_writes_three_artifacts(tmp_path):
    game, _events, _filled = _run_full_pipeline(tmp_path)
    folder = tmp_path / game.id
    assert (folder / GAME_JSON_NAME).is_file()
    assert (folder / PGN_NAME).is_file()
    assert (folder / REPORT_NAME).is_file()


def test_full_report_is_self_contained_and_shows_star_features(tmp_path):
    game, _events, _filled = _run_full_pipeline(tmp_path)
    html = (tmp_path / game.id / REPORT_NAME).read_text(encoding="utf-8")

    # self-contained: встроенный SVG, без внешних <img src>.
    assert html.lstrip().lower().startswith("<!doctype html>")
    assert "<svg" in html
    assert "<img" not in html
    # ★ анализ виден в отчёте (классификация хода — per-move бейдж).
    assert "blunder" in html.lower()


def test_full_pipeline_artifacts_have_no_secrets(tmp_path):
    game, _events, _filled = _run_full_pipeline(tmp_path)
    folder = tmp_path / game.id
    for name in (GAME_JSON_NAME, PGN_NAME, REPORT_NAME):
        text = (folder / name).read_text(encoding="utf-8")
        assert "api_key" not in text
        assert "sk-" not in text
