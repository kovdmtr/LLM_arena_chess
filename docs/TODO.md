# TODO — LLM Chess Arena

Атомарные задачи. **1 задача = 1 коммит.** Формат коммитов: `type(scope): summary`
(напр. `feat(core): add board wrapper`). Отмечай `[x]` по мере выполнения.

**Каждая задача с кодом включает тесты и зелёный `pytest` перед коммитом** —
см. «Критерий готовности задачи» в `CLAUDE.md`. Отдельные `test(...)` пункты ниже —
это лишь крупные тестовые блоки, вынесенные в свой коммит; они не отменяют правило
писать тесты для каждой задачи.

Легенда: ★ — задача дополнительной функциональности.

## Phase 0 — Каркас и конфиг
- [x] `chore: init project` — `pyproject.toml`, зависимости, `README.md`, структура `src/arena/`, `tests/`.
- [x] `chore: add gitignore and env example` — `.gitignore` (`.env`, `games/`, кэши), `.env.example`.
- [x] `feat(config): load settings from .env and config.yaml` — `Settings` (pydantic-settings) + `config.yaml` по умолчанию.
- [x] `feat(config): model catalog` — парсинг `models:`, резолв `api_key_env`, fail-fast при отсутствии ключа.
- [ ] `test(config): settings and catalog` — юнит-тесты загрузки/валидации.

## Phase 1 — Шахматное ядро
- [x] `feat(core): board wrapper` — FEN, `legal_moves_san()`, `push()`, `is_game_over()`, `outcome()` + причина окончания.
- [x] `test(core): board and endgame detection` — мат/пат/ничьи/повторения.
- [ ] `feat(core): move parsing` — извлечение хода из текста/JSON (SAN→UCI), причина при неудаче.
- [ ] `test(core): move parsing` — легальные/нелегальные/мусорные входы.
- [ ] `feat(models): pydantic data models` — `MoveRecord`, `MessageRecord`, `HintRecord`, `GameRecord`, `LLMResponse`, `AnalysisSummary`.
- [ ] `feat(core): build PGN from GameRecord` — теги, ходы, комментарии-рассуждения.
- [ ] `test(core): pgn export` — валидность и совместимость тегов.

## Phase 2 — Провайдеры LLM
- [ ] `feat(providers): base interface and factory` — `LLMProvider.complete()`, фабрика по имени.
- [ ] `feat(providers): openai` — реализация + маскирование ключа.
- [ ] `feat(providers): anthropic` — реализация (+ prompt caching статичной части).
- [ ] `feat(providers): gemini` — реализация.
- [ ] `test(providers): mocked transport` — парсинг ответов, обработка ошибок на моках.
- [ ] `feat(arena): model player` — `ModelPlayer` поверх провайдера, возвращает `LLMResponse`.

## Phase 3 — Игровой цикл
- [ ] `feat(prompts): system prompt and response format` — правила + строгий JSON-формат ответа.
- [ ] `feat(prompts): context builder` — FEN, легальные ходы, PGN, история, объяснения обеих сторон, остаток подсказок, причина ретрая.
- [ ] `test(prompts): context builder` — содержимое контекста на фикстурах.
- [ ] `feat(arena): game runner core loop` — чередование сторон, ведение board+record, события.
- [ ] `feat(arena): illegal move retry and technical loss` — коррекция, счётчик, 3-strike → `technical_loss`.
- [ ] `feat(arena): game end and result/termination` — проставление `result`/`termination`, обработка `resign`.
- [ ] `feat(storage): persist and load game.json` — папка партии, запись/чтение, без секретов.
- [ ] `test(arena): e2e with fake players` — детерминированные игроки доигрывают партию, проверка `game.json`.

## Phase 4 — Артефакты
- [ ] `feat(storage): export game.pgn` — из `GameRecord` через `core.pgn`.
- [ ] `test(storage): pgn opens as valid game` — повторный парсинг PGN.
- [ ] `feat(report): board image rendering` — SVG (+ опц. PNG через cairosvg).
- [ ] `feat(report): html report template` — Jinja2: шапка, ходы, доски, рассуждения, итог.
- [ ] `feat(report): render report from game.json` — генерация self-contained `report.html`.
- [ ] `test(report): report renders from fixture` — smoke-тест рендера.

## Phase 5 — ★ Движок: подсказки и анализ
- [ ] `feat(engine): stockfish wrapper` ★ — `best_move`, `evaluate`, корректная деградация без бинарника.
- [ ] `test(engine): stockfish (skip if absent)` ★.
- [ ] `feat(arena): hint protocol` ★ — `request_hint`, лимит 3/игрока, запись `HintRecord`, инъекция подсказки в контекст.
- [ ] `feat(analysis): centipawn loss and classification` ★ — пороги из конфига, `AnalysisSummary`.
- [ ] `test(analysis): classification thresholds` ★.
- [ ] `feat(analysis): llm commentary of key moments` ★ (опц.) — комментарий на основе линий движка и рассуждения.
- [ ] `feat(report): show eval and classification badges` ★ — бейджи и сводка в отчёте.

## Phase 6 — ★ Веб-интерфейс
- [ ] `feat(web): fastapi app skeleton` ★ — приложение, static/templates, health.
- [ ] `feat(web): model selection page` ★ — каталог моделей, форма выбора белых/чёрных.
- [ ] `feat(web): start game endpoint` ★ — `POST /games`, запуск `GameRunner`.
- [ ] `feat(web): websocket live view` ★ — трансляция событий хода/доски/рассуждения.
- [ ] `feat(web): games list and report view` ★ — `GET /games`, `GET /games/{id}`.

## Phase 7 — Закалка
- [ ] `feat(providers): retry with backoff` — устойчивость к rate-limit/сетевым сбоям.
- [ ] `feat(obs): logging with key masking` — структурное логирование, маскирование секретов.
- [ ] `chore: graceful degradation without engine` — единый путь отключения ★ при отсутствии Stockfish.
- [ ] `test: full e2e run` — прогон база+★ на фейковых игроках.
- [ ] `docs: finalize and add sample game` — пример `game.json`/`game.pgn`/`report.html`, актуализация доков.

## Бэклог (после)
- [ ] Турниры из нескольких партий, таблица результатов.
- [ ] Экспорт нескольких партий, агрегированная статистика моделей.
- [ ] Альтернативные движки/глубины анализа, кеш оценок позиций.
