# LLM Chess Arena — образ веб-приложения (FastAPI + Uvicorn + собранный SPA).
# Сборка: docker build -t llm-chess-arena .
# Запуск:  docker compose up -d   (см. docker-compose.yml и deploy/DEPLOY.md)

# --- стадия 1: сборка фронтенда -------------------------------------------
# Vite кладёт бандл в src/arena/web/spa (см. frontend/vite.config.js), откуда его
# раздаёт FastAPI. В репозитории сборки нет (.gitignore), поэтому собираем здесь.
FROM node:22-slim AS frontend
WORKDIR /build

# Сначала манифесты — слой с npm ci переиспользуется, пока зависимости не менялись.
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci

COPY frontend ./frontend
RUN cd frontend && npm run build   # → /build/src/arena/web/spa

# --- стадия 2: приложение --------------------------------------------------
FROM python:3.11-slim

# Stockfish — для ★-подсказок и пост-анализа. Без него приложение работает,
# но ★-функции деградируют (D-008). Пакет ставит бинарник в /usr/games/, которого
# нет в PATH процесса uvicorn → симлинкуем в /usr/local/bin, чтобы движок находился
# по имени "stockfish" (как ждёт config.yaml).
RUN apt-get update \
    && apt-get install -y --no-install-recommends stockfish \
    && ln -sf /usr/games/stockfish /usr/local/bin/stockfish \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Зависимости и установка пакета. Ставим editable (-e), чтобы исходники остались
# в /app/src — тогда config.yaml ищется по DEFAULT_CONFIG_PATH (= /app/config.yaml).
COPY pyproject.toml README.md ./
COPY src ./src
COPY config.yaml ./config.yaml
RUN pip install --no-cache-dir -e . \
    && sed -i 's#tools/bin/stockfish.exe#stockfish#' config.yaml

# Собранный фронтенд из первой стадии (node в финальный образ не попадает).
COPY --from=frontend /build/src/arena/web/spa ./src/arena/web/spa

# Секреты НЕ копируются в образ — они приходят как переменные окружения
# (docker-compose env_file: .env). Артефакты партий — в volume ./games.
EXPOSE 8000
# --proxy-headers: доверять X-Forwarded-* от nginx (127.0.0.1) — чтобы приложение
# знало исходную схему (https) за reverse-proxy и не генерировало http://-ссылок.
CMD ["uvicorn", "arena.web.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
