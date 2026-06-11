"""Сборка per-turn контекста хода для модели (спека 3.6).

В отличие от системного промпта (статичный, кэшируемый — D-017), контекст хода
меняется на каждом полуходе и несёт всё, что нужно модели для решения:

- её цвет и номер хода;
- FEN текущей позиции;
- (опц., ``include_legal_moves``, D-021) полный список легальных ходов в SAN; по
  умолчанию **не** кладётся — модель ходит по FEN/PGN, а легальность проверяется
  уже после ответа (ретрай при нелегальном ходе, D-006);
- PGN партии на текущий момент (снимок через ``core.build_pgn`` — единый источник);
- объяснения **обеих** сторон по сыгранным ходам (для логов и контекста соперника);
- сколько подсказок осталось у этой стороны;
- при инъекции — содержимое запрошенной ранее подсказки движка (D-010);
- при повторной попытке — причина отклонения предыдущего хода (D-006).

Контекст собирается из ``GameRecord`` (история, игроки, лимиты) и живой ``Board``
(позиция, чья очередь, легальные ходы) — те же объекты, что ведёт ``GameRunner``.
Причина ретрая передаётся как ``IllegalAttempt`` (raw + reason) — отдельный тип не
нужен, поля совпадают.
"""

from __future__ import annotations

from arena.core import Board, build_pgn
from arena.models import GameRecord, HintRecord, IllegalAttempt, MessageRecord, Side

# Человекочитаемые имена сторон для текста контекста.
_COLOR_NAMES: dict[Side, str] = {"white": "White", "black": "Black"}


def build_context(
    game: GameRecord,
    board: Board,
    *,
    retry: IllegalAttempt | None = None,
    hint: HintRecord | None = None,
    include_legal_moves: bool = True,
    include_strategy: bool = False,
) -> str:
    """Собрать текст контекста хода для стороны, чья сейчас очередь.

    Сторона и номер хода берутся из ``board`` (``turn``/``fullmove_number``), остаток
    подсказок — из ``game`` (лимит минус израсходованное стороной). ``retry`` (если
    задан) добавляет блок коррекции нелегального хода; ``hint`` (если задан) —
    инъекцию подсказки движка. ``include_legal_moves`` (D-021) управляет тем, кладём
    ли в контекст список легальных ходов (``False`` — модель ходит «вслепую» по
    FEN/PGN, легальность проверяется после ответа). ``include_strategy`` (фича
    «стратегия») инъектирует **приватный** план предыдущего хода этой стороны —
    модель продолжает свой замысел, а не оценивает позицию заново. Возвращает
    готовый текст без завершающего перевода строки.
    """
    side: Side = board.turn  # type: ignore[assignment]
    sections: list[str] = []

    sections.append(
        f"You are playing {_COLOR_NAMES[side]}. "
        f"It is move {board.fullmove_number}, your turn."
    )
    sections.append(f"Current position (FEN):\n{board.fen()}")
    if include_legal_moves:
        sections.append("Legal moves (SAN):\n" + " ".join(board.legal_moves_san()))
    sections.append("Game so far (PGN):\n" + build_pgn(game, include_reasoning=False))
    sections.append(_history_section(game))
    if include_strategy:
        # Приватный план этой стороны (только её собственный — соперник его не видит).
        sections.append(_plan_section(game, side))
    sections.append(f"Hints remaining: {_hints_remaining(game, side)}")

    if hint is not None:
        sections.append(_hint_section(hint))
    if retry is not None:
        sections.append(_retry_section(retry, include_legal_moves))

    sections.append(_reply_line(include_strategy))
    return "\n\n".join(sections)


def context_message(
    game: GameRecord,
    board: Board,
    *,
    retry: IllegalAttempt | None = None,
    hint: HintRecord | None = None,
    include_legal_moves: bool = True,
    include_strategy: bool = False,
) -> MessageRecord:
    """Обернуть ``build_context`` в ``MessageRecord`` с ролью ``user``."""
    content = build_context(
        game,
        board,
        retry=retry,
        hint=hint,
        include_legal_moves=include_legal_moves,
        include_strategy=include_strategy,
    )
    return MessageRecord(role="user", content=content)


def _reply_line(include_strategy: bool) -> str:
    """Финальная строка-напоминание о ключах JSON-ответа (с/без полей стратегии)."""
    if include_strategy:
        return (
            "Reply with one JSON object: "
            '{"reasoning", "move", "strategy", "plan_status", '
            '"request_hint", "resign"}.'
        )
    return (
        "Reply with one JSON object: "
        '{"reasoning", "move", "request_hint", "resign"}.'
    )


def _last_own_move(game: GameRecord, side: Side):
    """Последний (по времени) ход этой стороны или ``None`` (ещё не ходила)."""
    for record in reversed(game.moves):
        if record.side == side:
            return record
    return None


def _plan_section(game: GameRecord, side: Side) -> str:
    """Блок приватного плана этой стороны (фича «стратегия»).

    Берёт ``strategy``/``plan_status`` последнего хода стороны и просит продолжить,
    скорректировать или отбросить замысел. Если своего хода ещё не было (или план не
    записан) — приглашает сформулировать план впервые. План соперника не показывается.
    """
    last = _last_own_move(game, side)
    if last is not None and last.strategy.strip():
        return (
            f'Your plan from your previous move (private, you marked it "{last.plan_status}"):\n'
            f"«{last.strategy.strip()}»\n"
            "Given the opponent's reply, keep, adapt, or abandon this plan; make a "
            'move that serves it, then output your updated "strategy" and "plan_status".'
        )
    reason = (
        "this is your first move"
        if last is None
        else "you have not recorded a plan yet"
    )
    return (
        "Your plan (private, carried across your turns):\n"
        f"(none — {reason}; state your plan for the coming moves in \"strategy\".)"
    )


def _hints_remaining(game: GameRecord, side: Side) -> int:
    """Остаток подсказок стороны: лимит партии минус израсходованное (не ниже 0)."""
    used = game.hints_used.get(side, 0)
    return max(0, game.settings.hints_per_player - used)


def _history_section(game: GameRecord) -> str:
    """Блок объяснений обеих сторон по сыгранным ходам.

    Каждый ход: номер (в полной нумерации), цвет, SAN и — если есть — рассуждение
    модели. Пустая история (старт партии) даёт явную пометку.
    """
    if not game.moves:
        return "Move explanations so far:\n(none — this is the first move)"

    lines = ["Move explanations so far:"]
    for record in game.moves:
        number = (record.ply + 1) // 2  # полуход → номер полного хода
        head = f"{number}. {_COLOR_NAMES[record.side]} {record.san}"
        reasoning = record.reasoning.strip()
        lines.append(f"{head} — {reasoning}" if reasoning else head)
    return "\n".join(lines)


def _hint_section(hint: HintRecord) -> str:
    """Блок инъекции подсказки движка (D-010): лучший ход + краткая оценка."""
    if hint.mate_in is not None:
        evaluation = f"mate in {hint.mate_in}"
    elif hint.eval_cp is not None:
        # Сантипешки с точки зрения ходящей стороны → в пешках, со знаком.
        evaluation = f"{hint.eval_cp / 100:+.2f} (from your side)"
    else:
        evaluation = "unavailable"
    return (
        "Engine hint (requested earlier):\n"
        f"best move {hint.best_move}, evaluation {evaluation}"
    )


def _retry_section(retry: IllegalAttempt, include_legal_moves: bool) -> str:
    """Блок коррекции после нелегального/нераспознанного хода (D-006).

    Финальная подсказка зависит от ``include_legal_moves`` (D-021): со списком —
    «выбери из показанного выше», без списка — «дай легальный для позиции ход».
    """
    instruction = (
        "Choose one move from the legal moves listed above."
        if include_legal_moves
        else "Reply with a move that is legal in the current position."
    )
    return (
        f'Your previous answer "{retry.raw}" was rejected: {retry.reason}\n'
        f"{instruction}"
    )
