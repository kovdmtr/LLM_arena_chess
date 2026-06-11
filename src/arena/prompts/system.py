"""Системный промпт игрока: правила взаимодействия + строгий JSON-формат ответа.

Это статичная часть контекста (D-017): один и тот же системный промпт шлётся модели
на каждом ходу партии, поэтому он не зависит от позиции — только от лимитов партии
(подсказки, попытки), которые фиксированы на всю игру. Динамика хода (FEN, легальные
ходы, PGN, история, причина ретрая) собирается отдельно — это задача context builder.

Промпт описывает протокол ответа D-007: модель обязана вернуть **один JSON-объект**
``{ "reasoning", "move", "request_hint", "resign" }``. Именно эти ключи читает
``arena.arena.parse_response``; формулировки здесь и парсер должны оставаться в
согласии. Текст промпта — на английском: так все три провайдера надёжнее держат
формат и шахматную нотацию; язык поля ``reasoning`` не навязываем.
"""

from __future__ import annotations

from arena.models import MessageRecord

# Канонические ключи протокола ответа (D-007) — единый источник истины для текста
# промпта и тестов. Совпадают с ключами, которые разбирает ``parse_response``.
RESPONSE_KEYS: tuple[str, ...] = ("reasoning", "move", "request_hint", "resign")

# Доп. ключи фичи «стратегия» — добавляются в протокол, когда она включена
# (``include_strategy=True``). ``parse_response`` читает их всегда (мягко), но
# промпт описывает только при включённой фиче, чтобы не менять базовое поведение.
STRATEGY_KEYS: tuple[str, ...] = ("strategy", "plan_status")

# Условные фрагменты промпта под `include_legal_moves` (D-021): с/без списка
# легальных ходов. Подставляются в шаблон вместе с лимитами партии.
_LEGAL_MOVES_ON = {
    "moves_clause": "the full list of legal moves in SAN, ",
    "legality": "It MUST be one of the legal moves provided.",
    "correction_detail": "the reason and the legal moves",
    "strike_tail": "so always pick a move from the provided list.",
}
_LEGAL_MOVES_OFF = {
    "moves_clause": "",
    "legality": "It MUST be legal in the current position.",
    "correction_detail": "the reason",
    "strike_tail": "so make sure your move is legal before you answer.",
}

# Фрагменты фичи «стратегия» (контракт непрерывности). Подставляются, когда
# ``include_strategy=True``; иначе все три пусты и промпт не меняется.
_STRATEGY_SECTION = """

Strategy (you are playing a continuous game, not scoring a fresh position):
- Besides your move you keep a PLAN — your intentions for the next several moves \
(pawn structure, king safety, targets, piece maneuvers). The plan is private: it is \
NOT shown to your opponent.
- Keep "reasoning" (why THIS move now) separate from "strategy" (the multi-move plan \
this move serves). Keep the plan short: 1-3 sentences.
- On your next turn you will be reminded of this plan. Continue it, or consciously \
adapt or abandon it in response to your opponent, and say which in "plan_status"."""

_STRATEGY_KEYS_TEXT = """
  - "strategy": string — your private plan for the next few moves, carried across \
turns and not shown to the opponent.
  - "plan_status": string — one of "start", "continue", "adapt", "abandon": how this \
plan relates to your previous one (use "start" on your first move)."""

# Пример ответа: базовый (4 ключа) и с полями стратегии (6 ключей).
_EXAMPLE_BASE = (
    '{"reasoning": "Develop the knight and fight for the center.", '
    '"move": "Nf3", "request_hint": false, "resign": false}'
)
_EXAMPLE_STRATEGY = (
    '{"reasoning": "Develop the knight and fight for the center.", '
    '"move": "Nf3", '
    '"strategy": "Finish development, castle kingside, then press the d5 square.", '
    '"plan_status": "start", "request_hint": false, "resign": false}'
)

# Шаблон промпта. Плейсхолдеры подставляются из настроек партии; сам текст
# статичен в пределах одной игры (пригоден для prompt caching, D-017).
_TEMPLATE = """\
You are a chess engine playing a full game of standard chess against another \
opponent. There is no time control. You always play strictly by the rules of \
classical chess.

How the game works:
- On every turn you receive the current position: your color and move number, the \
position in FEN, {moves_clause}the PGN so far, and both players' previous \
explanations.
- You choose exactly one move. {legality} Give the move in standard algebraic \
notation (SAN, e.g. "Nf3", "exd5", "O-O", "e8=Q+") or in UCI coordinate notation \
(e.g. "g1f3", "e7e8q"). Do not pass; skipping a move is not allowed.
- If your move is illegal or cannot be understood, you receive a correction \
({correction_detail}) and must try again. {retries} illegal attempts in a row on \
the same turn lose the game on technical grounds, {strike_tail}

Hints:
- You have {hints} engine hints for the entire game. Set "request_hint" to true to \
spend one. The engine's best move and a short evaluation are then added to your \
context on your next turn. Once your hints are used up, requesting more has no effect.

Resigning:
- Set "resign" to true only to voluntarily concede the game. Use it sparingly, in a \
clearly lost position.{strategy_section}

Response format (strict):
- Reply with EXACTLY ONE JSON object and nothing else — no markdown fences, no prose \
around it. The object has these keys:
  - "reasoning": string — a brief explanation of your choice (used for the game log \
and shown to your opponent).
  - "move": string — your move in SAN or UCI, taken from the legal moves. Use null \
only when you are resigning or only requesting a hint.{strategy_keys}
  - "request_hint": boolean — true to spend one engine hint, otherwise false.
  - "resign": boolean — true to resign, otherwise false.

Example of a normal move:
{example}"""


def build_system_prompt(
    *,
    hints_per_player: int = 3,
    illegal_move_retries: int = 3,
    include_legal_moves: bool = True,
    include_strategy: bool = False,
) -> str:
    """Собрать текст системного промпта под лимиты партии.

    ``hints_per_player`` и ``illegal_move_retries`` берутся из настроек партии
    (``PlayerSettings``) и в пределах одной игры неизменны, поэтому промпт остаётся
    статичным (кэшируемым, D-017). ``include_legal_moves`` (D-021) переключает
    формулировки: с ним промпт обещает список легальных ходов в контексте, без него
    — требует, чтобы модель сама подобрала легальный ход (проверка после ответа).
    ``include_strategy`` (фича «стратегия») добавляет описание полей ``strategy``/
    ``plan_status`` и контракт непрерывности; при ``False`` (по умолчанию) промпт
    идентичен прежнему. Возвращает готовый текст без завершающего перевода строки.
    """
    variant = _LEGAL_MOVES_ON if include_legal_moves else _LEGAL_MOVES_OFF
    return _TEMPLATE.format(
        hints=hints_per_player,
        retries=illegal_move_retries,
        strategy_section=_STRATEGY_SECTION if include_strategy else "",
        strategy_keys=_STRATEGY_KEYS_TEXT if include_strategy else "",
        example=_EXAMPLE_STRATEGY if include_strategy else _EXAMPLE_BASE,
        **variant,
    )


def system_message(
    *,
    hints_per_player: int = 3,
    illegal_move_retries: int = 3,
    include_legal_moves: bool = True,
    include_strategy: bool = False,
) -> MessageRecord:
    """Обёртка ``build_system_prompt`` в ``MessageRecord`` с ролью ``system``.

    Удобно для сборки истории диалога: системная реплика всегда идёт первой.
    """
    content = build_system_prompt(
        hints_per_player=hints_per_player,
        illegal_move_retries=illegal_move_retries,
        include_legal_moves=include_legal_moves,
        include_strategy=include_strategy,
    )
    return MessageRecord(role="system", content=content)
