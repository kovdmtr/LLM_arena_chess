"""JSON-API веб-слоя — данные для SPA-фронтенда.

Тонкие обёртки над готовыми менеджерами (``GameManager``/``TournamentManager``) и
каталогом моделей: логика уже реализована в слоях ``arena.*``, здесь только
сериализация в JSON. SSR-роуты (``app.py``) остаются рядом и используют те же
менеджеры — контракт партии/турнира един (см. ``docs/FRONTEND.md`` §7).

Роутер собирается фабрикой ``build_api_router``, которой передают акцессоры
приложения (``get_catalog``/``get_manager``). Так модуль не импортирует ``app.py``
и не образует цикла импортов.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from arena.config import ConfigError, ModelCatalog
from arena.core import build_pgn
from arena.providers import ProviderError
from arena.web.games import STATUS_FINISHED, GameInfo, GameManager

CatalogGetter = Callable[[Any], ModelCatalog]
ManagerGetter = Callable[[Any], GameManager]

# Имя файла в Content-Disposition собираем только из безопасных символов.
_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]")


class StartGameRequest(BaseModel):
    """Тело ``POST /api/games``: идентификаторы моделей по сторонам."""

    white: str
    black: str


def build_api_router(
    *, get_catalog: CatalogGetter, get_manager: ManagerGetter
) -> APIRouter:
    """Собрать роутер ``/api`` поверх каталога моделей и планировщика партий."""
    router = APIRouter(prefix="/api", tags=["api"])

    @router.get("/models")
    def api_models(request: Request) -> list[dict[str, Any]]:
        """Каталог моделей: что можно выбрать и у чего есть ключ.

        ``has_key=false`` — модель показывается, но выбрать её нельзя (ключ не задан).
        Сам ключ наружу не отдаётся (D-003).
        """
        catalog = get_catalog(request.app)
        return [
            {
                "id": model.id,
                "display_name": model.display_name,
                "provider": model.provider,
                "has_key": catalog.has_key(model.id),
            }
            for model in catalog.models
        ]

    @router.post("/games", status_code=status.HTTP_201_CREATED)
    def api_start_game(request: Request, payload: StartGameRequest) -> dict[str, str]:
        """Запустить партию в фоне и вернуть её ``id``.

        Модели резолвятся через каталог (fail-fast: неизвестная модель или нет
        ключа) — ошибка отдаётся как 400 с человекочитаемым текстом, чтобы фронт
        показал её в форме.
        """
        catalog = get_catalog(request.app)
        try:
            resolved = {
                "white": catalog.resolve(payload.white),
                "black": catalog.resolve(payload.black),
            }
            session = get_manager(request.app).start(resolved)
        except (ConfigError, ProviderError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"id": session.id}

    @router.get("/games")
    def api_games(request: Request) -> list[dict[str, Any]]:
        """Список партий (память + диск) — карточки для архива."""
        return [_game_info(info) for info in get_manager(request.app).list_games()]

    @router.get("/games/{game_id}")
    def api_game(request: Request, game_id: str) -> dict[str, Any]:
        """Партия целиком: статус + ``GameRecord`` (ходы, рассуждения, план, ★-анализ).

        Идущая партия отдаётся так же — с уже сыгранными ходами: фронт использует
        это для гидратации после перезагрузки, а дальше слушает ``WS /games/{id}/ws``.
        """
        manager = get_manager(request.app)
        record = manager.load_record(game_id)
        if record is None:
            raise HTTPException(status_code=404, detail="партия не найдена")
        session = manager.get(game_id)
        live = session is not None and not session.done
        return {
            "id": game_id,
            "live": live,
            "status": session.status if session is not None else STATUS_FINISHED,
            "error": session.error if session is not None else None,
            "record": record.model_dump(mode="json"),
        }

    @router.get("/games/{game_id}/pgn")
    def api_game_pgn(request: Request, game_id: str) -> Response:
        """PGN партии как файл на скачивание (тот же ``core.build_pgn``, что и в отчёте)."""
        record = get_manager(request.app).load_record(game_id)
        if record is None:
            raise HTTPException(status_code=404, detail="партия не найдена")
        filename = _UNSAFE_FILENAME.sub("_", record.id) or "game"
        return Response(
            content=build_pgn(record) + "\n",
            media_type="application/x-chess-pgn; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}.pgn"'},
        )

    return router


def _game_info(info: GameInfo) -> dict[str, Any]:
    """``GameInfo`` → JSON-карточка партии для списка."""
    return {
        "id": info.id,
        "white": info.white,
        "black": info.black,
        "status": info.status,
        "result": info.result,
        "live": info.live,
        "created_at": info.created_at.isoformat(),
    }
