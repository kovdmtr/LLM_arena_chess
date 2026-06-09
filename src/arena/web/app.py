"""★ FastAPI-приложение арены — каркас (D-002).

``create_app`` собирает приложение: health-эндпоинт, монтирование статики
(``/static``), Jinja2-шаблоны и стартовую страницу (``/``). Это фундамент Phase 6:
последующие задачи добавляют сюда страницу выбора моделей, запуск партии,
WebSocket-живой просмотр и список/просмотр отчётов (см. ROADMAP).

Фабрика, а не глобальный объект: ``create_app`` строит изолированный экземпляр
(удобно для тестов и для инъекции ``Settings``). Готовые настройки можно передать
явно; иначе роуты, которым они нужны, загрузят их лениво (каркасу — health/static/
индекс — настройки не требуются). Для ``uvicorn`` в конце модуля собран
экземпляр ``app`` (``uvicorn arena.web.app:app``).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request, WebSocket, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from arena.config import ConfigError, ModelCatalog, Settings
from arena.web.games import GameManager
from arena.web.live import stream_session

# Каталог пакета веб-слоя; статика и шаблоны лежат рядом с этим модулем.
_WEB_DIR = Path(__file__).resolve().parent
STATIC_DIR = _WEB_DIR / "static"
TEMPLATES_DIR = _WEB_DIR / "templates"

APP_TITLE = "LLM Chess Arena"
APP_VERSION = "0.1.0"


def create_app(
    settings: Settings | None = None,
    *,
    game_manager: GameManager | None = None,
) -> FastAPI:
    """Собрать экземпляр FastAPI-приложения арены (Phase 6).

    ``settings`` (опц.) кладётся в ``app.state.settings``; роуты, которым нужен
    каталог моделей, строят его лениво (``_get_catalog``) — загрузкой ``Settings``
    из ``config.yaml``/``.env``, если он не передан. ``game_manager`` (опц.)
    переопределяет планировщик фоновых партий (шов для тестов с фейковыми игроками);
    по умолчанию строится лениво из настроек (``_get_manager``). Шаблоны доступны как
    ``app.state.templates``. Монтируется статика ``/static`` и поднимается health.
    """
    app = FastAPI(title=APP_TITLE, version=APP_VERSION)
    app.state.settings = settings
    app.state.catalog = None  # строится лениво из settings (см. _get_catalog)
    app.state.game_manager = game_manager  # либо лениво в _get_manager

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.state.templates = templates

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/health")
    def health() -> dict[str, str]:
        """Проверка живости сервиса (для мониторинга/тестов)."""
        return {"status": "ok", "service": APP_TITLE, "version": APP_VERSION}

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        """Стартовая страница арены."""
        return templates.TemplateResponse(
            request, "index.html", {"title": APP_TITLE}
        )

    @app.get("/games/new", response_class=HTMLResponse)
    def new_game(request: Request) -> HTMLResponse:
        """Страница выбора моделей: форма выбора белых/чёрных из каталога.

        Форма отправляется на ``POST /games`` (запуск партии). Модели без заданного
        API-ключа показываются, но помечены и недоступны для выбора (ключ не задан).
        """
        return _render_new_game(request, _get_catalog(request.app))

    @app.post("/games", response_model=None)
    def start_game(
        request: Request,
        white: str = Form(...),
        black: str = Form(...),
    ) -> HTMLResponse | RedirectResponse:
        """Запустить партию между выбранными моделями и перенаправить на её страницу.

        Модели резолвятся через каталог (fail-fast при неизвестной модели или
        отсутствии ключа, ``ConfigError``) — при ошибке форма перерисовывается с
        сообщением (400). При успехе партия стартует в фоне (``GameManager``), а
        браузер редиректится (303) на ``/games/{id}`` — её страницу/живой просмотр.
        """
        catalog = _get_catalog(request.app)
        try:
            resolved = {
                "white": catalog.resolve(white),
                "black": catalog.resolve(black),
            }
        except ConfigError as exc:
            return _render_new_game(
                request, catalog, error=str(exc),
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        session = _get_manager(request.app).start(resolved)
        return RedirectResponse(
            f"/games/{session.id}", status_code=status.HTTP_303_SEE_OTHER
        )

    @app.websocket("/games/{game_id}/ws")
    async def game_ws(websocket: WebSocket, game_id: str) -> None:
        """Live-просмотр партии: replay накопленных событий + стрим новых."""
        session = _get_manager(websocket.app).get(game_id)
        await stream_session(websocket, session)

    return app


def _render_new_game(
    request: Request,
    catalog: ModelCatalog,
    *,
    error: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    """Отрисовать страницу выбора моделей (``new_game.html``) из каталога.

    ``error`` (опц.) показывается над формой; используется для перерисовки после
    неудачного ``POST /games`` (например, у выбранной модели нет ключа).
    """
    models = [
        {
            "id": model.id,
            "display_name": model.display_name,
            "provider": model.provider,
            "has_key": catalog.has_key(model.id),
        }
        for model in catalog.models
    ]
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "new_game.html",
        {"title": f"{APP_TITLE} — новая партия", "models": models, "error": error},
        status_code=status_code,
    )


def _get_catalog(app: FastAPI) -> ModelCatalog:
    """Вернуть каталог моделей приложения, построив его лениво при первом обращении.

    Использует ``app.state.settings`` (если передан в ``create_app``) или загружает
    ``Settings`` из ``config.yaml``/``.env``. Результат кэшируется в
    ``app.state.catalog`` — каталог строится один раз на приложение.
    """
    catalog = getattr(app.state, "catalog", None)
    if catalog is None:
        settings = app.state.settings or Settings.load()
        app.state.settings = settings
        catalog = ModelCatalog.from_settings(settings)
        app.state.catalog = catalog
    return catalog


def _get_manager(app: FastAPI) -> GameManager:
    """Вернуть планировщик фоновых партий, построив его лениво при первом обращении.

    Без явного ``game_manager`` строит дефолтный ``GameManager`` (реальные игроки,
    ``games_root`` из ``output.games_dir``). Кэшируется в ``app.state.game_manager``.
    """
    manager = getattr(app.state, "game_manager", None)
    if manager is None:
        settings = app.state.settings or Settings.load()
        app.state.settings = settings
        manager = GameManager(games_root=settings.config.output.games_dir)
        app.state.game_manager = manager
    return manager


# Готовый экземпляр для ASGI-сервера: ``uvicorn arena.web.app:app``.
app = create_app()
