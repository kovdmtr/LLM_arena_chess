"""★ FastAPI-приложение арены (D-002): JSON-API, WebSocket и раздача SPA.

``create_app`` собирает изолированный экземпляр (удобно для тестов и инъекции
``Settings``): «ворота» доступа по токену, health, роутер ``/api/*``, WebSocket
живого просмотра и раздачу собранного SPA-фронтенда.

Фронтенд — это сборка Vite (``frontend/`` → ``src/arena/web/spa``): статика из
``/assets`` и history-fallback, отдающий ``index.html`` на любой путь SPA
(``/games/{id}``, ``/tournaments`` и т.д.). Собственной вёрстки на сервере больше
нет — SSR-шаблоны удалены вместе с переходом на SPA; самодостаточный HTML-отчёт
остался и отдаётся как файл на скачивание (``GET /api/games/{id}/report``).

Для ``uvicorn`` в конце модуля собран экземпляр ``app``
(``uvicorn arena.web.app:app``).
"""

from __future__ import annotations

import hmac
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from arena.config import ModelCatalog, Settings
from arena.engine import build_engine
from arena.obs import register_secrets
from arena.web.api import build_api_router
from arena.web.games import GameManager
from arena.web.live import stream_session
from arena.web.tournaments import TournamentManager

# Каталог пакета веб-слоя; сборка SPA лежит рядом с этим модулем (vite build).
_WEB_DIR = Path(__file__).resolve().parent
SPA_DIR = _WEB_DIR / "spa"

APP_TITLE = "LLM Chess Arena"
APP_VERSION = "0.1.0"

# Доступ «по ссылке»: имя cookie с токеном и страница отказа.
_ACCESS_COOKIE = "arena_access"
_ACCESS_TOKEN_TTL = 60 * 60 * 24 * 30  # 30 дней
_UNSET = object()
_ACCESS_DENIED_HTML = (
    "<!DOCTYPE html><html lang='ru'><head><meta charset='utf-8'>"
    "<title>Доступ закрыт</title></head><body style='font-family:system-ui;"
    "max-width:32rem;margin:4rem auto;padding:0 1rem;color:#1c1917'>"
    "<h1>403 — доступ только по ссылке</h1>"
    "<p>Эта арена открыта по приватной ссылке с токеном. "
    "Откройте её по выданной ссылке вида <code>…/?token=…</code>.</p>"
    "</body></html>"
)

# Фронтенд не собран: сервер работает (API/WS живы), но показывать нечего.
_SPA_MISSING_HTML = (
    "<!DOCTYPE html><html lang='ru'><head><meta charset='utf-8'>"
    "<title>Фронтенд не собран</title></head><body style='font-family:system-ui;"
    "max-width:32rem;margin:4rem auto;padding:0 1rem;color:#1c1917'>"
    "<h1>Фронтенд не собран</h1>"
    "<p>Соберите SPA: <code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code>"
    " — сборка кладётся в <code>src/arena/web/spa</code>. "
    "JSON-API (<code>/api/*</code>) при этом работает.</p>"
    "</body></html>"
)


def create_app(
    settings: Settings | None = None,
    *,
    game_manager: GameManager | None = None,
    tournament_manager: TournamentManager | None = None,
    access_token: str | None = None,
    spa_dir: Path | str | None = None,
) -> FastAPI:
    """Собрать экземпляр FastAPI-приложения арены.

    ``settings`` (опц.) кладётся в ``app.state.settings``; роуты, которым нужен
    каталог моделей, строят его лениво (``_get_catalog``) — загрузкой ``Settings``
    из ``config.yaml``/``.env``, если он не передан. ``game_manager`` и
    ``tournament_manager`` (опц.) переопределяют планировщики фоновых партий и
    турниров (шов для тестов с фейковыми игроками). ``spa_dir`` (опц.) —
    каталог сборки фронтенда; по умолчанию ``src/arena/web/spa``.
    """
    app = FastAPI(title=APP_TITLE, version=APP_VERSION)
    app.state.settings = settings
    app.state.catalog = None  # строится лениво из settings (см. _get_catalog)
    app.state.game_manager = game_manager  # либо лениво в _get_manager
    app.state.tournament_manager = tournament_manager  # либо лениво в _get_tournament_manager
    # Токен доступа «по ссылке»: явный (тесты) или из секретов/окружения (лениво).
    app.state.access_token_override = access_token
    app.state._access_token = _UNSET
    app.state.spa_dir = Path(spa_dir) if spa_dir is not None else SPA_DIR

    # Ассеты сборки. ``check_dir=False`` — сервер должен подниматься и без
    # собранного фронта (API и WS от него не зависят).
    app.mount(
        "/assets",
        StaticFiles(directory=str(app.state.spa_dir / "assets"), check_dir=False),
        name="assets",
    )

    # JSON-API для SPA-фронтенда (см. web/api.py и docs/FRONTEND.md §7). Акцессоры
    # передаём функциями — роутер не знает про этот модуль, цикла импортов нет.
    app.include_router(
        build_api_router(
            get_catalog=_get_catalog,
            get_manager=_get_manager,
            get_tournament_manager=_get_tournament_manager,
        )
    )

    @app.middleware("http")
    async def _access_gate(request: Request, call_next):
        """Пускать только запросы с верным токеном, если доступ «по ссылке» включён.

        Токен берётся из ``?token=…`` или cookie ``arena_access``. Открыт без
        токена только health (для мониторинга): ассеты — часть закрытого сайта,
        а cookie к моменту их запроса уже поставлена ответом с ``index.html``.
        Первый заход с верным ``?token`` ставит cookie, дальше навигация работает
        без него. Токен не задан → сайт открыт.
        """
        token = _resolve_access_token(request.app)
        if not token:
            return await call_next(request)
        if request.url.path == "/health":
            return await call_next(request)
        query_token = request.query_params.get("token")
        provided = query_token or request.cookies.get(_ACCESS_COOKIE)
        if not (provided and hmac.compare_digest(provided, token)):
            return HTMLResponse(_ACCESS_DENIED_HTML, status_code=403)
        response = await call_next(request)
        if query_token and hmac.compare_digest(query_token, token):
            response.set_cookie(
                _ACCESS_COOKIE, token, max_age=_ACCESS_TOKEN_TTL,
                httponly=True, samesite="lax",
            )
        return response

    @app.get("/health")
    def health() -> dict[str, str]:
        """Проверка живости сервиса (для мониторинга/тестов)."""
        return {"status": "ok", "service": APP_TITLE, "version": APP_VERSION}

    @app.websocket("/games/{game_id}/ws")
    async def game_ws(websocket: WebSocket, game_id: str) -> None:
        """Live-просмотр партии: replay накопленных событий + стрим новых."""
        token = _resolve_access_token(websocket.app)
        if token:
            provided = websocket.query_params.get("token") or websocket.cookies.get(
                _ACCESS_COOKIE
            )
            if not (provided and hmac.compare_digest(provided, token)):
                await websocket.close(code=1008)  # policy violation
                return
        session = _get_manager(websocket.app).get(game_id)
        await stream_session(websocket, session)

    @app.get("/{spa_path:path}", response_class=HTMLResponse)
    def spa_fallback(request: Request, spa_path: str) -> HTMLResponse:
        """History-fallback: любой путь SPA отдаёт ``index.html``.

        Роут объявлен последним, поэтому health, ``/api/*``, ассеты и WebSocket
        разбираются раньше. Неизвестный путь под ``/api/`` — это ошибка клиента,
        а не маршрут фронта, поэтому там честный 404, а не страница приложения.
        """
        if spa_path.startswith("api/"):
            raise HTTPException(status_code=404, detail={"code": "error.notFound"})
        index = Path(request.app.state.spa_dir) / "index.html"
        if not index.is_file():
            return HTMLResponse(_SPA_MISSING_HTML, status_code=503)
        return HTMLResponse(index.read_text(encoding="utf-8"))

    return app


def _resolve_access_token(app: FastAPI) -> str | None:
    """Эффективный токен доступа «по ссылке» (кэшируется на ``app.state``).

    Источник по приоритету: явный ``access_token`` из ``create_app`` → секрет
    ``arena_access_token`` из ``.env`` → переменная окружения ``ARENA_ACCESS_TOKEN``.
    ``None``/пусто — доступ открыт (gate выключен). Пустая строка трактуется как
    «не задан».
    """
    cached = getattr(app.state, "_access_token", _UNSET)
    if cached is _UNSET:
        override = getattr(app.state, "access_token_override", None)
        if override is not None:
            cached = override or None
        else:
            # ``Secrets`` (pydantic-settings) сам читает и ``.env``, и переменные
            # окружения (``ARENA_ACCESS_TOKEN`` → поле ``arena_access_token``).
            try:
                cached = _ensure_settings(app).secrets.arena_access_token or None
            except Exception:  # noqa: BLE001 — нет настроек/конфига → доступ открыт
                cached = None
        app.state._access_token = cached
    return cached


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
            player_settings=settings.config.arena.to_player_settings(),
        )
        app.state.game_manager = manager
    return manager


def _get_tournament_manager(app: FastAPI) -> TournamentManager:
    """Вернуть планировщик фоновых турниров, построив его лениво при первом обращении.

    Без явного ``tournament_manager`` строит дефолтный (реальные игроки через каталог,
    ★-движок/анализ из конфига — как у ``GameManager``). Кэшируется в app.state.
    """
    manager = getattr(app.state, "tournament_manager", None)
    if manager is None:
        settings = _ensure_settings(app)
        engine_cfg = settings.config.engine
        manager = TournamentManager(
            catalog=_get_catalog(app),
            games_root=settings.config.output.games_dir,
            engine_factory=lambda: build_engine(engine_cfg, depth=engine_cfg.hint_depth),
            analysis_config=settings.config.analysis,
            analysis_depth=engine_cfg.analysis_depth,
            player_settings=settings.config.arena.to_player_settings(),
        )
        app.state.tournament_manager = manager
    return manager


# Готовый экземпляр для ASGI-сервера: ``uvicorn arena.web.app:app``.
app = create_app()
