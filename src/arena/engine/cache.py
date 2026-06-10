"""★ Кеш оценок позиций поверх движка (Phase 8, бэклог-3).

Пост-анализ и подсказки часто оценивают одни и те же позиции: дебютные ходы
повторяются между партиями турнира, а внутри партии анализ обращается к движку по
FEN. ``CachingEngine`` — прозрачная обёртка над любым движком с тем же контрактом
(``evaluate``/``best_move``/``close`` + контекстный менеджер), которая запоминает
результат по ключу ``(fen, depth)`` и при повторном запросе возвращает его без
обращения к движку.

Обёртка — drop-in: её можно передать везде, где ждут ``StockfishEngine`` (в
``GameRunner`` как ``HintEngine`` и в ``analyze_game`` как ``EvalEngine``).
``build_engine(..., cache=True)`` оборачивает движок автоматически. Кеш живёт,
пока жива обёртка, поэтому для переиспользования между партиями (турнир) держите
один ``CachingEngine`` на весь прогон.
"""

from __future__ import annotations

from typing import Protocol

from arena.models import HintRecord


class _Engine(Protocol):
    """Минимальный контракт оборачиваемого движка (как у ``StockfishEngine``)."""

    def evaluate(self, fen: str, *, depth: int | None = None) -> int: ...
    def best_move(self, fen: str, *, depth: int | None = None) -> HintRecord: ...
    def close(self) -> None: ...


class CachingEngine:
    """Обёртка над движком с кешем результатов ``evaluate``/``best_move``.

    Ключ кеша — ``(fen, depth)``: одна и та же позиция на разной глубине кешируется
    отдельно (оценки несравнимы). ``hits``/``misses`` доступны для наблюдения.
    Методы жизненного цикла (``open``/``close``/контекстный менеджер) делегируются
    внутреннему движку, так что обёртка взаимозаменяема с ним.
    """

    def __init__(self, inner: _Engine) -> None:
        self.inner = inner
        self._eval_cache: dict[tuple[str, int | None], int] = {}
        self._move_cache: dict[tuple[str, int | None], HintRecord] = {}
        self.hits = 0
        self.misses = 0

    def evaluate(self, fen: str, *, depth: int | None = None) -> int:
        """Оценка позиции с кешированием по ``(fen, depth)``."""
        key = (fen, depth)
        cached = self._eval_cache.get(key)
        if cached is not None:
            self.hits += 1
            return cached
        self.misses += 1
        value = self.inner.evaluate(fen, depth=depth)
        self._eval_cache[key] = value
        return value

    def best_move(self, fen: str, *, depth: int | None = None) -> HintRecord:
        """Лучший ход с кешированием по ``(fen, depth)``."""
        key = (fen, depth)
        cached = self._move_cache.get(key)
        if cached is not None:
            self.hits += 1
            return cached
        self.misses += 1
        hint = self.inner.best_move(fen, depth=depth)
        self._move_cache[key] = hint
        return hint

    @property
    def cache_info(self) -> dict[str, int]:
        """Счётчики кеша: попадания/промахи и размеры словарей (для наблюдения/тестов)."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "eval_entries": len(self._eval_cache),
            "move_entries": len(self._move_cache),
        }

    def clear_cache(self) -> None:
        """Очистить кеш (счётчики сбрасываются)."""
        self._eval_cache.clear()
        self._move_cache.clear()
        self.hits = 0
        self.misses = 0

    # --- делегирование жизненного цикла внутреннему движку ----------------

    def open(self) -> "CachingEngine":
        opener = getattr(self.inner, "open", None)
        if opener is not None:
            opener()
        return self

    def close(self) -> None:
        self.inner.close()

    def __enter__(self) -> "CachingEngine":
        return self.open()

    def __exit__(self, *exc_info) -> None:
        self.close()
