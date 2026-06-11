"""Тесты LLM-комментария ключевых моментов (★, опц., D-009).

Комментатор подменяется фейком (записывает полученные сообщения, отдаёт заранее
заданный текст или бросает ``ProviderError``), чтобы проверять именно логику
надстройки без сетевых вызовов: заполнение ``KeyMoment.comment``, состав промпта
(класс, SAN, оценка, рассуждение, лучший ход движка), мягкую деградацию (нет
комментатора / нет анализа / сбой провайдера / пустой ответ) и опциональный движок
для строки «лучший ход».
"""

from __future__ import annotations

from datetime import datetime

import chess

from arena.analysis import build_commentary_prompt, comment_key_moments
from arena.engine import EngineUnavailableError
from arena.models import (
    AnalysisSummary,
    GameRecord,
    HintRecord,
    KeyMoment,
    MoveRecord,
    PlayerInfo,
)
from arena.providers import ProviderError

CREATED_AT = datetime(2026, 6, 9, 12, 0, 0)


class _PlyCommenter:
    """Комментатор, решающий ответ/ошибку по номеру ключевого момента (по порядку)."""

    def __init__(self, responses):
        # responses: список значений по порядку вызовов; строка → текст,
        # ProviderError-инстанс/класс → бросить.
        self.responses = list(responses)
        self.seen: list[list] = []
        self._i = 0

    def complete(self, messages, params):
        self.seen.append(list(messages))
        value = self.responses[self._i]
        self._i += 1
        if isinstance(value, ProviderError):
            raise value
        return value


class _FakeBestMove:
    """Фейковый движок лучшего хода (или бросает ``EngineUnavailableError``)."""

    def __init__(self, *, best="d2d4", error: bool = False):
        self.best = best
        self.error = error

    def best_move(self, fen, *, depth=None):
        if self.error:
            raise EngineUnavailableError("движок недоступен")
        return HintRecord(best_move=self.best, eval_cp=120)


def _pinfo(name: str) -> PlayerInfo:
    return PlayerInfo(model_id=name, provider="fake", display_name=name.upper())


def _game_with_moments(moment_classes, *, with_analysis=True):
    """Партия из нескольких ходов + ``AnalysisSummary`` с ключевыми моментами.

    ``moment_classes`` — список ``(ply, classification)`` для key_moments.
    """
    board = chess.Board()
    sans = ["e4", "e5", "Qh5", "Nc6"]
    moves = []
    for i, san in enumerate(sans, start=1):
        fen_before = board.fen()
        move = board.parse_san(san)
        uci = move.uci()
        board.push(move)
        moves.append(
            MoveRecord(
                ply=i,
                side="white" if i % 2 == 1 else "black",
                san=san,
                uci=uci,
                fen_before=fen_before,
                fen_after=board.fen(),
                reasoning=f"reasoning for {san}",
                engine_eval_cp=-270 if i == 3 else 30,
            )
        )
    analysis = None
    if with_analysis:
        analysis = AnalysisSummary(
            key_moments=[KeyMoment(ply=p, classification=c) for p, c in moment_classes]
        )
    game = GameRecord(
        id="g1",
        created_at=CREATED_AT,
        players={"white": _pinfo("w"), "black": _pinfo("b")},
        moves=moves,
        analysis=analysis,
    )
    return game


# --- заполнение комментариев -------------------------------------------------

def test_fills_comments_for_all_key_moments():
    game = _game_with_moments([(3, "blunder")])
    commenter = _PlyCommenter(["Qh5 is premature and loses tempo."])

    filled = comment_key_moments(game, commenter)

    assert filled == 1
    assert game.analysis.key_moments[0].comment == "Qh5 is premature and loses tempo."


def test_returns_count_and_comments_each_moment():
    game = _game_with_moments([(1, "brilliant"), (3, "blunder")])
    commenter = _PlyCommenter(["First comment.", "Second comment."])

    filled = comment_key_moments(game, commenter)

    assert filled == 2
    assert [k.comment for k in game.analysis.key_moments] == [
        "First comment.",
        "Second comment.",
    ]


def test_comment_is_stripped():
    game = _game_with_moments([(3, "blunder")])
    commenter = _PlyCommenter(["  spaced out comment.\n"])

    comment_key_moments(game, commenter)

    assert game.analysis.key_moments[0].comment == "spaced out comment."


# --- деградация --------------------------------------------------------------

def test_no_commenter_does_nothing():
    game = _game_with_moments([(3, "blunder")])

    filled = comment_key_moments(game, None)

    assert filled == 0
    assert game.analysis.key_moments[0].comment == ""


def test_no_analysis_returns_zero():
    game = _game_with_moments([(3, "blunder")], with_analysis=False)
    commenter = _PlyCommenter(["unused"])

    filled = comment_key_moments(game, commenter)

    assert filled == 0
    assert game.analysis is None
    assert commenter.seen == []  # комментатор даже не вызывался


def test_provider_error_skips_that_moment_only():
    game = _game_with_moments([(1, "brilliant"), (3, "blunder")])
    commenter = _PlyCommenter([ProviderError("rate limit"), "Second survives."])

    filled = comment_key_moments(game, commenter)

    assert filled == 1
    assert game.analysis.key_moments[0].comment == ""  # упал — пропущен
    assert game.analysis.key_moments[1].comment == "Second survives."


def test_empty_response_leaves_comment_empty():
    game = _game_with_moments([(3, "blunder")])
    commenter = _PlyCommenter(["   \n  "])

    filled = comment_key_moments(game, commenter)

    assert filled == 0
    assert game.analysis.key_moments[0].comment == ""


def test_moment_without_matching_move_is_skipped():
    game = _game_with_moments([(99, "blunder")])  # нет хода с ply=99
    commenter = _PlyCommenter(["unused"])

    filled = comment_key_moments(game, commenter)

    assert filled == 0
    assert commenter.seen == []


# --- состав промпта ----------------------------------------------------------

def test_prompt_includes_classification_san_eval_and_reasoning():
    game = _game_with_moments([(3, "blunder")])
    move = game.moves[2]  # Qh5, ply=3
    moment = game.analysis.key_moments[0]

    messages = build_commentary_prompt(game, move, moment)

    assert messages[0].role == "system"
    user = messages[1].content
    assert "blunder" in user
    assert "Qh5" in user
    assert move.fen_before in user
    assert "reasoning for Qh5" in user
    # engine_eval_cp=-270 (POV белых) → -2.70 пешки.
    assert "-2.70" in user


def test_prompt_includes_engine_best_move_when_engine_present():
    game = _game_with_moments([(3, "blunder")])
    commenter = _PlyCommenter(["ok"])
    engine = _FakeBestMove(best="d1h5")

    comment_key_moments(game, commenter, engine=engine)

    user = commenter.seen[0][1].content
    assert "d1h5" in user


def test_unavailable_engine_degrades_without_best_move_line():
    game = _game_with_moments([(3, "blunder")])
    commenter = _PlyCommenter(["still commented"])
    engine = _FakeBestMove(error=True)

    filled = comment_key_moments(game, commenter, engine=engine)

    assert filled == 1
    user = commenter.seen[0][1].content
    assert "preferred move" not in user.lower()


def test_prompt_handles_missing_reasoning_and_eval():
    game = _game_with_moments([(1, "brilliant")])
    move = game.moves[0]
    move.reasoning = ""
    move.engine_eval_cp = None
    moment = game.analysis.key_moments[0]

    user = build_commentary_prompt(game, move, moment)[1].content

    assert "no reasoning" in user.lower()
    assert "evaluation" not in user.lower()  # строки оценки нет


def test_mate_eval_is_rendered_as_forced_mate():
    game = _game_with_moments([(3, "blunder")])
    move = game.moves[2]
    move.engine_eval_cp = -100_000  # мат за чёрных
    moment = game.analysis.key_moments[0]

    user = build_commentary_prompt(game, move, moment)[1].content

    assert "forced mate for Black" in user


# --- фича «стратегия»: учёт плана в комментарии (D-025) ---------------------


def test_prompt_includes_plan_and_previous_plan():
    game = _game_with_moments([(3, "blunder")])
    # Белые: план на 1-м ходу и новый (продолжение) на 3-м (ключевой момент Qh5).
    game.moves[0].strategy = "attack the f7 square early"
    game.moves[2].strategy = "go for a quick mate on f7"
    game.moves[2].plan_status = "continue"
    moment = game.analysis.key_moments[0]

    user = build_commentary_prompt(game, game.moves[2], moment)[1].content

    assert "attack the f7 square early" in user  # прежний план стороны
    assert "go for a quick mate on f7" in user  # план этого хода
    assert '"continue"' in user  # статус плана
    assert "followed or changed that plan" in user  # просьба оценить следование


def test_prompt_omits_plan_lines_when_strategy_disabled():
    # По умолчанию (стратегия пуста) блок плана не добавляется — промпт прежний.
    game = _game_with_moments([(3, "blunder")])
    moment = game.analysis.key_moments[0]
    user = build_commentary_prompt(game, game.moves[2], moment)[1].content
    assert "plan" not in user.lower()


def test_previous_plan_is_side_specific():
    # План соперника (чёрных) не утекает в блок «прежний план» белых.
    game = _game_with_moments([(3, "blunder")])
    game.moves[1].strategy = "BLACK-PLAN"  # ход чёрных (ply2)
    game.moves[2].strategy = "white-current"  # ход белых (ply3)
    moment = game.analysis.key_moments[0]
    user = build_commentary_prompt(game, game.moves[2], moment)[1].content
    assert "white-current" in user
    assert "BLACK-PLAN" not in user
