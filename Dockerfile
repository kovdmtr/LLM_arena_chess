# LLM Chess Arena — образ веб-приложения (FastAPI + Uvicorn).
# Сборка: docker build -t llm-chess-arena .
# Запуск:  docker compose up -d   (см. docker-compose.yml и deploy/DEPLOY.md)
FROM python:3.11-slim

# Stockfish — для ★-подсказок и пост-анализа. Без него приложение работает,
# но ★-функции деградируют (D-008). Из PATH движок берётся по имени "stockfish".
RUN apt-get update \
    && apt-get install -y --no-install-recommends stockfish \
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
CMD ["uvicorn", "arena.web.app:app", "--host", "0.0.0.0", "--port", "8000"]
