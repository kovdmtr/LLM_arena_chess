"""★ LLM-комментарий ключевых моментов партии (опц., D-009).

Пост-анализ (``analyze_game``) уже размечает ходы и собирает ``AnalysisSummary`` с
ключевыми моментами (блестящие/ошибки/зевки), но их ``comment`` остаётся пустым.
Эта надстройка просит LLM коротко прокомментировать каждый ключевой момент на
основе **линий движка** (оценка позиции, рекомендованный лучший ход) и
**рассуждения** самой модели на этом ходу, и заполняет ``KeyMoment.comment``
(отчёт уже умеет его показывать).

Фича опциональна и деградирует мягко (как ★-движок, D-008):

- нет ``commenter`` или у партии нет ``analysis`` → ничего не делаем (комментарии
  остаются пустыми);
- сбой провайдера на отдельном моменте (``ProviderError``) → этот момент
  пропускается, остальные комментируются;
- движок для лучшего хода опционален: при его отсутствии/``EngineUnavailableError``
  комментарий строится без строки «движок предпочитал …».

Секреты не логируются и в промпт не попадают: ``commenter`` — это обычный
``LLMProvider`` (ключ инкапсулирован в нём, D-003), в сообщения уходит только
позиция/оценка/рассуждение.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from arena.config.settings import ModelParams
from arena.engine import EngineUnavailableError
from arena.models import GameRecord, HintRecord, KeyMoment, MessageRecord, MoveRecord
from arena.providers import ProviderError

# Конечная оценка форсированного мата (как в ``analyzer``/``engine``).
_MATE_SCORE = 100_000

_SYSTEM_PROMPT = (
    "You are a concise chess commentator. You will be given one move from a game "
    "between two engines/LLMs that a post-game analysis flagged as notable "
    "(a brilliant move, a mistake, or a blunder), together with the engine's "
    "evaluation, its preferred move when available, and the player's own stated "
    "reasoning. Write ONE short sentence (at most ~30 words) explaining, for a "
    "general chess audience, why the move is notable. Be factual and specific; "
    "do not use markdown, lists, or quotes. Output only the sentence."
)


class Commenter(Protocol):
    """Минимальный контракт комментатора — совпадает с ``LLMProvider.complete``."""

    def complete(
        self, messages: Sequence[MessageRecord], params: ModelParams
    ) -> str: ...


class BestMoveEngine(Protocol):
    """Минимальный контракт движка для строки «лучший ход» (как ``StockfishEngine``)."""

    def best_move(self, fen: str, *, depth: int | None = None) -> HintRecord: ...


def comment_key_moments(
    game: GameRecord,
    commenter: Commenter | None,
    *,
    params: ModelParams | None = None,
    engine: BestMoveEngine | None = None,
    depth: int | None = None,
) -> int:
    """Заполнить ``KeyMoment.comment`` LLM-комментарием для каждого ключевого момента.

    Мутирует ``game.analysis.key_moments`` на месте и возвращает число фактически
    заполненных комментариев. При ``commenter is None`` или отсутствии ``analysis``
    возвращает ``0``, ничего не меняя. Сбой провайдера на отдельном моменте или
    пустой ответ → момент пропускается (его ``comment`` остаётся пустым).
    """
    if commenter is None or game.analysis is None:
        return 0

    params = params or ModelParams()
    moves_by_ply = {move.ply: move for move in game.moves}
    filled = 0
    for moment in game.analysis.key_moments:
        move = moves_by_ply.get(moment.ply)
        if move is None:
            continue
        best = _best_move(engine, move, depth)
        messages = build_commentary_prompt(game, move, moment, best_move=best)
        try:
            raw = commenter.complete(messages, params)
        except ProviderError:
            continue
        comment = raw.strip()
        if comment:
            moment.comment = comment
            filled += 1
    return filled


def _best_move(
    engine: BestMoveEngine | None, move: MoveRecord, depth: int | None
) -> HintRecord | None:
    """Лучший ход движка для позиции перед ходом — или ``None`` при деградации."""
    if engine is None:
        return None
    try:
        return engine.best_move(move.fen_before, depth=depth)
    except EngineUnavailableError:
        return None


def build_commentary_prompt(
    game: GameRecord,
    move: MoveRecord,
    moment: KeyMoment,
    *,
    best_move: HintRecord | None = None,
) -> list[MessageRecord]:
    """Собрать ``[system, user]`` для комментария одного ключевого момента.

    В ``user`` уходит номер хода, сторона, SAN, класс (``moment.classification``),
    оценка позиции (POV белых, из ``engine_eval_cp``), FEN до хода, опц. лучший ход
    движка и рассуждение самой модели. Никаких секретов — только данные позиции.
    """
    move_no = (move.ply + 1) // 2
    lines = [
        f"Move {move_no} by {move.side} ({move.san}).",
        f"Post-analysis flagged it as: {moment.classification}.",
        f"Position before the move (FEN): {move.fen_before}",
    ]
    eval_text = _format_eval_white(move.engine_eval_cp)
    if eval_text is not None:
        lines.append(f"Engine evaluation after the move (White's point of view): {eval_text}.")
    if best_move is not None:
        lines.append(f"Engine preferred move (UCI): {best_move.best_move}.")
    reasoning = (move.reasoning or "").strip()
    if reasoning:
        lines.append(f'The player\'s stated reasoning was: "{reasoning}"')
    else:
        lines.append("The player gave no reasoning.")
    lines.append("Explain in one sentence why this move is notable.")

    return [
        MessageRecord(role="system", content=_SYSTEM_PROMPT),
        MessageRecord(role="user", content="\n".join(lines)),
    ]


def _format_eval_white(eval_cp: int | None) -> str | None:
    """Оценку POV белых (сантипешки) → читаемая строка в пешках, мат как «mate»."""
    if eval_cp is None:
        return None
    if abs(eval_cp) >= _MATE_SCORE:
        return "forced mate for White" if eval_cp > 0 else "forced mate for Black"
    return f"{eval_cp / 100:+.2f}"
