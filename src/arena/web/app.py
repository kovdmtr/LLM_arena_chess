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
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

if TYPE_CHECKING:
    from arena.config import Settings

# Каталог пакета веб-слоя; статика и шаблоны лежат рядом с этим модулем.
_WEB_DIR = Path(__file__).resolve().parent
STATIC_DIR = _WEB_DIR / "static"
TEMPLATES_DIR = _WEB_DIR / "templates"

APP_TITLE = "LLM Chess Arena"
APP_VERSION = "0.1.0"


def create_app(settings: "Settings | None" = None) -> FastAPI:
    """Собрать экземпляр FastAPI-приложения арены (каркас Phase 6).

    ``settings`` (опц.) кладётся в ``app.state.settings`` для роутов, которым нужен
    конфиг/каталог моделей (добавляются следующими задачами). Шаблоны доступны как
    ``app.state.templates``. Монтируется статика ``/static`` и поднимается health.
    """
    app = FastAPI(title=APP_TITLE, version=APP_VERSION)
    app.state.settings = settings

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

    return app


# Готовый экземпляр для ASGI-сервера: ``uvicorn arena.web.app:app``.
app = create_app()
