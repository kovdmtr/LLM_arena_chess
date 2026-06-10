"""★ Модели данных турнира (Phase 8, бэклог-1).

Турнир — это набор партий между несколькими моделями по расписанию (round-robin).
Здесь только типизированная форма данных; генерация пар — в ``pairings.py``, прогон
партий и подсчёт таблицы — в ``runner.py`` (следующий шаг).

- ``TournamentGame`` — одна пара в расписании: номер тура, кто белыми/чёрными
  (``model_id``), и — после того как сыграна — ссылка на ``GameRecord`` (``game_id``)
  и результат партии.
- ``TournamentRecord`` — турнир целиком: участники (``PlayerInfo``, без секретов
  D-003), флаг двойного круга и список партий.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from arena.models import PlayerInfo


class TournamentGame(BaseModel):
    """Одна партия расписания турнира.

    До того как сыграна — ``game_id``/``result`` равны ``None`` (только пара и тур).
    После прогона ``runner`` проставляет ``game_id`` (папка ``games/<id>/``) и
    ``result`` (PGN-результат ``1-0`` / ``0-1`` / ``1/2-1/2``).
    """

    model_config = {"protected_namespaces": ()}

    round_number: int = Field(ge=1)
    white: str  # model_id играющего белыми
    black: str  # model_id играющего чёрными
    game_id: str | None = None
    result: str | None = None


class TournamentRecord(BaseModel):
    """Турнир целиком: участники, формат и расписание партий.

    ``participants`` — несекретные описания моделей (``PlayerInfo``); ``double``
    означает двойной круг (каждая пара играет дважды со сменой цвета). ``games`` —
    расписание (а после прогона — и результаты).
    """

    id: str
    created_at: datetime
    participants: list[PlayerInfo] = Field(default_factory=list)
    double: bool = False
    games: list[TournamentGame] = Field(default_factory=list)
