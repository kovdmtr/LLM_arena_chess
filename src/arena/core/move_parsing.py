"""Извлечение хода из ответа модели и нормализация в ``(san, uci)``.

Модель присылает ход строкой — в SAN (``Nf3``, ``O-O``, ``e4``) или в UCI
(``g1f3``, ``e2e4``, ``e7e8q``). Иногда вокруг хода остаётся «мусор»: кавычки,
звёздочки из markdown, точка после хода. ``parse_move`` снимает такую обёртку,
пробует сначала SAN, затем UCI (D-005: легальность — только через ``python-chess``)
и возвращает разобранный ход вместе с обеими нотациями.

При неудаче бросается ``MoveParseError`` с человекочитаемой ``reason`` — её арена
кладёт в ``illegal_attempts`` и отдаёт модели как корректирующее сообщение для
ретрая (D-007). Сам ход здесь не применяется к доске — это делает вызывающий код.
"""

from __future__ import annotations

from dataclasses import dataclass

import chess

from arena.core.board import Board

# Символы-обёртки, которые встречаются вокруг хода и не являются его частью.
# Внимание: ``+`` (шах) и ``#`` (мат) НЕ входят сюда — их разбирает ``parse_san``.
_WRAPPERS = "\"'`*[]() \t\r\n."


@dataclass(frozen=True)
class ParsedMove:
    """Разобранный ход: объект ``chess.Move`` и обе текстовые нотации."""

    move: chess.Move
    san: str
    uci: str


class MoveParseError(ValueError):
    """Ход не разобран. ``raw`` — исходная строка, ``reason`` — причина для модели."""

    def __init__(self, raw: str, reason: str) -> None:
        super().__init__(reason)
        self.raw = raw
        self.reason = reason


def _clean(raw: str) -> str:
    """Снять окружающие пробелы и обёртку (кавычки, markdown, точка)."""
    return raw.strip().strip(_WRAPPERS).strip()


def _to_parsed(board: Board, move: chess.Move) -> ParsedMove:
    return ParsedMove(move=move, san=board.san_of(move), uci=move.uci())


def parse_move(board: Board, raw: str) -> ParsedMove:
    """Разобрать ход ``raw`` в позиции ``board`` (SAN или UCI).

    Возвращает ``ParsedMove``; бросает ``MoveParseError`` с понятной ``reason``,
    если ход пуст, не распознан, неоднозначен или нелегален. Доску не меняет.
    """
    if raw is None:
        raise MoveParseError("", "пустой ход")
    token = _clean(raw)
    if not token:
        raise MoveParseError(raw, "пустой ход")

    # 1) Пробуем SAN. ``InvalidMoveError`` означает «не похоже на SAN» — тогда
    #    проверим UCI ниже. Прочие ошибки SAN информативны сами по себе.
    illegal_as_san: MoveParseError | None = None
    try:
        move = board.parse_san(token)
    except chess.InvalidMoveError:
        move = None
    except chess.AmbiguousMoveError:
        raise MoveParseError(
            raw, f"неоднозначный ход {token!r}: уточните фигуру или клетку отправления"
        ) from None
    except chess.IllegalMoveError:
        # По форме это SAN, но ход нелегален. Маловероятно, что та же строка —
        # ещё и валидный UCI, но проверим; иначе вернём именно эту причину.
        illegal_as_san = MoveParseError(
            raw, f"ход {token!r} нелегален в текущей позиции"
        )
        move = None
    else:
        return _to_parsed(board, move)

    # 2) Пробуем UCI (нижний регистр: продвижение пишется как ``e7e8q``).
    try:
        move = board.parse_uci(token.lower())
    except chess.InvalidMoveError:
        if illegal_as_san is not None:
            raise illegal_as_san from None
        raise MoveParseError(
            raw, f"{token!r} не распознан как ход (ожидается SAN или UCI)"
        ) from None
    except chess.IllegalMoveError:
        raise MoveParseError(
            raw, f"ход {token!r} нелегален в текущей позиции"
        ) from None
    return _to_parsed(board, move)
