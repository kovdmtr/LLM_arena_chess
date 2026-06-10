"""★ Агрегированная статистика моделей по множеству партий (Phase 8, бэклог-2).

Когда сыграно несколько партий (вручную или турниром), хочется сводную таблицу:
кто сколько сыграл, выиграл/проиграл/свёл вничью, сколько набрал очков и какова
средняя точность ходов. ``aggregate_stats`` проходит по ``GameRecord``-ам и
сворачивает их в ``StatsTable`` — список ``ModelStats`` (одна строка на модель),
отсортированный по очкам.

Идентичность модели — её ``model_id`` (``PlayerInfo.model_id``, стабилен; D-003 —
секретов в записи нет). Одна и та же модель, сыгравшая и за белых, и за чёрных в
разных партиях, попадает в **одну** строку: счётчики складываются по обеим сторонам.

Учитываются только **завершённые** партии (``result`` ∈ ``1-0`` / ``0-1`` /
``1/2-1/2``); незавершённые (``"*"``) не дают очков, но модель-участник всё равно
появляется в таблице (со ``games = 0``), чтобы было видно состав. Счётчики ошибок и
средняя точность берутся из пост-анализа (★, D-009), если он есть; подсказки — из
``GameRecord.hints_used``.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel, Field

from arena.models import GameRecord, Side
from arena.storage import (
    DEFAULT_GAMES_ROOT,
    GAME_JSON_NAME,
    StorageError,
    load_game,
)

# Результаты, считающиеся завершённой партией (учитываются в таблице).
_DECISIVE = {"1-0", "0-1", "1/2-1/2"}

_SIDES: tuple[Side, Side] = ("white", "black")


class ModelStats(BaseModel):
    """Сводная строка по одной модели за все её партии.

    ``games`` — число завершённых партий с участием модели; ``points`` — очки
    (победа 1, ничья ½, поражение 0); ``score_pct`` — доля очков от максимума
    (``points / games * 100``). ``avg_accuracy`` — средняя точность ходов из
    пост-анализа (0..1) по партиям, где она доступна, иначе ``None``. Счётчики
    ошибок и подсказок суммируются по обеим сторонам.
    """

    # ``model_id`` начинается с зарезервированного префикса ``model_`` — снимаем
    # защиту пространства имён pydantic (как в ``PlayerInfo``).
    model_config = {"protected_namespaces": ()}

    model_id: str
    display_name: str
    games: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    points: float = 0.0
    score_pct: float = 0.0
    avg_accuracy: float | None = None
    blunders: int = 0
    mistakes: int = 0
    inaccuracies: int = 0
    hints_used: int = 0


class StatsTable(BaseModel):
    """Таблица статистики: строки по моделям + число учтённых партий."""

    models: list[ModelStats] = Field(default_factory=list)
    total_games: int = 0


def aggregate_stats(records: Iterable[GameRecord]) -> StatsTable:
    """Свернуть партии в ``StatsTable`` (строка на модель, сортировка по очкам).

    ``total_games`` — число **завершённых** партий (по одной на запись, не на
    сторону). Сортировка строк: очки убыв., затем ``score_pct`` убыв., затем имя.
    """
    stats: dict[str, ModelStats] = {}
    accuracies: dict[str, list[float]] = {}
    counted = 0

    for record in records:
        # Бакет на каждого участника — даже если партия не доиграна (чтобы модель
        # появилась в таблице). display_name берём при первом появлении.
        for side in _SIDES:
            player = record.players[side]
            if player.model_id not in stats:
                stats[player.model_id] = ModelStats(
                    model_id=player.model_id, display_name=player.display_name
                )
                accuracies[player.model_id] = []

        if record.result not in _DECISIVE:
            continue
        counted += 1

        white_id = record.players["white"].model_id
        black_id = record.players["black"].model_id
        for model_id in (white_id, black_id):
            stats[model_id].games += 1

        if record.result == "1-0":
            _record_result(stats[white_id], stats[black_id])
        elif record.result == "0-1":
            _record_result(stats[black_id], stats[white_id])
        else:  # "1/2-1/2"
            stats[white_id].draws += 1
            stats[black_id].draws += 1

        for side, model_id in zip(_SIDES, (white_id, black_id)):
            if record.analysis is not None:
                pa = getattr(record.analysis, side)
                stats[model_id].blunders += pa.blunders
                stats[model_id].mistakes += pa.mistakes
                stats[model_id].inaccuracies += pa.inaccuracies
                if pa.accuracy is not None:
                    accuracies[model_id].append(pa.accuracy)
            stats[model_id].hints_used += record.hints_used.get(side, 0)

    for model_id, row in stats.items():
        row.points = row.wins + row.draws * 0.5
        row.score_pct = (row.points / row.games * 100.0) if row.games else 0.0
        acc = accuracies[model_id]
        row.avg_accuracy = (sum(acc) / len(acc)) if acc else None

    ordered = sorted(
        stats.values(),
        key=lambda r: (-r.points, -r.score_pct, r.display_name),
    )
    return StatsTable(models=ordered, total_games=counted)


def _record_result(winner: ModelStats, loser: ModelStats) -> None:
    """Зафиксировать решительный исход: победитель +победа, проигравший +поражение."""
    winner.wins += 1
    loser.losses += 1


def load_records(
    games_root: str | Path = DEFAULT_GAMES_ROOT,
) -> list[GameRecord]:
    """Загрузить все ``GameRecord`` из ``games_root`` (по папкам с ``game.json``).

    Битые/нечитаемые записи пропускаются (не валят агрегацию). Возвращает список,
    отсортированный по имени папки; пустой, если каталога нет.
    """
    root = Path(games_root)
    if not root.is_dir():
        return []
    records: list[GameRecord] = []
    for child in sorted(root.iterdir()):
        if not (child / GAME_JSON_NAME).is_file():
            continue
        try:
            records.append(load_game(child))
        except StorageError:
            continue
    return records
