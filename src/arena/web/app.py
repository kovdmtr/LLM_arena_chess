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

from fastapi import FastAPI, Form, HTTPException, Request, WebSocket, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from arena.config import ConfigError, ModelCatalog, Settings
from arena.engine import build_engine
from arena.obs import register_secrets
from arena.providers import ProviderError
from arena.report import render_report_html
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
            session = _get_manager(request.app).start(resolved)
        except (ConfigError, ProviderError) as exc:
            # Неизвестная модель/провайдер или отсутствие ключа (резолв), либо сбой
            # построения провайдера (старт) — показываем форму с понятной ошибкой.
            return _render_new_game(
                request, catalog, error=str(exc),
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        return RedirectResponse(
            f"/games/{session.id}", status_code=status.HTTP_303_SEE_OTHER
        )

    @app.websocket("/games/{game_id}/ws")
    async def game_ws(websocket: WebSocket, game_id: str) -> None:
        """Live-просмотр партии: replay накопленных событий + стрим новых."""
        session = _get_manager(websocket.app).get(game_id)
        await stream_session(websocket, session)

    @app.get("/games", response_class=HTMLResponse)
    def games_list(request: Request) -> HTMLResponse:
        """Список партий: идущие (из памяти) и завершённые (из памяти/с диска)."""
        games = _get_manager(request.app).list_games()
        return templates.TemplateResponse(
            request,
            "games.html",
            {"title": f"{APP_TITLE} — партии", "games": games},
        )

    @app.get("/games/{game_id}", response_class=HTMLResponse)
    def game_detail(request: Request, game_id: str) -> HTMLResponse:
        """Страница партии: живой просмотр для идущей, готовый отчёт для завершённой.

        Идущая партия (сессия в памяти не завершена) → страница live-просмотра,
        подключающаяся к ``WS /games/{id}/ws``. Завершённая (в памяти или на диске)
        → self-contained HTML-отчёт с интерактивным плеером (переиспользуется из
        слоя ``report``). Неизвестная партия → 404.
        """
        manager = _get_manager(request.app)
        session = manager.get(game_id)
        if session is not None and not session.done:
            return templates.TemplateResponse(
                request,
                "game_live.html",
                {
                    "title": f"{APP_TITLE} — партия {game_id}",
                    "game_id": game_id,
                    "white": session.players["white"].display_name,
                    "black": session.players["black"].display_name,
                },
            )
        record = manager.load_record(game_id)
        if record is None:
            raise HTTPException(status_code=404, detail="партия не найдена")
        return HTMLResponse(render_report_html(record))

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


def _ensure_settings(app: FastAPI) -> Settings:
    """Вернуть ``Settings`` приложения, загрузив их лениво при первом обращении.

    Помимо кэширования в ``app.state.settings`` регистрирует значения секретов
    (API-ключи провайдеров) в реестре маскирования логов (D-003) — чтобы ключ не
    утёк в вывод, даже если всплывёт в сообщении/трейсбеке.
    """
    settings = getattr(app.state, "settings", None)
    if settings is None:
        settings = Settings.load()
        app.state.settings = settings
    register_secrets(
        [
            settings.secrets.openai_api_key,
            settings.secrets.anthropic_api_key,
            settings.secrets.google_api_key,
        ]
    )
    return settings


def _get_catalog(app: FastAPI) -> ModelCatalog:
    """Вернуть каталог моделей приложения, построив его лениво при первом обращении.

    Использует ``app.state.settings`` (если передан в ``create_app``) или загружает
    ``Settings`` из ``config.yaml``/``.env``. Результат кэшируется в
    ``app.state.catalog`` — каталог строится один раз на приложение.
    """
    catalog = getattr(app.state, "catalog", None)
    if catalog is None:
        catalog = ModelCatalog.from_settings(_ensure_settings(app))
        app.state.catalog = catalog
    return catalog


def _get_manager(app: FastAPI) -> GameManager:
    """Вернуть планировщик фоновых партий, построив его лениво при первом обращении.

    Без явного ``game_manager`` строит дефолтный ``GameManager`` (реальные игроки,
    ``games_root`` из ``output.games_dir``). Кэшируется в ``app.state.game_manager``.
    """
    manager = getattr(app.state, "game_manager", None)
    if manager is None:
        settings = _ensure_settings(app)
        engine_cfg = settings.config.engine
        # ★ Движок подключается через единый путь (build_engine): на каждую партию —
        # открытый Stockfish или None (деградация без бинарника/при enabled=false).
        manager = GameManager(
            games_root=settings.config.output.games_dir,
            engine_factory=lambda: build_engine(engine_cfg, depth=engine_cfg.hint_depth),
            analysis_config=settings.config.analysis,
            analysis_depth=engine_cfg.analysis_depth,
        )
        app.state.game_manager = manager
    return manager


# Готовый экземпляр для ASGI-сервера: ``uvicorn arena.web.app:app``.
app = create_app()
