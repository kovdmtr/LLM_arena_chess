"""★ Обёртка над Stockfish (UCI): подсказки и оценки. Опциональна."""

from arena.engine.factory import build_engine
from arena.engine.stockfish import (
    DEFAULT_DEPTH,
    EngineOpener,
    EngineUnavailableError,
    StockfishEngine,
)

__all__ = [
    "DEFAULT_DEPTH",
    "EngineOpener",
    "EngineUnavailableError",
    "StockfishEngine",
    "build_engine",
]
