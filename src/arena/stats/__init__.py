"""★ Агрегированная статистика моделей по множеству партий (опц., Phase 8)."""

from arena.stats.aggregate import (
    ModelStats,
    StatsTable,
    aggregate_stats,
    load_records,
)

__all__ = [
    "ModelStats",
    "StatsTable",
    "aggregate_stats",
    "load_records",
]
