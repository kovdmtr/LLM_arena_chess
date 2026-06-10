"""★ Единая точка включения движка: построить Stockfish из конфига — или ``None``.

Деградация без движка (D-008) разбросана по точкам потребления: ``GameRunner``
не выдаёт подсказки без движка, ``analyze_game`` возвращает ``None``. Чтобы
*решение* «движок есть / движка нет» принималось **в одном месте**, а не у каждого
вызывающего, здесь живёт ``build_engine``:

- ``engine.enabled = false`` в конфиге → ``None`` (★ отключены сознательно);
- бинарник не запускается (`EngineUnavailableError`) → ``None`` (★ деградируют);
- иначе → готовый **открытый** ``StockfishEngine`` (процесс уже поднят, так что
  недоступность обнаруживается сразу, а не при первом ходе).

Вызывающий просто проверяет ``if engine is not None`` — никакой обработки
исключений и проверки бинарника на его стороне.
"""

from __future__ import annotations

from arena.config.settings import EngineConfig
from arena.engine.cache import CachingEngine
from arena.engine.stockfish import (
    EngineOpener,
    EngineUnavailableError,
    StockfishEngine,
)


def build_engine(
    config: EngineConfig,
    *,
    depth: int | None = None,
    opener: EngineOpener | None = None,
    cache: bool = False,
) -> StockfishEngine | CachingEngine | None:
    """Построить открытый движок из ``config`` или вернуть ``None``.

    ``None`` означает «★-фичи выключены» — либо движок отключён в конфиге
    (``enabled=false``), либо бинарник недоступен (``EngineUnavailableError`` при
    запуске). ``depth`` задаёт глубину по умолчанию (обычно ``hint_depth``; для
    пост-анализа глубину передают в ``analyze_game(depth=...)``). ``opener`` —
    шов для тестов (подмена UCI-процесса). ``cache=True`` оборачивает движок в
    ``CachingEngine`` (кеш оценок по ``(fen, depth)``) — полезно при анализе многих
    партий (турнир), где повторяются дебютные позиции.
    """
    if not config.enabled:
        return None
    engine = StockfishEngine(
        config.path,
        depth=depth if depth is not None else config.hint_depth,
        opener=opener,
    )
    try:
        engine.open()
    except EngineUnavailableError:
        return None
    return CachingEngine(engine) if cache else engine
