# LLM Chess Arena — образ веб-приложения (FastAPI + Uvicorn).
# Сборка: docker build -t llm-chess-arena .
# Запуск:  docker compose up -d   (см. docker-compose.yml и deploy/DEPLOY.md)
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

# Секреты НЕ копируются в образ — они приходят как переменные окружения
# (docker-compose env_file: .env). Артефакты партий — в volume ./games.
EXPOSE 8000
# --proxy-headers: доверять X-Forwarded-* от nginx (127.0.0.1) — чтобы приложение
# знало исходную схему (https) за reverse-proxy и не генерировало http://-ссылок.
CMD ["uvicorn", "arena.web.app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
