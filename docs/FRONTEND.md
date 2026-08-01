# FRONTEND — карта фронтенда и контракт бэкенда

Фронтенд — **SPA на Vite + React** (каталог `frontend/`), который общается с
FastAPI по JSON-API `/api/*` и WebSocket. Сервер собственной вёрстки не имеет:
SSR-шаблоны Jinja удалены вместе с переходом на SPA.

Этот документ — точка входа, чтобы дорабатывать фронт или менять его снова:
как он устроен, что отдаёт бэкенд, как запускать и что нельзя потерять.

---

## 1. Архитектура

```
frontend/                     исходники SPA (в git)
  index.html                  точка входа Vite
  vite.config.js              сборка + dev-прокси на uvicorn
  src/
    main.jsx                  тема → рендер
    App.jsx                   оболочка: Header, экран по маршруту, Footer
    i18n/messages.js          словари RU/EN
    lib/                      чистые модули (всё, что под тестами)
    components/               Board, MoveList, ModelChip, States, Link…
    screens/                  Home, Archive, NewGame, Game(Live/Report), Tournaments…
src/arena/web/spa/            сборка (vite build) — НЕ в git, раздаётся FastAPI
```

- **Сборка кладётся внутрь питон-пакета** (`build.outDir = ../src/arena/web/spa`):
  так FastAPI находит её относительно `__file__`, и она едет в Docker-образ.
- **Раздача**: `GET /assets/*` — файлы сборки, любой другой путь отдаёт
  `index.html` (history-fallback), поэтому deep links (`/games/{id}`,
  `/tournaments/t1`) открываются напрямую и переживают перезагрузку.
  Путь под `/api/`, которого нет, даёт 404, а не страницу приложения.
- **Без сборки** сервер поднимается и отвечает 503 со страницей-инструкцией;
  JSON-API и WebSocket при этом работают.
- **Доска рисуется на клиенте** из FEN (`lib/fen.js` + `components/Board.jsx`),
  фигуры — юникодные глифы. Серверный `svg` в кадрах WS остался в протоколе, но
  фронт его не использует: он не знает про тему и палитру дизайна.
- **Шахматной логики на фронте нет**: позиции берутся из `fen_before`/`fen_after`
  записи и из кадров WS — считает всегда бэкенд (python-chess).
- **Язык интерфейса** — RU или EN целиком (`lib/i18n.js`), выбор в localStorage;
  он же уезжает на бэкенд при старте партии как язык рассуждений моделей.
- **Тема** — светлая/тёмная (`data-theme` на `<html>`), по умолчанию системная.

### Чистые модули (`frontend/src/lib`)
| Модуль | Ответственность |
|--------|-----------------|
| `router.js` | путь → экран и обратно; пути совпадают с адресами бэкенда |
| `navigation.js` | History API, хук маршрута, сохранение `?token=` |
| `api.js` | клиент `/api/*`, `ApiError`, токен в запросах, разбор `detail` |
| `i18n.js` | `t()` с интерполяцией и `Intl.PluralRules`, выбор языка |
| `theme.js` | разрешение и хранение темы |
| `fen.js` | разбор FEN, координаты, UCI, пары ходов |
| `live.js` | свёртка кадров WS в состояние живого экрана |
| `report.js` | кадры плеера, глифы/классы оценок, формат оценки и точности |
| `format.js`, `models.js`, `newGame.js`, `tournament.js` | форматирование и правила форм |

Правило: **тексты не «зашиты» в данные** — модули возвращают ключи словаря,
фразу подставляет `t()` в компоненте. Иначе интерфейс перестанет быть
строго одноязычным.

---

## 2. HTTP-контракт бэкенда

| Метод | Путь | Вход | Ответ |
|-------|------|------|-------|
| GET | `/health` | — | `{status, service, version}`. Единственный путь без токена. |
| GET | `/api/models` | — | `[{id, display_name, provider, has_key}]` (ключи наружу не отдаются) |
| POST | `/api/games` | `{white, black, language?}` | `201 {id}` |
| GET | `/api/games` | — | `[{id, white, black, status, result, live, created_at}]` (идущие первыми) |
| GET | `/api/games/{id}` | — | `{id, live, status, error, record}` — `record` это `GameRecord` |
| GET | `/api/games/{id}/pgn` | — | PGN файлом (`attachment`) |
| GET | `/api/games/{id}/report` | — | самодостаточный HTML-отчёт файлом (D-013) |
| POST | `/api/tournaments` | `{models[], double?, language?}` | `201 {id}` |
| GET | `/api/tournaments` | — | `[{id, participants, double, status, played, total, live, created_at}]` |
| GET | `/api/tournaments/{id}` | — | `{id, live, status, error, double, created_at, participants, played, total, standings, schedule}` |
| WS | `/games/{id}/ws` | токен | стрим событий партии (§3) |
| GET | `/assets/*` | — | файлы сборки SPA |
| GET | `*` | — | `index.html` (history-fallback) |

`language` — код интерфейса (`ru`/`en`): на нём модели пишут `reasoning` и
`strategy`. Незнакомый код игнорируется, партия просто идёт без указания языка.

### Ошибки
Все ошибки `/api/*` — это `detail` объектом:

```json
{"detail": {"code": "error.modelNoKey", "params": {"id": "gpt-4o"}, "message": "…"}}
```

`code` фронт переводит на язык интерфейса, `params` подставляет в фразу,
`message` — техническая подробность нижних слоёв (показывается, только если код
фронту незнаком). Коды: `modelUnknown`, `modelNoKey`, `modelUnavailable`,
`startFailed`, `tournamentTooFewModels`, `gameNotFound`, `tournamentNotFound`.
Новый код на бэкенде → добавь перевод в оба словаря (`src/i18n/messages.js`).

---

## 3. WebSocket-протокол live-просмотра

- URL: `ws(s)://<host>/games/{game_id}/ws` (`wss` на HTTPS). Токен — `?token=…`
  или cookie `arena_access`.
- Сервер сначала **переигрывает** накопленные кадры (подключившийся позже видит
  партию с начала), затем дослеживает новые, затем шлёт `status` и закрывает сокет.
- Сообщение — JSON `{"type": <str>, "payload": <obj>}`.

| type | payload |
|------|---------|
| `game_start` | `fen`, `to_move`, `svg` |
| `turn_start` | `side`, `ply`, `fen`, `svg` |
| `move` | `side`, `ply`, `san`, `uci`, `fen`, `svg`, `reasoning` |
| `illegal_attempt` | `side`, `ply`, `attempt`, `raw`, `reason` |
| `hint` | `side`, `ply`, `best_move`, `eval_cp`, `mate_in`, `hints_remaining` |
| `game_over` | `fen`, `plies`, `result`, `termination`, `svg` |
| `status` | `status` (`running`/`finished`/`error`), `result`, `termination`, `error` |
| `error` | `message` — партия неизвестна |

Замечания:
- `ply` — полуход с 1; номер хода = `(ply+1)//2`, белые при нечётном.
- `svg` фронт игнорирует (доска своя), поле осталось для совместимости.
- Повтор кадра при переподключении не должен задваивать ленту — свёртка в
  `lib/live.js` дедуплицирует по `ply`.
- Незнакомый тип кадра фронт молча пропускает: бэкенд может быть новее.

---

## 4. Аутентификация — доступ «по ссылке»

Если задан `ARENA_ACCESS_TOKEN`, middleware пускает только запросы с верным
токеном: `?token=<T>` или cookie `arena_access` (ставится при первом заходе с
токеном, 30 дней). Без токена открыт только `/health` — ассеты закрыты вместе с
сайтом, к моменту их запроса cookie уже поставлена ответом с `index.html`.
WebSocket проверяется отдельно тем же токеном.

Фронт дополнительно прокидывает `?token=` из адресной строки в каждый запрос и
в адрес WS — в dev-режиме `index.html` отдаёт Vite, и cookie может не быть.

---

## 5. Данные (модели → JSON)

Источник истины по партии — `GameRecord` (`src/arena/models.py`), он же в
`game.json`. Что использует фронт:

- `GameRecord`: `id`, `created_at`, `players: {white,black: PlayerInfo}`, `result`
  (`"1-0"`/`"0-1"`/`"1/2-1/2"`/`"*"`), `termination`, `moves`, `analysis`,
  `settings`, `hints_used`.
- `PlayerInfo`: `model_id`, `provider`, `display_name`.
- `MoveRecord`: `ply`, `side`, `san`, `uci`, `fen_before`, `fen_after`,
  `reasoning`, `strategy`, `plan_status`, `hint_used`, `hint`, `engine_eval_cp`
  (POV белых), `classification` (`book`/`brilliant`/`good`/`interesting`/
  `normal`/`inaccuracy`/`mistake`/`blunder`).
- `AnalysisSummary`: `white`/`black: {accuracy, blunders, mistakes, inaccuracies}`,
  `key_moments`.
- `PlayerSettings`: помимо лимитов — `response_language` (язык рассуждений).
- Турнир: `TournamentRecord`, таблица — `StatsTable{models: [ModelStats], total_games}`.

Глифы и цвета классов продублированы на фронте (`lib/report.js`) и **должны
совпадать** с `arena.analysis.classify` — иначе разбор на сайте разойдётся с
offline-отчётом. Это покрыто тестом.

---

## 6. Как запускать и проверять

**Dev (два процесса):**
```bash
.venv\Scripts\python.exe -m uvicorn arena.web.app:app      # бэкенд :8000
cd frontend && npm install && npm run dev                   # фронт :5173
```
Открывать `http://localhost:5173` (именно `localhost`). Vite проксирует на
uvicorn `/api` и **только** WS `/games/{id}/ws` — страница `/games/{id}`
остаётся маршрутом SPA. Если на бэкенде задан `ARENA_ACCESS_TOKEN`,
заходить надо по `http://localhost:5173/?token=<токен в URL-кодировке>`.

**Как в проде (один процесс):**
```bash
cd frontend && npm run build          # → src/arena/web/spa
.venv\Scripts\python.exe -m uvicorn arena.web.app:app
```

**Тесты:**
```bash
.venv\Scripts\python.exe -m pytest    # бэкенд (в т.ч. раздача SPA и /api/*)
cd frontend && npm test               # vitest: чистые модули фронта
```

**Docker:** сборка двухстадийная — node собирает фронт, питон-образ его раздаёт
(см. `Dockerfile`, `deploy/DEPLOY.md`). После правок в `frontend/` нужен
`docker compose up -d --build`, а не `restart`.

---

## 7. Что нельзя потерять (паритет функций)

1. Навигация по разделам и deep links (любой адрес открывается напрямую).
2. Выбор моделей и старт партии; модель без ключа видна, но недоступна.
3. Live-просмотр по WebSocket: доска, лента ходов парами, мысли модели.
4. Разбор завершённой партии: плеер (◀/▶, слайдер, клик по ходу, клавиши ←/→),
   оценки и классы ходов, «Мысли модели»/«План», подсказки движка, точность и
   счётчики ошибок по сторонам.
5. Скачивание PGN и самодостаточного HTML-отчёта.
6. Турниры: создание (≥2 модели, два круга), список, таблица + расписание со
   ссылками на партии, живой прогресс.
7. Доступ «по ссылке» (токен) — включая WebSocket.
8. Строго одноязычный интерфейс RU/EN и обе темы на каждом экране.

---

## 8. Чего пока нет (из `DESIGN_BRIEF.md`)

Вне сделанного захода — требуют новой инфраструктуры на бэкенде:
аккаунты и «мои партии», пауза/продолжение партии, режимы think/flash у моделей,
рейтинг Elo. Дизайн-референс этих экранов лежит в `docs/design/`.
