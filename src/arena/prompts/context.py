"""Сборка per-turn контекста хода для модели (спека 3.6).

В отличие от системного промпта (статичный, кэшируемый — D-017), контекст хода
меняется на каждом полуходе и несёт всё, что нужно модели для решения:

- её цвет и номер хода;
- FEN текущей позиции;
- полный список легальных ходов в SAN (ход выбирается строго из него — D-005);
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
) -> str:
    """Собрать текст контекста хода для стороны, чья сейчас очередь.

    Сторона и номер хода берутся из ``board`` (``turn``/``fullmove_number``), остаток
    подсказок — из ``game`` (лимит минус израсходованное стороной). ``retry`` (если
    задан) добавляет блок коррекции нелегального хода; ``hint`` (если задан) —
    инъекцию подсказки движка. Возвращает готовый текст без завершающего перевода
    строки.
    """
    side: Side = board.turn  # type: ignore[assignment]
    sections: list[str] = []

    sections.append(
        f"You are playing {_COLOR_NAMES[side]}. "
        f"It is move {board.fullmove_number}, your turn."
    )
    sections.append(f"Current position (FEN):\n{board.fen()}")
    sections.append(
        "Legal moves (SAN):\n" + " ".join(board.legal_moves_san())
    )
    sections.append("Game so far (PGN):\n" + build_pgn(game, include_reasoning=False))
    sections.append(_history_section(game))
    sections.append(f"Hints remaining: {_hints_remaining(game, side)}")

    if hint is not None:
        sections.append(_hint_section(hint))
    if retry is not None:
        sections.append(_retry_section(retry))

    sections.append(
        'Reply with one JSON object: '
        '{"reasoning", "move", "request_hint", "resign"}.'
    )
    return "\n\n".join(sections)


def context_message(
    game: GameRecord,
    board: Board,
    *,
    retry: IllegalAttempt | None = None,
    hint: HintRecord | None = None,
) -> MessageRecord:
    """Обернуть ``build_context`` в ``MessageRecord`` с ролью ``user``."""
    content = build_context(game, board, retry=retry, hint=hint)
    return MessageRecord(role="user", content=content)


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


def _retry_section(retry: IllegalAttempt) -> str:
    """Блок коррекции после нелегального/нераспознанного хода (D-006)."""
    return (
        f'Your previous answer "{retry.raw}" was rejected: {retry.reason}\n'
        "Choose one move from the legal moves listed above."
    )
