"""★ UCI-обёртка над Stockfish через ``python-chess`` (D-008).

Движок опционален: без бинарника ★-фичи (подсказки D-010, пост-анализ D-009)
деградируют, база работает (D-008). Обёртка закрывает обе задачи одним процессом:

- ``best_move(fen)`` — лучший ход + оценка для подсказки (``HintRecord``, D-010);
- ``evaluate(fen)`` — оценка позиции в сантипешках с точки зрения ходящей стороны
  (для centipawn-loss анализа D-009).

Жизненный цикл UCI-процесса — через контекстный менеджер (``with StockfishEngine()
as engine: ...``) либо явные ``open()``/``close()``. Если бинарник недоступен —
``EngineUnavailableError`` (вызывающий код отключает ★-фичи с предупреждением).

Логика разбора оценок не зависит от реального процесса: конструктор принимает
``opener`` (фабрику движка), что позволяет юнит-тестам подменять транспорт, а
интеграционным — пропускаться без бинарника.
"""

from __future__ import annotations

from typing import Callable

import chess
import chess.engine

from arena.models import HintRecord

# Глубина анализа по умолчанию (совпадает с ``EngineConfig`` в config.yaml).
DEFAULT_DEPTH = 18

# Конечная замена ±мату при сведе́нии оценки к целому числу сантипешек: мат лучше
# любой материальной оценки, поэтому берётся заведомо большим (±100 пешек).
_MATE_SCORE = 100_000

# Тип фабрики движка: вызывается без аргументов, возвращает UCI-движок.
EngineOpener = Callable[[], "chess.engine.SimpleEngine"]


class EngineUnavailableError(RuntimeError):
    """Stockfish недоступен (нет бинарника/не запускается) — ★-фичи отключаются."""


class StockfishEngine:
    """Обёртка над UCI-движком: лучший ход и оценка позиции по FEN.

    ``path`` — путь к бинарнику или имя в PATH. ``depth`` — глубина анализа по
    умолчанию (переопределяется аргументом методов). Процесс запускается лениво
    при первом обращении (или в ``open()``/``__enter__``) и закрывается в
    ``close()``/``__exit__``.
    """

    def __init__(
        self,
        path: str = "stockfish",
        *,
        depth: int = DEFAULT_DEPTH,
        opener: EngineOpener | None = None,
    ) -> None:
        self.path = path
        self.depth = depth
        # По умолчанию запускаем реальный Stockfish; тесты подменяют ``opener``.
        self._opener: EngineOpener = opener or (
            lambda: chess.engine.SimpleEngine.popen_uci(path)
        )
        self._engine: chess.engine.SimpleEngine | None = None

    # --- жизненный цикл процесса ------------------------------------------

    def open(self) -> "StockfishEngine":
        """Запустить UCI-процесс (идемпотентно). ``EngineUnavailableError`` при сбое."""
        if self._engine is None:
            try:
                self._engine = self._opener()
            except (FileNotFoundError, OSError, chess.engine.EngineError) as exc:
                raise EngineUnavailableError(
                    f"не удалось запустить движок {self.path!r}: {exc}"
                ) from exc
        return self

    def close(self) -> None:
        """Завершить UCI-процесс (идемпотентно)."""
        if self._engine is not None:
            self._engine.quit()
            self._engine = None

    def __enter__(self) -> "StockfishEngine":
        return self.open()

    def __exit__(self, *exc_info) -> None:
        self.close()

    # --- анализ ------------------------------------------------------------

    def _analyse(self, fen: str, depth: int | None) -> chess.engine.InfoDict:
        """Проанализировать позицию ``fen`` и вернуть ``InfoDict`` (pv + score)."""
        self.open()
        assert self._engine is not None  # open() гарантирует процесс
        board = chess.Board(fen)
        limit = chess.engine.Limit(depth=depth if depth is not None else self.depth)
        return self._engine.analyse(board, limit)

    def best_move(self, fen: str, *, depth: int | None = None) -> HintRecord:
        """Вернуть лучший ход и оценку позиции ``fen`` как ``HintRecord`` (D-010).

        ``best_move`` — рекомендованный ход в UCI; ``eval_cp``/``mate_in`` — оценка
        с точки зрения ходящей стороны (``eval_cp`` равен ``None`` при форсированном
        мате — тогда заполняется ``mate_in``).
        """
        info = self._analyse(fen, depth)
        pv = info.get("pv")
        if not pv:
            raise EngineUnavailableError(f"движок не предложил ход для позиции: {fen}")
        score = info["score"].relative  # с точки зрения ходящей стороны
        return HintRecord(
            best_move=pv[0].uci(),
            eval_cp=score.score(),  # None при мате
            mate_in=score.mate(),  # None, если не мат
        )

    def evaluate(self, fen: str, *, depth: int | None = None) -> int:
        """Вернуть оценку позиции ``fen`` в сантипешках с точки зрения ходящей стороны.

        Форсированный мат сводится к конечному значению (``±_MATE_SCORE``), чтобы
        результат всегда был целым числом — это удобно для centipawn-loss анализа
        (D-009): мат строго лучше/хуже любой материальной оценки.
        """
        info = self._analyse(fen, depth)
        return info["score"].relative.score(mate_score=_MATE_SCORE)
