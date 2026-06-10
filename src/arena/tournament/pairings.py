"""★ Генерация пар round-robin и сборка ``TournamentRecord`` (Phase 8, бэклог-1).

``round_robin`` строит расписание «каждый с каждым» круговым методом (circle
method): для ``n`` участников — ``n-1`` туров по ``n/2`` партий, нечётное число
дополняется фиктивным «bye» (его партии пропускаются). Цвета чередуются по туру и
доске, чтобы у моделей было примерно поровну белых и чёрных. ``double=True`` даёт
двойной круг: второй проход с теми же парами, но переменой цвета.

``new_tournament_record`` собирает ``TournamentRecord`` из участников (``PlayerInfo``),
планируя партии ``round_robin`` по их ``model_id``.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from arena.models import PlayerInfo
from arena.tournament.models import TournamentGame, TournamentRecord

# Метка-заполнитель для нечётного числа участников (этот «игрок» пропускает тур).
_BYE = "__bye__"


def round_robin(
    models: Sequence[str], *, double: bool = False
) -> list[TournamentGame]:
    """Составить расписание round-robin по ``model_id`` (список ``TournamentGame``).

    Каждая неупорядоченная пара встречается ровно один раз (``double=True`` — два
    раза с переменой цвета). Туры нумеруются с 1; при ``double`` второй круг
    продолжает нумерацию. Меньше двух участников → пустое расписание.
    """
    players = list(models)
    if len(players) < 2:
        return []

    if len(players) % 2 == 1:
        players.append(_BYE)
    n = len(players)

    # Круговой метод даёт неупорядоченные пары по турам; цвет назначаем отдельно,
    # жадно балансируя, чтобы у каждой модели было поровну белых и чёрных.
    rounds: list[list[tuple[str, str]]] = []
    order = players[:]
    for _ in range(n - 1):
        pairs: list[tuple[str, str]] = []
        for board in range(n // 2):
            a = order[board]
            b = order[n - 1 - board]
            if a != _BYE and b != _BYE:
                pairs.append((a, b))
        rounds.append(pairs)
        # Круговая ротация: первый фиксирован, остальные сдвигаются.
        order = [order[0], order[-1], *order[1:-1]]

    # Жадный баланс цветов: белыми идёт тот, у кого пока меньше партий белыми
    # (``balance`` = «белые минус чёрные»). Держит |белые−чёрные| ≈ 0 у каждого.
    balance: dict[str, int] = {p: 0 for p in players if p != _BYE}

    def _colored(a: str, b: str) -> tuple[str, str]:
        white, black = (a, b) if balance[a] <= balance[b] else (b, a)
        balance[white] += 1
        balance[black] -= 1
        return white, black

    games: list[TournamentGame] = []
    for round_index, pairs in enumerate(rounds, start=1):
        for a, b in pairs:
            white, black = _colored(a, b)
            games.append(
                TournamentGame(round_number=round_index, white=white, black=black)
            )

    if double:
        # Второй круг: те же пары с переменой цвета — это и доигрывает баланс до
        # идеального (у каждого ровно поровну белых и чёрных за оба круга).
        base = len(rounds)
        single = list(games)
        for game in single:
            games.append(
                TournamentGame(
                    round_number=base + game.round_number,
                    white=game.black,
                    black=game.white,
                )
            )

    return games


def new_tournament_record(
    participants: Sequence[PlayerInfo],
    *,
    tournament_id: str,
    created_at: datetime,
    double: bool = False,
) -> TournamentRecord:
    """Построить ``TournamentRecord`` с расписанием round-robin по ``participants``.

    ``id`` и ``created_at`` задаёт вызывающий (детерминизм в тестах, без обращения
    к часам внутри). Партии планируются ``round_robin`` по ``model_id`` участников.
    """
    games = round_robin([p.model_id for p in participants], double=double)
    return TournamentRecord(
        id=tournament_id,
        created_at=created_at,
        participants=list(participants),
        double=double,
        games=games,
    )
