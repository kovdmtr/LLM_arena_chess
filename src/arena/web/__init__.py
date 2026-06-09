"""★ Веб-интерфейс (FastAPI + WebSocket): выбор моделей и живой просмотр."""

from arena.web.app import APP_TITLE, APP_VERSION, create_app
from arena.web.games import GameInfo, GameManager, GameSession

__all__ = [
    "APP_TITLE",
    "APP_VERSION",
    "GameInfo",
    "GameManager",
    "GameSession",
    "create_app",
]
