# Деплой LLM Chess Arena на сервер (Docker)

Веб-приложение упаковано в один контейнер (FastAPI + Uvicorn + Stockfish).
Ниже — деплой на чистый Ubuntu/Debian-сервер. Все команды выполняются **на сервере**.

> ⚠️ **Безопасность — прочитай до запуска.**
> 1. **Смени root-пароль** сразу (`passwd`) и настрой SSH-ключи; пароли в чатах/почте — это утечка.
> 2. **У приложения НЕТ авторизации.** Любой, кто откроет URL, сможет запускать партии,
>    а это **тратит твои деньги на API** (OpenAI/Anthropic/Gemini). Поэтому порт по
>    умолчанию открыт только на `127.0.0.1`. Наружу выставляй ТОЛЬКО за nginx с
>    basic-auth/HTTPS, за VPN или через SSH-туннель (см. ниже).

## 1. Поставить Docker
```bash
curl -fsSL https://get.docker.com | sh
```

## 2. Получить код
Репозиторий приватный — варианты:
```bash
# вариант A: git clone по токену (НЕ сохраняй токен в URL надолго; лучше credential manager)
git clone https://github.com/kovdmtr/LLM_arena_chess.git
cd LLM_arena_chess

# вариант B: без git — скопировать с локальной машины
#   scp -r C:\Users\dmitr\Chess_LLM_Claude root@SERVER:/opt/llm-arena
```

## 3. Прописать ключи провайдеров
```bash
cp .env.example .env
nano .env        # вписать OPENAI_API_KEY / ANTHROPIC_API_KEY / GOOGLE_API_KEY
```
`.env` в образ не попадает и в git не коммитится — ключи живут только на сервере.

## 4. Собрать и запустить
Сборка и запуск — двумя шагами, а не одной командой: так неудачная сборка
вообще не доходит до работающего контейнера.
```bash
docker compose build            # 1) собрать образ (первый раз — дольше: npm-зависимости)
docker compose up -d            # 2) поднять, только если сборка прошла
docker compose logs -f          # убедиться, что поднялось (Ctrl+C для выхода из логов)
```
Сборка образа двухстадийная: сначала node собирает SPA-фронтенд
(`frontend/` → `src/arena/web/spa`), затем он копируется в питон-образ, который и
раздаёт его вместе с API. Node в финальный образ не попадает, ставить его на
сервер не нужно. Стадия сборки проверяет, что бандл получился (`index.html` +
`assets/`), поэтому «пустой» образ до запуска не доедет.
Проверка здоровья (локально на сервере):
```bash
curl http://127.0.0.1:8000/health   # -> {"status":"ok",...}
```

## 5. Доступ «по ссылке» (рекомендуется как минимум это)
Самый простой способ закрыть сайт: задать секретный токен — тогда внутрь пускают
только по ссылке с ним, остальные видят 403. В `.env`:
```bash
# сгенерировать секрет
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
# вписать в .env
echo "ARENA_ACCESS_TOKEN=ВСТАВЬ_СЕКРЕТ" >> .env
docker compose up -d            # перечитать .env
```
Делись ссылкой вида `http://адрес/?token=ВСТАВЬ_СЕКРЕТ` — у того, кто открыл, токен
сохранится в cookie. Это не «военная» защита (токен виден в URL/истории), но отсекает
случайных посетителей. Для надёжности комбинируй с nginx basic-auth/HTTPS ниже.

## 6. Открыть наружу безопасно (выбери один способ)

### а) SSH-туннель — проще всего, ничего не публикуем
На своей машине:
```bash
ssh -L 8000:127.0.0.1:8000 root@167.233.41.85
```
Затем в браузере: <http://localhost:8000>

### б) nginx + Basic-Auth (+ HTTPS) — для постоянного доступа
```bash
apt-get install -y nginx apache2-utils
htpasswd -c /etc/nginx/.htpasswd admin        # задать логин/пароль
```
`/etc/nginx/sites-available/arena`:
```nginx
server {
    listen 80;
    server_name your.domain.com;          # или IP
    location / {
        auth_basic "LLM Chess Arena";
        auth_basic_user_file /etc/nginx/.htpasswd;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;  # чтобы приложение знало про HTTPS
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;     # WebSocket для live-просмотра
        proxy_set_header Connection "upgrade";
    }
}
```
```bash
ln -s /etc/nginx/sites-available/arena /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
# HTTPS: certbot --nginx -d your.domain.com  (нужен домен)
```
Дополнительно ограничь доступ файрволом на свой IP:
```bash
ufw allow OpenSSH && ufw allow 'Nginx Full' && ufw enable
```

## Обновление версии
```bash
git pull            # или заново scp
docker compose build            # упало — старый контейнер продолжает работать
docker compose up -d
```

## Полезное
- Логи: `docker compose logs -f`
- Перезапуск: `docker compose restart`
- Остановить: `docker compose down`
- Партии/турниры сохраняются в `./games` (volume) и переживают пересборку.
- Stockfish ставится в образ (apt) → ★-подсказки и анализ работают из коробки.
- Менять модели/лимиты — в `config.yaml` (затем `docker compose build && docker compose up -d`).
- Фронтенд собирается внутри образа, поэтому после правок в `frontend/` нужна
  пересборка (`docker compose build`), а не `restart`.
- Страница «Фронтенд не собран» (503) в норме не появляется: стадия сборки
  проверяет наличие бандла и падает, если его нет. Если всё же увидел её —
  образ старый: `docker compose build --no-cache && docker compose up -d`.
