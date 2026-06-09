"""Сборка текстового PGN из ``GameRecord`` (поверх ``python-chess``).

``game.json`` — единственный источник истины (D-004); PGN **порождается** из него,
а не ведётся параллельно. Здесь только одна публичная функция — ``build_pgn`` —
которая разворачивает ``GameRecord`` в стандартный PGN: семь обязательных тегов
(Event/Site/Date/Round/White/Black/Result) плюс служебные, ходы в SAN и рассуждения
моделей как комментарии ``{...}`` к ходам.

PGN строится через ``python-chess`` (D-005): ходы берутся из ``MoveRecord.uci`` и
применяются к доске, поэтому SAN и нумерация ходов всегда корректны и совместимы с
lichess/chess.com. Секреты в PGN не попадают (D-003) — в тегах только ``model_id``.
"""

from __future__ import annotations

import chess
import chess.pgn

from arena.models import GameRecord

# Имя арены в теге Event по умолчанию.
_DEFAULT_EVENT = "LLM Chess Arena"


def _clean_comment(text: str) -> str:
    """Обезвредить текст рассуждения для вставки в PGN-комментарий ``{...}``.

    Фигурные скобки закрывают/открывают комментарий в PGN, а переводы строк ломают
    однострочный экспорт — заменяем их пробелами и схлопываем повторы пробелов.
    """
    cleaned = text.replace("{", "(").replace("}", ")")
    return " ".join(cleaned.split())


def build_pgn(
    game: GameRecord,
    *,
    event: str = _DEFAULT_EVENT,
    site: str = "LLM Chess Arena",
    round_: str = "1",
    include_reasoning: bool = True,
) -> str:
    """Собрать текстовый PGN из ``GameRecord``.

    Теги: семь обязательных (Event/Site/Date/Round/White/Black/Result) и служебные
    ``Termination``, ``WhiteModel``/``BlackModel``, ``WhiteProvider``/``BlackProvider``
    (для прослеживаемости; нестандартные теги lichess/chess.com игнорируют). Ходы —
    в SAN; если ``include_reasoning`` и у хода есть ``reasoning``, оно добавляется
    комментарием ``{...}``.

    Ходы применяются из ``MoveRecord.uci``; нелегальный ход в позиции поднимет
    ``ValueError`` из ``python-chess`` (``game.json`` к этому моменту уже валиден).
    """
    pgn_game = chess.pgn.Game()
    headers = pgn_game.headers

    headers["Event"] = event
    headers["Site"] = site
    headers["Date"] = game.created_at.strftime("%Y.%m.%d")
    headers["Round"] = round_
    headers["White"] = game.players["white"].display_name
    headers["Black"] = game.players["black"].display_name
    headers["Result"] = game.result

    if game.termination:
        headers["Termination"] = game.termination
    headers["WhiteModel"] = game.players["white"].model_id
    headers["BlackModel"] = game.players["black"].model_id
    headers["WhiteProvider"] = game.players["white"].provider
    headers["BlackProvider"] = game.players["black"].provider

    node: chess.pgn.GameNode = pgn_game
    for record in game.moves:
        move = chess.Move.from_uci(record.uci)
        node = node.add_main_variation(move)
        if include_reasoning and record.reasoning:
            node.comment = _clean_comment(record.reasoning)

    exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=True)
    return pgn_game.accept(exporter)
