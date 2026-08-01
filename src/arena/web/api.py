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
from arena.models import PlayerInfo
from arena.prompts import SUPPORTED_LANGUAGES
from arena.report import render_report_html
from arena.providers import ProviderError
from arena.web.games import STATUS_FINISHED, GameInfo, GameManager
from arena.web.tournaments import TournamentInfo, TournamentManager

CatalogGetter = Callable[[Any], ModelCatalog]
ManagerGetter = Callable[[Any], GameManager]
TournamentManagerGetter = Callable[[Any], TournamentManager]

# Имя файла в Content-Disposition собираем только из безопасных символов.
_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]")


class StartGameRequest(BaseModel):
    """Тело ``POST /api/games``: модели по сторонам и язык интерфейса."""

    white: str
    black: str
    language: str | None = None


class StartTournamentRequest(BaseModel):
    """Тело ``POST /api/tournaments``: участники (≥2), формат и язык интерфейса."""

    models: list[str]
    double: bool = False
    language: str | None = None


def api_error(
    status_code: int,
    code: str,
    *,
    params: dict[str, Any] | None = None,
    message: str | None = None,
) -> HTTPException:
    """Ошибка API с машиночитаемым кодом.

    Интерфейс одноязычный (RU **или** EN), а тексты нижних слоёв — русские,
    поэтому наружу отдаём ``detail = {code, params, message}``: ``code`` фронт
    переводит на язык интерфейса, ``params`` подставляет в фразу, ``message``
    остаётся технической подробностью (показывается, только если код незнаком).
    """
    detail: dict[str, Any] = {"code": code}
    if params:
        detail["params"] = params
    if message:
        detail["message"] = message
    return HTTPException(status_code=status_code, detail=detail)


def _resolve_model(catalog: ModelCatalog, model_id: str) -> Any:
    """Резолвнуть модель каталога или поднять 400 с кодом причины."""
    try:
        catalog.get(model_id)
    except ConfigError as exc:
        raise api_error(
            400, "error.modelUnknown", params={"id": model_id}, message=str(exc)
        ) from exc
    try:
        if not catalog.has_key(model_id):
            raise api_error(400, "error.modelNoKey", params={"id": model_id})
        return catalog.resolve(model_id)
    except ConfigError as exc:  # напр. модель ссылается на неизвестного провайдера
        raise api_error(
            400, "error.modelUnavailable", params={"id": model_id}, message=str(exc)
        ) from exc


def _normalize_language(code: str | None) -> str | None:
    """Код языка интерфейса → поддерживаемый промптом или ``None``.

    Незнакомый код не ошибка: партия просто играется без указания языка (как и
    было до фичи), а не падает с 400 из-за косметического поля.
    """
    normalized = (code or "").strip().lower()
    return normalized if normalized in SUPPORTED_LANGUAGES else None


def build_api_router(
    *,
    get_catalog: CatalogGetter,
    get_manager: ManagerGetter,
    get_tournament_manager: TournamentManagerGetter,
) -> APIRouter:
    """Собрать роутер ``/api`` поверх каталога, планировщика партий и турниров."""
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
        ключа) — ошибка отдаётся как 400 с кодом причины, чтобы фронт показал её
        в форме на языке интерфейса.
        """
        catalog = get_catalog(request.app)
        resolved = {
            "white": _resolve_model(catalog, payload.white),
            "black": _resolve_model(catalog, payload.black),
        }
        try:
            session = get_manager(request.app).start(
                resolved, language=_normalize_language(payload.language)
            )
        except ProviderError as exc:
            raise api_error(400, "error.startFailed", message=str(exc)) from exc
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
            raise api_error(404, "error.gameNotFound", params={"id": game_id})
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
            raise api_error(404, "error.gameNotFound", params={"id": game_id})
        filename = _UNSAFE_FILENAME.sub("_", record.id) or "game"
        return Response(
            content=build_pgn(record) + "\n",
            media_type="application/x-chess-pgn; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}.pgn"'},
        )

    @router.get("/games/{game_id}/report")
    def api_game_report(request: Request, game_id: str) -> Response:
        """Самодостаточный HTML-отчёт партии как файл на скачивание (D-013).

        Разбор партии показывает SPA, а этот файл — то же самое, но автономно:
        открывается без сети и без сервера, поэтому ссылки «на главную» в нём нет.
        """
        record = get_manager(request.app).load_record(game_id)
        if record is None:
            raise api_error(404, "error.gameNotFound", params={"id": game_id})
        filename = _UNSAFE_FILENAME.sub("_", record.id) or "game"
        return Response(
            content=render_report_html(record),
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}.html"'},
        )

    # --- турниры --------------------------------------------------------------

    @router.post("/tournaments", status_code=status.HTTP_201_CREATED)
    def api_start_tournament(
        request: Request, payload: StartTournamentRequest
    ) -> dict[str, str]:
        """Запустить round-robin турнир в фоне и вернуть его ``id``.

        Требуется ≥2 различных модели (дубли схлопываются, порядок сохраняется);
        каждая резолвится через каталог — fail-fast по отсутствию ключа. Ошибки
        валидации отдаются как 400 с кодом причины для формы.
        """
        catalog = get_catalog(request.app)
        model_ids = list(dict.fromkeys(payload.models))  # дедуп, порядок сохранён
        if len(model_ids) < 2:
            raise api_error(400, "error.tournamentTooFewModels")
        participants: list[PlayerInfo] = []
        for model_id in model_ids:
            _resolve_model(catalog, model_id)  # fail-fast: ключ обязателен
            model = catalog.get(model_id)
            participants.append(
                PlayerInfo(
                    model_id=model.id,
                    provider=model.provider,
                    display_name=model.display_name,
                )
            )
        session = get_tournament_manager(request.app).start(
            participants,
            double=payload.double,
            language=_normalize_language(payload.language),
        )
        return {"id": session.id}

    @router.get("/tournaments")
    def api_tournaments(request: Request) -> list[dict[str, Any]]:
        """Список турниров (память + диск) с прогрессом ``played/total``."""
        manager = get_tournament_manager(request.app)
        return [_tournament_info(info) for info in manager.list_tournaments()]

    @router.get("/tournaments/{tournament_id}")
    def api_tournament(request: Request, tournament_id: str) -> dict[str, Any]:
        """Турнир целиком: участники, статус, прогресс, таблица и расписание.

        Для идущего турнира таблица частичная (по сыгранным партиям) — фронт
        обновляет страницу по таймеру, пока ``live``.
        """
        manager = get_tournament_manager(request.app)
        record = manager.load_record(tournament_id)
        if record is None:
            raise api_error(404, "error.tournamentNotFound", params={"id": tournament_id})
        session = manager.get(tournament_id)
        live = session is not None and not session.done
        standings = manager.load_standings(tournament_id)
        names = {p.model_id: p.display_name for p in record.participants}
        schedule = [
            {
                "round": game.round_number,
                "white": game.white,
                "black": game.black,
                "white_name": names.get(game.white, game.white),
                "black_name": names.get(game.black, game.black),
                "result": game.result,
                "game_id": game.game_id,
            }
            for game in record.games
        ]
        return {
            "id": tournament_id,
            "live": live,
            "status": session.status if session is not None else STATUS_FINISHED,
            "error": session.error if session is not None else None,
            "double": record.double,
            "created_at": record.created_at.isoformat(),
            "participants": [p.model_dump(mode="json") for p in record.participants],
            "played": sum(1 for game in record.games if game.result is not None),
            "total": len(record.games),
            "standings": (
                standings.model_dump(mode="json")
                if standings is not None
                else {"models": [], "total_games": 0}
            ),
            "schedule": schedule,
        }

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


def _tournament_info(info: TournamentInfo) -> dict[str, Any]:
    """``TournamentInfo`` → JSON-карточка турнира для списка."""
    return {
        "id": info.id,
        "participants": list(info.participants),
        "double": info.double,
        "status": info.status,
        "played": info.played,
        "total": info.total,
        "live": info.live,
        "created_at": info.created_at.isoformat(),
    }
