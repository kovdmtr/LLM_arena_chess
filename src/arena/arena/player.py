"""ModelPlayer: тонкая обёртка над провайдером, отдающая разобранный ответ.

``ModelPlayer`` соединяет два соседних слоя: берёт историю диалога, вызывает
``LLMProvider.complete`` (сырой текст) и разбирает текст в ``LLMResponse`` по
протоколу D-007 (``{ reasoning, move, request_hint, resign }``). Легальность хода
здесь НЕ проверяется — это задача ``core`` и ``GameRunner``; задача игрока лишь
надёжно извлечь намерение модели из ответа.

Парсер устойчив к тексту вокруг JSON (D-007): модель часто оборачивает объект в
прозу или markdown-ограждение ```` ```json ... ``` ````. Если распознать JSON не
удаётся, парсер не падает, а возвращает ``LLMResponse`` без хода (``move=None``) с
сырым текстом в ``reasoning`` — вышестоящий слой обработает это как
нераспознанный ход (ретрай, D-006). Сбой самого провайдера (``ProviderError``)
наружу не маскируется и пробрасывается.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from arena.config.settings import ModelParams
from arena.models import LLMResponse, MessageRecord, PlayerInfo
from arena.providers import LLMProvider

# Ключи протокола ответа (D-007).
_REASONING_KEYS = ("reasoning",)
_MOVE_KEYS = ("move",)
_HINT_KEYS = ("request_hint",)
_RESIGN_KEYS = ("resign",)
# Поля фичи «стратегия» — читаем всегда (мягко); пусто/``start`` без них.
_STRATEGY_KEYS = ("strategy",)
_PLAN_STATUS_KEYS = ("plan_status",)

# Строковые значения, трактуемые как «истина» (модель иногда шлёт строку/число).
_TRUTHY_STRINGS = frozenset({"true", "yes", "y", "1"})

# Допустимые значения ``plan_status``; всё иное (или отсутствие) → ``start``.
_PLAN_STATUSES = frozenset({"start", "continue", "adapt", "abandon"})


class ModelPlayer:
    """Игрок поверх LLM-провайдера: история диалога → разобранный ``LLMResponse``.

    Хранит провайдера и параметры генерации (по умолчанию — из ``ResolvedModel``
    провайдера). ``respond`` — единственная операция: вызвать модель и вернуть
    разобранный ответ. Ключ и SDK инкапсулированы провайдером; игрок их не видит.
    """

    def __init__(
        self, provider: LLMProvider, *, params: ModelParams | None = None
    ) -> None:
        self.provider = provider
        # Параметры генерации фиксируются на игрока: по умолчанию из каталога
        # модели, но вызывающий может переопределить (например, для тестов).
        self.params = params if params is not None else provider.model.params

    @property
    def info(self) -> PlayerInfo:
        """Несекретное описание игрока для ``GameRecord`` (D-003: без ключа)."""
        model = self.provider.model
        return PlayerInfo(
            model_id=model.id,
            provider=model.provider,
            display_name=model.display_name,
        )

    def respond(self, messages: Sequence[MessageRecord]) -> LLMResponse:
        """Вызвать модель на ``messages`` и вернуть разобранный ``LLMResponse``.

        Транспортные/SDK-сбои пробрасываются как ``ProviderError``. Любой
        текстовый ответ (в т.ч. без распознаваемого JSON) парсится best-effort и
        ошибки разбора наружу не поднимает.
        """
        raw = self.provider.complete(messages, self.params)
        return parse_response(raw)

    def __repr__(self) -> str:  # делегируем провайдеру — он уже скрывает ключ
        return f"ModelPlayer({self.provider!r})"


def parse_response(text: str) -> LLMResponse:
    """Разобрать сырой текст ответа модели в ``LLMResponse`` (D-007).

    Стратегия (устойчивость к тексту вокруг JSON):

    1. Найти все сбалансированные JSON-объекты в тексте (с учётом строковых
       литералов и экранирования), распарсить каждый.
    2. Выбрать первый объект, содержащий ключ ``move`` (а если такого нет —
       первый валидный объект): модель иногда приводит примеры перед ответом.
    3. Поля привести к типам ``LLMResponse`` терпимо к вариациям SDK
       (bool как строка/число, пустой ``move`` → ``None``).

    Если ни одного объекта распарсить не удалось, вернуть ``LLMResponse`` без хода
    с сырым текстом в ``reasoning`` (вышестоящий слой обработает как
    нераспознанный ход).
    """
    objects = _extract_json_objects(text)
    payload = _select_payload(objects)
    if payload is None:
        # JSON не распознан — сохраняем текст как рассуждение, хода нет.
        return LLMResponse(reasoning=text.strip(), move=None)

    return LLMResponse(
        reasoning=_as_str(_first_key(payload, _REASONING_KEYS)),
        move=_as_move(_first_key(payload, _MOVE_KEYS)),
        strategy=_as_str(_first_key(payload, _STRATEGY_KEYS)),
        plan_status=_as_plan_status(_first_key(payload, _PLAN_STATUS_KEYS)),
        request_hint=_as_bool(_first_key(payload, _HINT_KEYS)),
        resign=_as_bool(_first_key(payload, _RESIGN_KEYS)),
    )


def _extract_json_objects(text: str) -> list[dict]:
    """Вернуть все top-level JSON-объекты, найденные в ``text`` (по порядку).

    Сканирует строку, отслеживая глубину фигурных скобок и нахождение внутри
    строкового литерала (с экранированием), чтобы ``{``/``}`` внутри строк не
    ломали баланс. Каждую сбалансированную подстроку пробует распарсить —
    невалидные пропускаются.
    """
    objects: list[dict] = []
    depth = 0
    start = -1
    in_string = False
    escaped = False

    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start != -1:
                    candidate = text[start : i + 1]
                    try:
                        parsed = json.loads(candidate)
                    except (ValueError, json.JSONDecodeError):
                        parsed = None
                    if isinstance(parsed, dict):
                        objects.append(parsed)
                    start = -1
    return objects


def _select_payload(objects: list[dict]) -> dict | None:
    """Выбрать объект-ответ: первый с ключом ``move``, иначе первый валидный."""
    for obj in objects:
        if any(key in obj for key in _MOVE_KEYS):
            return obj
    return objects[0] if objects else None


def _first_key(payload: dict, keys: Sequence[str]):
    """Значение первого присутствующего ключа из ``keys`` (или ``None``)."""
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _as_str(value) -> str:
    """Привести значение к строке; ``None`` → пустая строка."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _as_move(value) -> str | None:
    """Нормализовать поле ``move``: пустое/пробельное/``None`` → ``None``."""
    if value is None:
        return None
    text = value if isinstance(value, str) else str(value)
    text = text.strip()
    return text or None


def _as_plan_status(value) -> str:
    """Нормализовать ``plan_status`` к допустимому значению; иначе ``start``."""
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _PLAN_STATUSES:
            return normalized
    return "start"


def _as_bool(value) -> bool:
    """Терпимо привести значение к ``bool`` (bool/число/строка ``"true"`` и т.п.)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in _TRUTHY_STRINGS
    return False
