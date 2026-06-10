"""★ Обёртка над Stockfish (UCI): подсказки и оценки. Опциональна."""

from arena.engine.cache import CachingEngine
from arena.engine.factory import build_engine
from arena.engine.stockfish import (
    DEFAULT_DEPTH,
    EngineOpener,
    EngineUnavailableError,
    StockfishEngine,
)

__all__ = [
    "DEFAULT_DEPTH",
    "CachingEngine",
    "EngineOpener",
    "EngineUnavailableError",
    "StockfishEngine",
    "build_engine",
]
