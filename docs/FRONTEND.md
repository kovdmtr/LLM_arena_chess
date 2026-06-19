# FRONTEND — карта фронтенда и гайд по полному переписыванию

Этот документ — точка входа, чтобы **в новой сессии переписать фронтенд с нуля**
(хоть сменить вёрстку/CSS, хоть перейти на SPA — React/Vue/Svelte), не сломав
бэкенд. Здесь: как устроен текущий фронт, полный контракт бэкенда (HTTP-роуты,
WebSocket-протокол, формы, данные), аутентификация, ограничения и пошаговый план
переделки с паритетом функций.

> Бэкенд трогать НЕ обязательно: весь фронт можно заменить, общаясь по тем же
> роутам. Если хочется SPA — см. раздел «Вариант B» и «Предлагаемый JSON-API».

---

## 1. Текущая архитектура фронтенда

- **Server-rendered (SSR) на Jinja2.** FastAPI (`src/arena/web/app.py`) отдаёт
  готовый HTML из шаблонов `src/arena/web/templates/`. Никакого build-step,
  node_modules, бандлера — чистый HTML + немного inline-JS.
- **Один CSS-файл** `src/arena/web/static/app.css`, подключается в `base.html`.
- **Доски рендерятся на сервере** как inline-SVG (`arena.report.render_board_svg` /
  `render_move_svg`), не на клиенте. На фронте шахматной логики нет.
- **Отчёт партии — самодостаточный HTML-документ** (`arena.report.render_report_html`,
  шаблон `report.html.j2`): встроенные SVG-доски, интерактивный плеер на vanilla-JS,
  встроенный PGN + кнопка «Скачать PGN». Этот документ НЕ расширяет `base.html` —
  он автономен (D-013: открывается даже как сохранённый offline-файл).
- **Live-просмотр партии** — WebSocket + inline-JS в `game_live.html`.
- **Язык интерфейса — русский.**

### Файлы (что за что отвечает)
| Файл | Назначение |
|------|-----------|
| `src/arena/web/app.py` | все роуты, middleware доступа, lazy-сборка менеджеров |
| `src/arena/web/templates/base.html` | каркас: `<head>`, шапка-логотип (ссылка на `/`), блоки `head`/`content` |
| `.../templates/index.html` | стартовая: кнопки Партия/Архив/Турнир/Турниры |
| `.../templates/new_game.html` | форма выбора белых/чёрных (2×`<select>`) |
| `.../templates/games.html` | список партий |
| `.../templates/game_live.html` | live-просмотр (WS), по концу — авто-reload в отчёт |
| `.../templates/new_tournament.html` | форма создания турнира (чекбоксы моделей + double) |
| `.../templates/tournaments.html` | список турниров |
| `.../templates/tournament_detail.html` | страница турнира: таблица + расписание (авто-refresh пока идёт) |
| `src/arena/web/static/app.css` | весь CSS интерфейса (кроме отчёта — у него свой inline-CSS) |
| `src/arena/report/templates/report.html.j2` | self-contained отчёт партии (своя вёрстка/CSS/JS) |
| `src/arena/web/live.py` | сервер WebSocket-стрима событий партии |

---

## 2. Полный справочник HTTP-роутов

Базовый префикс — корень сайта. Все роуты, кроме `/health` и `/static/*`, закрыты
токеном доступа, если включён (см. §4).

| Метод | Путь | Вход | Ответ |
|-------|------|------|-------|
| GET | `/health` | — | JSON `{status, service, version}`. Не закрыт токеном (для мониторинга). |
| GET | `/` | — | HTML: `index.html` (главное меню). |
| GET | `/games/new` | — | HTML: `new_game.html` (каталог моделей формой). |
| POST | `/games` | form: `white=<model_id>`, `black=<model_id>` | 303 redirect → `/games/{id}`; при ошибке (нет ключа/неизвестная модель/`ProviderError`) — 400 + перерисованная форма. |
| WS | `/games/{game_id}/ws` | токен через `?token=` или cookie | стрим событий партии (см. §3). |
| GET | `/games` | — | HTML: `games.html` (список: память + диск). |
| GET | `/games/{game_id}` | — | **идущая** → `game_live.html`; **завершённая** → **самодостаточный отчёт** (полный HTML-документ); 404 если нет. |
| GET | `/tournaments/new` | — | HTML: `new_tournament.html`. |
| POST | `/tournaments` | form: `models=<id>` (повторяется ≥2), `double=true` (опц.) | 303 → `/tournaments/{id}`; при ошибке — 400 + форма. |
| GET | `/tournaments` | — | HTML: `tournaments.html` (список). |
| GET | `/tournaments/{tournament_id}` | — | HTML: `tournament_detail.html` (идущий — частичная таблица + авто-refresh; завершённый — итог). 404 если нет. |
| — | `/static/*` | — | статика (CSS). Не закрыта токеном. |

**Формы** — `application/x-www-form-urlencoded` (обычный `<form method=post>`).
`POST /games` и `POST /tournaments` отвечают **редиректом** (303) — это SSR-стиль.
Для SPA удобнее, чтобы они возвращали JSON `{id}` (см. §7).

**Каталог моделей** (для форм выбора): сейчас доступен только как отрисованный HTML.
Каждая модель: `id`, `display_name`, `provider`, `has_key` (есть ли ключ — без ключа
недоступна). Для SPA нужен JSON-эндпоинт (см. §7).

---

## 3. WebSocket-протокол live-просмотра

- URL: `ws(s)://<host>/games/{game_id}/ws` (`wss` на HTTPS). Токен — `?token=…` в URL
  или cookie `arena_access` (см. §4).
- Сервер сначала **переигрывает** уже накопленные события (подключившийся позже
  видит партию с начала), затем **дослеживает** новые до конца, затем шлёт `status`
  и закрывает сокет.
- Каждое сообщение — JSON `{"type": <str>, "payload": <obj>}`.

### Типы кадров и поля payload
| type | payload |
|------|---------|
| `game_start` | `fen`, `to_move`, `svg` (inline-SVG доски) |
| `turn_start` | `side`, `ply`, `fen`, `svg` |
| `move` | `side`, `ply`, `san`, `uci`, `fen`, `svg`, `reasoning` (рассуждение модели) |
| `illegal_attempt` | `side`, `ply`, `attempt` (номер попытки), `raw`, `reason` |
| `hint` | `side`, `ply`, `best_move`, `eval_cp`, `mate_in`, `hints_remaining` |
| `game_over` | `fen`, `plies`, `result`, `termination`, `svg` |
| `status` | `status` (`running`/`finished`/`error`), `result`, `termination`, `error` — финальный кадр |
| `error` | `message` — если партия неизвестна |

Замечания для фронта:
- `svg` добавляется к любому кадру, где есть `fen` (готовая доска с подсветкой
  последнего хода по `uci`). Если делаешь свою доску из `fen` — `svg` можно игнорить.
- `ply` — номер полухода с 1; номер хода = `(ply+1)//2`, белые при нечётном `ply`.
- Текущий клиент по кадру `status` делает `location.reload()` → тот же URL
  `/games/{id}` отдаёт уже отчёт с анализом. SPA может вместо reload подгрузить отчёт/данные.

---

## 4. Аутентификация — доступ «по ссылке»

Если на сервере задан `ARENA_ACCESS_TOKEN` (env/`.env`), middleware (`web/app.py`,
`_access_gate`) пускает только запросы с верным токеном:
- источник токена: query `?token=<T>` **или** cookie `arena_access`;
- первый заход с верным `?token` ставит httponly-cookie `arena_access` (30 дней),
  дальше навигация без токена в URL;
- открыты без токена: `/health` и `/static/*`;
- WebSocket тоже под токеном (через `?token` или ту же cookie);
- сверка constant-time; неверный/нет токена → 403 (HTML-страница).

**Для любого нового фронта:** либо заходить по ссылке `…/?token=<T>` (cookie
поставится сама), либо слать `?token=` на каждый запрос/WS. SPA: достаточно один раз
открыть `/?token=…` — дальше fetch/WS пойдут с cookie (same-origin).

---

## 5. Данные (модели → JSON)

Источник истины по партии — `GameRecord` (Pydantic, `src/arena/models.py`),
сериализуется в `game.json`. Ключевые поля (то, что нужно фронту):

- `GameRecord`: `id`, `created_at`, `players: {white,black: PlayerInfo}`, `result`
  (`"1-0"`/`"0-1"`/`"1/2-1/2"`/`"*"`), `termination`, `moves: [MoveRecord]`,
  `analysis: AnalysisSummary | null`, `settings`, `hints_used`.
- `PlayerInfo`: `model_id`, `provider`, `display_name` (без ключей).
- `MoveRecord`: `ply`, `side`, `san`, `uci`, `fen_before`, `fen_after`, `reasoning`,
  `strategy`, `plan_status` (`start`/`continue`/`adapt`/`abandon` — фича «стратегия»),
  `hint_used`, `hint`, `engine_eval_cp` (оценка POV белых), `classification`
  (`book`/`brilliant`/`good`/`inaccuracy`/`mistake`/`blunder`).
- `AnalysisSummary`: `white`/`black: PlayerAnalysis{accuracy, blunders, mistakes,
  inaccuracies}`, `key_moments: [{ply, classification, comment}]`.
- Турнир: `TournamentRecord{id, created_at, participants:[PlayerInfo], double,
  games:[TournamentGame{round_number, white, black, game_id, result}]}`.
- Таблица: `StatsTable{models:[ModelStats{model_id, display_name, games, wins, draws,
  losses, points, score_pct, avg_accuracy, blunders, mistakes, inaccuracies,
  hints_used}], total_games}` (слой `arena.stats`).

Любую из этих структур легко отдать как JSON (`.model_dump()`), что и нужно для SPA.

---

## 6. Что нельзя терять при переписывании (паритет функций)

1. Стартовая страница / навигация (везде должна быть ссылка домой).
2. Выбор моделей и старт партии (модели без ключа — недоступны).
3. **Live-просмотр** партии по WebSocket (доска + лента ходов + рассуждения).
4. **Отчёт завершённой партии**: интерактивный плеер (перемотка ходов, доски),
   ★-анализ (точность, бейджи классификации, оценки, ключевые моменты), рассуждения
   и план (`strategy`/`plan_status`) под ходами, подсказки движка.
5. **Кнопка «Скачать PGN»** (PGN встроен в отчёт; см. `report.html.j2`).
6. Турниры: создание (≥2 модели, double), список, страница со standings-таблицей и
   расписанием (ссылки на партии), живой прогресс.
7. Доступ «по ссылке» (токен) должен продолжать работать.

---

## 7. Вариант B: SPA (React/Vue/Svelte) — что добавить в бэкенд

SSR-роуты возвращают HTML и редиректы. Для SPA нужен **JSON-API**. Предлагаемые
эндпоинты (тонкие обёртки над уже существующими менеджерами/слоями — логика готова):

| Нужный JSON-эндпоинт | Откуда брать данные |
|----------------------|---------------------|
| `GET /api/models` → `[{id,display_name,provider,has_key}]` | `ModelCatalog` (`catalog.models`, `has_key`) |
| `POST /api/games {white,black}` → `{id}` | `GameManager.start(resolved)` (вернуть id вместо redirect) |
| `GET /api/games` → `[GameInfo]` | `GameManager.list_games()` |
| `GET /api/games/{id}` → `GameRecord` (JSON) | `GameManager.load_record(id).model_dump()` |
| WS `/games/{id}/ws` | уже есть — не меняется |
| `POST /api/tournaments {models[],double}` → `{id}` | `TournamentManager.start(participants,double)` |
| `GET /api/tournaments` → `[TournamentInfo]` | `TournamentManager.list_tournaments()` |
| `GET /api/tournaments/{id}` → `{record, standings, live}` | `load_record` + `load_standings` |

Тогда фронт сам рисует:
- **доску** — либо из `fen` клиентской либой (react-chessboard / chessground /
  chessboard.js), либо запрашивать готовый SVG с сервера (`render_board_svg`);
- **отчёт/плеер** — из `GameRecord` (массив `moves` с `fen_after`/eval/classification);
- **таблицы/списки** — из JSON выше.

Существующие SSR-роуты можно оставить (для совместимости) или удалить. Менеджеры
(`GameManager`, `TournamentManager`) и слои (`stats`, `report`, `core`) переиспользуются
как есть — переписывается только тонкий веб-слой `web/`.

> Раздачу самого SPA-бандла можно повесить на `StaticFiles` (mount каталога билда)
> или отдельный nginx-location; API — на FastAPI. Деплой (Docker+nginx) уже есть —
> добавить proxy/route на статику фронта.

---

## 8. Вариант A: остаться на SSR (просто новая вёрстка/CSS)

Самый дешёвый путь — поменять только представление:
1. Переписать `src/arena/web/templates/*.html` (вёрстка) и `static/app.css` (стили).
2. Отдельно — `src/arena/report/templates/report.html.j2` (отчёт; помни D-013:
   самодостаточный, без внешних ссылок/сети; доски и PGN встроены).
3. JS в шаблонах сейчас inline (live `game_live.html`, плеер в `report.html.j2`).
   Контракт WS и DOM-хуки см. §3. Можно вынести в `static/*.js` и подключать.
4. Роуты/контекст шаблонов в `app.py` менять обычно не нужно — они передают готовые
   данные (списки моделей, `tournaments`, `standings`, `schedule` и т.д.).

Подводные камни:
- **Starlette `TemplateResponse`** — НОВАЯ сигнатура `TemplateResponse(request, name,
  context)` (старый порядок падает). См. `app.py`.
- Отчёт партии **не** наследует `base.html` (он автономен) — стили туда отдельно.
- Текст и эскейпинг: пользовательский текст (рассуждения, имена) эскейпится Jinja —
  не отключать автоэскейп.

---

## 9. Как запускать/проверять фронт локально

- Запуск: `\.venv\Scripts\python.exe -m uvicorn arena.web.app:app` → http://127.0.0.1:8000
- Тесты веб-слоя: `\.venv\Scripts\python.exe -m pytest tests/test_web_*.py`
  (smoke роутов, формы, список/детали, доступ по токену, live через «ворота»).
- Фейковые игроки в тестах (`player_factory`) позволяют гонять партии/турниры без
  сети — переиспользуй этот шов при тестировании нового фронта.

---

## 10. Сводка решений для редизайна

- **Минимум усилий** → Вариант A (шаблоны+CSS), бэкенд не трогаем.
- **Современный SPA** → Вариант B: добавить `/api/*` JSON-обёртки (§7), WS оставить,
  доску рисовать клиентом из `fen`. Менеджеры/слои переиспользуются.
- В обоих случаях сохранить паритет функций (§6) и работу токена доступа (§4).
