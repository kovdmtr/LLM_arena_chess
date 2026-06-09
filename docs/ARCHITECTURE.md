# ARCHITECTURE — LLM Chess Arena

## 1. Принципы

- **Слои с однонаправленными зависимостями.** Доменное ядро (`core`) не знает о
  провайдерах, вебе и движке.
- **`game.json` — единственный источник истины.** PGN и HTML — производные.
- **Провайдеры за единым интерфейсом** — добавить нового = реализовать `LLMProvider`.
- **Движок опционален** — система работает без Stockfish (★-фичи деградируют).
- **Чистые функции там, где можно** (парсинг, сборка PGN, классификация) — легко тестировать.

## 2. Слои и модули

```
config  →  providers  →  prompts  →  arena  →  storage  →  report
              ↓             ↑          ↓ ↑
            models  ←———  core  ←——  engine  ←  analysis
```

### `config/`
Загрузка настроек: `Settings` (pydantic-settings) читает `.env` (секреты) и
`config.yaml` (несекретное). Предоставляет каталог моделей (`ModelCatalog`) и
резолвит ключ провайдера по `api_key_env`. Валидирует наличие ключей для выбранных
моделей при старте (fail-fast).

### `models.py` (данные)
Pydantic-модели — общий язык между слоями:
`PlayerConfig`, `MoveRecord`, `MessageRecord`, `HintRecord`, `GameRecord`,
`AnalysisSummary`, `LLMResponse` (распарсенный ответ модели: `move`, `reasoning`,
`request_hint`, `resign`).

### `core/` (шахматный домен)
Обёртка над `python-chess`, без знания об LLM:
- `board.py` — состояние партии: `fen()`, `legal_moves_san()`, `push(move)`,
  `is_game_over()`, `outcome()` (мат/пат/ничьи), детект окончания и причины.
- `move_parsing.py` — извлечение хода из ответа модели: пробуем `parse_san`,
  затем `parse_uci`; нормализация в `(san, uci)`; возврат причины при неудаче.
- `pgn.py` — сборка `chess.pgn.Game` из `GameRecord`: теги, ходы, комментарии
  (рассуждения), NAG (классификация), экспорт строки PGN.

### `providers/` (LLM-абстракция)
- `base.py` — `LLMProvider` (интерфейс `complete(messages, params) -> text`) и
  фабрика по имени провайдера.
- `openai_provider.py`, `anthropic_provider.py`, `gemini_provider.py` —
  реализации поверх официальных SDK. Ретраи/backoff, маскирование ключей.
- Где поддерживается (Anthropic) — prompt caching статической части (правила).

### `prompts/`
- `templates.py` — system-промпт (правила игры, строгий формат ответа) и шаблон
  хода.
- `context_builder.py` — собирает сообщение хода: цвет, номер, FEN, легальные ходы,
  PGN, последние ходы, **объяснения обеих моделей**, остаток подсказок, при ретрае —
  причину отклонения. Возвращает структуру сообщений для провайдера.
- Формат ответа модели — строгий JSON: `{ "reasoning": "...", "move": "Nf3",
  "request_hint": false, "resign": false }`. Парсер терпим к обёрткам/текстовому
  мусору вокруг JSON.

### `arena/` (оркестратор)
- `player.py` — `ModelPlayer`: связывает `ModelConfig` + `LLMProvider`; делает ход:
  собирает контекст → вызывает провайдера → парсит `LLMResponse`.
- `game_runner.py` — `GameRunner`: главный цикл партии.
  - чередует стороны, ведёт `core.Board` и `GameRecord`;
  - валидирует ход; при нелегальном — корректирующее сообщение, инкремент счётчика;
    **3 подряд → техническое поражение**;
  - обрабатывает `request_hint` (если есть лимит и движок) и `resign`;
  - детектит окончание партии, проставляет `result`/`termination`;
  - эмитит события (`on_move`, `on_illegal`, `on_hint`, `on_end`) — для веба/WebSocket;
  - по завершении передаёт `GameRecord` в `storage` и (★) `analysis`.

### `engine/` (★ Stockfish)
- `stockfish.py` — UCI-обёртка через `python-chess`: `best_move(fen)`,
  `evaluate(fen) -> cp`, контекстный менеджер жизненного цикла процесса.
  Если бинарник недоступен — `EngineUnavailable`, ★-фичи отключаются с предупреждением.

### `analysis/` (★ разметка ходов)
- `annotate.py` — проходит по `GameRecord`: для каждой позиции берёт оценку движка,
  считает centipawn loss, классифицирует (`blunder/mistake/inaccuracy/good/brilliant`)
  по конфигурируемым порогам; собирает `AnalysisSummary` (accuracy, ключевые моменты).
- `commentary.py` (опц.) — LLM-комментарий ключевых моментов на основе линий движка
  и исходного рассуждения модели.

### `storage/`
- `repository.py` — запись/чтение `game.json`, создание папки партии,
  экспорт `game.pgn` (через `core.pgn`), сохранение `report.html`.
  Гарантирует, что секреты в артефакты не попадают.

### `report/`
- `render.py` + `board_image.py` — рендер доски `python-chess` в SVG (опц.
  растеризация в PNG через `cairosvg` для переносимости).
- `templates/report.html.j2` — Jinja2: шапка (игроки, итог, причина окончания),
  по ходам — доска, SAN, сторона, модель, рассуждение, нелегальные попытки, метка
  подсказки, оценка движка, бейдж классификации; (★) сводка accuracy и ключевые моменты.
  Итог — один self-contained HTML.

### `web/` (FastAPI)
- `app.py` — приложение, монтирование static/templates.
- `routes.py` — `GET /` (страница выбора моделей из каталога), `POST /games`
  (старт партии), `GET /games` (список), `GET /games/{id}` (просмотр отчёта).
- `ws.py` — WebSocket: подписка на события `GameRunner` для живого просмотра
  (обновление доски, ход, рассуждение).
- `static/`, `templates/` — лёгкий фронтенд (vanilla JS), доска рендерится
  сервером (SVG) и шлётся по WebSocket.

### Точки входа
- `web/app.py` (uvicorn) — основной режим (веб).
- `cli.py` — служебный запуск партии из терминала (для тестов/CI), переиспользует
  `GameRunner`.

## 3. Поток одной партии

```
Веб: выбор белых/чёрных моделей  ─POST /games─▶  GameRunner.run()
  loop по ходам:
    context_builder → ModelPlayer.move() → LLMResponse
      ├─ request_hint? → engine.best_move → запись HintRecord, повтор контекста
      ├─ resign?       → завершение партии
      └─ move:
           core.move_parsing → legal?
             ├─ нет → коррекция; attempts++; 3 → technical_loss
             └─ да  → core.Board.push; запись MoveRecord; событие on_move (WS)
    core.is_game_over? → result/termination
  storage.save(game.json) → core.pgn → game.pgn
  (★) analysis.annotate → AnalysisSummary → обновить game.json
  report.render → report.html
```

## 4. Протокол ответа модели

Запрашиваем строгий JSON; парсер устойчив к лишнему тексту вокруг:
```json
{ "reasoning": "почему этот ход", "move": "Nf3", "request_hint": false, "resign": false }
```
- `move` принимается в SAN или UCI.
- `request_hint: true` — если есть лимит и движок: на следующем запросе в контекст
  добавляется подсказка; счётчик уменьшается.
- Нераспознанный/нелегальный `move` → корректирующее сообщение + ретрай.

## 5. Обработка ошибок

- Сбой провайдера (сеть, rate-limit) → ретраи с экспоненциальным backoff; при
  исчерпании — партия помечается ошибкой, состояние сохраняется.
- Невалидный JSON ответа → трактуется как нелегальная попытка (с причиной).
- Stockfish недоступен → ★-фичи off, база работает.
- Ключ отсутствует → fail-fast на старте с понятным сообщением.

## 6. Тестируемость

- `core` (board, parsing, pgn), `prompts/context_builder`, `analysis/annotate`,
  `storage` — юнит-тесты на чистых данных.
- Провайдеры — на моках транспорта; реальные вызовы — отдельные `@pytest.mark`,
  `skip` без ключа.
- Движок — `skip`, если нет бинарника.
- E2E: «партия» из двух фейковых детерминированных игроков → проверка `game.json`,
  PGN, HTML.
