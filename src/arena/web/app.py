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

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from arena.config import ModelCatalog, Settings

# Каталог пакета веб-слоя; статика и шаблоны лежат рядом с этим модулем.
_WEB_DIR = Path(__file__).resolve().parent
STATIC_DIR = _WEB_DIR / "static"
TEMPLATES_DIR = _WEB_DIR / "templates"

APP_TITLE = "LLM Chess Arena"
APP_VERSION = "0.1.0"


def create_app(settings: Settings | None = None) -> FastAPI:
    """Собрать экземпляр FastAPI-приложения арены (каркас Phase 6).

    ``settings`` (опц.) кладётся в ``app.state.settings``; роуты, которым нужен
    каталог моделей, строят его лениво (``_get_catalog``) — загрузкой ``Settings``
    из ``config.yaml``/``.env``, если он не передан. Шаблоны доступны как
    ``app.state.templates``. Монтируется статика ``/static`` и поднимается health.
    """
    app = FastAPI(title=APP_TITLE, version=APP_VERSION)
    app.state.settings = settings
    app.state.catalog = None  # строится лениво из settings (см. _get_catalog)

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

        Форма отправляется на ``POST /games`` (запуск партии — следующая задача).
        Модели без заданного API-ключа показываются, но помечены и недоступны для
        выбора (ключ не задан в ``.env``).
        """
        catalog = _get_catalog(request.app)
        models = [
            {
                "id": model.id,
                "display_name": model.display_name,
                "provider": model.provider,
                "has_key": catalog.has_key(model.id),
            }
            for model in catalog.models
        ]
        return templates.TemplateResponse(
            request,
            "new_game.html",
            {"title": f"{APP_TITLE} — новая партия", "models": models},
        )

    return app


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


# Готовый экземпляр для ASGI-сервера: ``uvicorn arena.web.app:app``.
app = create_app()
