"""Pydantic-модели данных — общий язык между слоями.

Это типизированная форма ``game.json`` (D-004 — единственный источник истины):
из ``GameRecord`` затем порождаются PGN и HTML-отчёт. Модели здесь только описывают
данные; чтение/запись на диск — задача слоя ``storage``.

Состав:

- ``LLMResponse`` — разобранный ответ модели по протоколу D-007
  (``reasoning`` / ``move`` / ``request_hint`` / ``resign``); ещё не провалидирован
  как легальный ход.
- ``MessageRecord`` — одна реплика в истории диалога с моделью (роль + текст).
- ``IllegalAttempt`` — нелегальная/нераспознанная попытка хода (raw + причина).
- ``HintRecord`` — содержимое подсказки движка (лучший ход + оценка), D-010.
- ``MoveRecord`` — полная запись одного полухода (SAN/UCI, FEN до/после,
  рассуждение, попытки, подсказка, оценка и классификация из пост-анализа).
- ``PlayerInfo`` — кто играл сторону (модель/провайдер/имя), без секретов.
- ``PlayerAnalysis`` / ``KeyMoment`` / ``AnalysisSummary`` — итог пост-анализа (D-009).
- ``GameRecord`` — вся партия целиком.

Секреты (API-ключи) сюда не попадают (D-003): ``PlayerInfo`` хранит лишь ``model_id``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# Сторона/победитель. ``None`` (без Literal) используется отдельно для ничьей.
Side = Literal["white", "black"]

# Роль реплики в истории диалога с моделью.
Role = Literal["system", "user", "assistant"]

# Классы качества хода из пост-анализа (D-009). ``book`` — дебютная теория.
Classification = Literal[
    "book", "brilliant", "good", "interesting",
    "normal", "inaccuracy", "mistake", "blunder",
]

# Статус стратегического плана относительно прошлого хода стороны (фича «стратегия»).
# ``start`` — первый план партии (прошлого плана нет); далее модель помечает, как
# новый план соотносится с предыдущим: продолжает / корректирует / отбрасывает.
PlanStatus = Literal["start", "continue", "adapt", "abandon"]


class LLMResponse(BaseModel):
    """Разобранный ответ модели по протоколу D-007.

    ``move`` — ход строкой (SAN или UCI), как его прислала модель; легальность
    проверяется отдельно через ``core`` и может отсутствовать (например, при сдаче
    или нераспознанном ответе). ``request_hint`` тратит подсказку (если есть),
    ``resign`` означает добровольную сдачу.
    """

    reasoning: str = ""
    move: str | None = None
    # Фича «стратегия»: приватный rolling-план на ближайшие ходы (``strategy``) и его
    # статус относительно прошлого плана (``plan_status``). Пусты/``start`` по
    # умолчанию — когда фича выключена или модель их не прислала.
    strategy: str = ""
    plan_status: PlanStatus = "start"
    request_hint: bool = False
    resign: bool = False


class MessageRecord(BaseModel):
    """Одна реплика в истории диалога с моделью (роль + текст)."""

    role: Role
    content: str


class IllegalAttempt(BaseModel):
    """Нелегальная или нераспознанная попытка хода: что прислали и почему отклонено."""

    raw: str
    reason: str


class HintRecord(BaseModel):
    """Подсказка движка для текущей позиции (D-010).

    ``best_move`` — рекомендованный ход в UCI; ``eval_cp`` — оценка позиции в
    сантипешках с точки зрения ходящей стороны (``None``, если оценка недоступна,
    например при мате — тогда заполняется ``mate_in``).
    """

    best_move: str
    eval_cp: int | None = None
    mate_in: int | None = None


class MoveRecord(BaseModel):
    """Полная запись одного полухода — основа партии в ``game.json``.

    Поля ``engine_eval_cp`` и ``classification`` заполняются на этапе пост-анализа
    (★, D-009) и до него остаются ``None``.
    """

    ply: int = Field(ge=1)
    side: Side
    san: str
    uci: str
    fen_before: str
    fen_after: str
    reasoning: str = ""
    # Фича «стратегия»: план, сформулированный на этом ходу, и его статус (D-025).
    # Прикреплён к ходу → «текущий план стороны» = ``strategy`` её последнего хода.
    # Пуст/``start``, когда фича выключена.
    strategy: str = ""
    plan_status: PlanStatus = "start"
    illegal_attempts: list[IllegalAttempt] = Field(default_factory=list)
    hint_used: bool = False
    hint: HintRecord | None = None
    engine_eval_cp: int | None = None
    classification: Classification | None = None


class PlayerInfo(BaseModel):
    """Кто играл сторону: модель, провайдер, отображаемое имя.

    Хранит только ``model_id`` — никаких ключей (D-003).
    """

    # ``model_id`` начинается с ``model_`` — снимаем защиту пространства имён,
    # иначе pydantic ругается на конфликт с зарезервированным префиксом.
    model_config = {"protected_namespaces": ()}

    model_id: str
    provider: str
    display_name: str


class PlayerSettings(BaseModel):
    """Срез настроек арены, под которыми сыграна партия (для воспроизводимости).

    ``include_legal_moves`` (D-021) управляет тем, кладём ли в контекст хода
    список легальных ходов. По умолчанию ``False`` — модель ходит «вслепую» по
    FEN/PGN, а легальность проверяется уже **после** ответа (ретрай при нелегальном
    ходе, D-006). ``True`` возвращает прежнее поведение (список-подсказку в промпте).
    ``strategy_enabled`` (фича «стратегия») включает rolling-план: модель пишет
    ``strategy``/``plan_status``, а план её прошлого хода ре-инъектируется ей же.
    По умолчанию включено.
    """

    illegal_move_retries: int = 3
    hints_per_player: int = 3
    include_legal_moves: bool = False
    strategy_enabled: bool = True


class PlayerAnalysis(BaseModel):
    """Сводка пост-анализа по одной стороне (D-009).

    ``accuracy`` — доля «точных» ходов (0..1); счётчики — по классам ошибок.
    """

    accuracy: float | None = None
    blunders: int = 0
    mistakes: int = 0
    inaccuracies: int = 0


class KeyMoment(BaseModel):
    """Ключевой момент партии: ход, его класс и комментарий (опц. от LLM)."""

    ply: int = Field(ge=1)
    classification: Classification
    comment: str = ""


class AnalysisSummary(BaseModel):
    """Итог пост-анализа партии: сводки по сторонам и ключевые моменты."""

    white: PlayerAnalysis = Field(default_factory=PlayerAnalysis)
    black: PlayerAnalysis = Field(default_factory=PlayerAnalysis)
    key_moments: list[KeyMoment] = Field(default_factory=list)


class GameRecord(BaseModel):
    """Канонический лог партии целиком — типизированная форма ``game.json`` (D-004).

    ``result`` — PGN-результат (``"1-0"`` / ``"0-1"`` / ``"1/2-1/2"`` / ``"*"`` пока
    партия идёт). ``termination`` — стабильный код причины окончания (как у
    ``core.board.GameOutcome``: ``checkmate`` / ``stalemate`` / ``technical_loss`` /
    ``resign`` / …) или ``None``, если партия не завершена. ``analysis`` заполняется
    на этапе пост-анализа (★) и до него ``None``.
    """

    id: str
    created_at: datetime
    players: dict[Side, PlayerInfo]
    settings: PlayerSettings = Field(default_factory=PlayerSettings)
    result: str = "*"
    termination: str | None = None
    moves: list[MoveRecord] = Field(default_factory=list)
    messages: dict[Side, list[MessageRecord]] = Field(
        default_factory=lambda: {"white": [], "black": []}
    )
    hints_used: dict[Side, int] = Field(
        default_factory=lambda: {"white": 0, "black": 0}
    )
    analysis: AnalysisSummary | None = None
