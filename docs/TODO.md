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
- [x] `test(config): settings and catalog` — юнит-тесты загрузки/валидации.

## Phase 1 — Шахматное ядро
- [x] `feat(core): board wrapper` — FEN, `legal_moves_san()`, `push()`, `is_game_over()`, `outcome()` + причина окончания.
- [x] `test(core): board and endgame detection` — мат/пат/ничьи/повторения.
- [x] `feat(core): move parsing` — извлечение хода из текста/JSON (SAN→UCI), причина при неудаче.
- [x] `test(core): move parsing` — легальные/нелегальные/мусорные входы.
- [x] `feat(models): pydantic data models` — `MoveRecord`, `MessageRecord`, `HintRecord`, `GameRecord`, `LLMResponse`, `AnalysisSummary`.
- [x] `feat(core): build PGN from GameRecord` — теги, ходы, комментарии-рассуждения.
- [x] `test(core): pgn export` — валидность и совместимость тегов.

## Phase 2 — Провайдеры LLM
- [x] `feat(providers): base interface and factory` — `LLMProvider.complete()`, фабрика по имени.
- [x] `feat(providers): openai` — реализация + маскирование ключа.
- [x] `feat(providers): anthropic` — реализация (+ prompt caching статичной части).
- [x] `feat(providers): gemini` — реализация.
- [x] `test(providers): mocked transport` — парсинг ответов, обработка ошибок на моках.
- [x] `feat(arena): model player` — `ModelPlayer` поверх провайдера, возвращает `LLMResponse`.

## Phase 3 — Игровой цикл
- [x] `feat(prompts): system prompt and response format` — правила + строгий JSON-формат ответа.
- [x] `feat(prompts): context builder` — FEN, легальные ходы, PGN, история, объяснения обеих сторон, остаток подсказок, причина ретрая.
- [x] `test(prompts): context builder` — содержимое контекста на фикстурах.
- [x] `feat(arena): game runner core loop` — чередование сторон, ведение board+record, события.
- [x] `feat(arena): illegal move retry and technical loss` — коррекция, счётчик, 3-strike → `technical_loss`.
- [x] `feat(arena): game end and result/termination` — проставление `result`/`termination`, обработка `resign`.
- [x] `feat(storage): persist and load game.json` — папка партии, запись/чтение, без секретов.
- [x] `test(arena): e2e with fake players` — детерминированные игроки доигрывают партию, проверка `game.json`.

## Phase 4 — Артефакты
- [x] `feat(storage): export game.pgn` — из `GameRecord` через `core.pgn`.
- [x] `test(storage): pgn opens as valid game` — повторный парсинг PGN.
- [x] `feat(report): board image rendering` — SVG (+ опц. PNG через cairosvg).
- [x] `feat(report): html report template` — Jinja2: шапка, ходы, доски, рассуждения, итог.
- [x] `feat(report): render report from game.json` — генерация self-contained `report.html`.
- [x] `test(report): report renders from fixture` — smoke-тест рендера.
- [x] `feat(report): interactive single-board replay` ★ — одна доска + перемотка ходов (⏮◀▶⏭, слайдер, клавиши, клик по ходу) вместо ленты картинок; self-contained (встроенный JS). Логику переиспользует Phase 6 для веб-просмотра.

## Phase 5 — ★ Движок: подсказки и анализ
- [x] `feat(engine): stockfish wrapper` ★ — `best_move`, `evaluate`, корректная деградация без бинарника.
- [x] `test(engine): stockfish (skip if absent)` ★.
- [x] `feat(arena): hint protocol` ★ — `request_hint`, лимит 3/игрока, запись `HintRecord`, инъекция подсказки в контекст.
- [x] `feat(analysis): centipawn loss and classification` ★ — пороги из конфига, `AnalysisSummary`.
- [x] `test(analysis): classification thresholds` ★.
- [x] `feat(analysis): llm commentary of key moments` ★ (опц.) — комментарий на основе линий движка и рассуждения.
- [x] `feat(report): show eval and classification badges` ★ — бейджи и сводка в отчёте.

## Phase 6 — ★ Веб-интерфейс
- [x] `feat(web): fastapi app skeleton` ★ — приложение, static/templates, health.
- [x] `feat(web): model selection page` ★ — каталог моделей, форма выбора белых/чёрных.
- [x] `feat(web): start game endpoint` ★ — `POST /games`, запуск `GameRunner`.
- [x] `feat(web): websocket live view` ★ — трансляция событий хода/доски/рассуждения.
- [x] `feat(web): games list and report view` ★ — `GET /games`, `GET /games/{id}`.

## Доп. изменения (вне исходных фаз)
- [x] `feat(prompts): optional legal-moves list` ★ (D-021) — флаг `include_legal_moves` (дефолт `false`): ИИ не получает список легальных ходов, легальность проверяется после хода (ретрай D-006). Сквозной `config.yaml`→`ArenaConfig`/`PlayerSettings`→`system`/`context`.

## Phase 7 — Закалка
- [x] `feat(providers): retry with backoff` — устойчивость к rate-limit/сетевым сбоям (D-022).
- [x] `feat(obs): logging with key masking` — структурное логирование, маскирование секретов (D-023).
- [x] `chore: graceful degradation without engine` — единый путь отключения ★ при отсутствии Stockfish; `engine.build_engine` + подключение движка/пост-анализа в веб-партии (D-024).
- [x] `test: full e2e run` — прогон база+★ на фейковых игроках (`test_full_e2e.py`: партия+подсказка+анализ+комментарий → game.json/PGN/report.html).
- [x] `docs: finalize and add sample game` — пример в `examples/sample-game/` (`game.json`/`game.pgn`/`report.html`, реальный анализ Stockfish) + генератор `scripts/generate_sample_game.py`; README/ROADMAP актуализированы. **Phase 7 закрыта.**

## Phase 8 — Бэклог (расширения)
Атомизация трёх бэклог-пунктов. Альтернативные движки/глубины анализа уже
поддержаны (`engine.path` — любой UCI-бинарник, `engine.analysis_depth`/`hint_depth`
в `config.yaml`); из бэклога-3 остаётся кеш оценок позиций.

- [x] `feat(engine): position eval cache` — обёртка `CachingEngine` (кеш `evaluate`/`best_move` по `(fen, depth)`), drop-in, опц. в `build_engine`. _(бэклог-3)_
- [x] `feat(stats): aggregate model statistics across games` — `stats`-слой: `ModelStats`/`StatsTable`, `aggregate_stats(records)` (партии, W/L/D, очки, score%, средняя точность, зевки/ошибки/неточности, подсказки), загрузка записей из каталога. _(бэклог-2)_
- [x] `feat(report): stats report and multi-game PGN export` — `render_stats_html` + `storage.export_combined_pgn`/`export_stats_report`. _(бэклог-2)_
- [x] `feat(tournament): round-robin pairings and models` — модели `TournamentRecord`/`TournamentGame`, генерация пар `round_robin(models, double=…)`. _(бэклог-1)_
- [x] `feat(tournament): runner with standings and report` — `TournamentRunner` (фейк-тестируемый `player_factory`) проигрывает пары, сохраняет партии, считает таблицу (через `stats`), рендерит standings-отчёт. **Phase 8 закрыта.** _(бэклог-1)_

## Фича: стратегия/план (непрерывность замысла)
ИИ на каждом ходу формулирует **приватный rolling-план** (`strategy`) и статус
`plan_status` (start/continue/adapt/abandon); план его последнего хода
ре-инъектируется ему же на следующем ходу — партия играется как связная игра, а не
оценка позиции с нуля. Решения: только последний план; приватно (соперник не видит);
включено по умолчанию; статус continue/adapt/abandon. См. дизайн в сессии / `DECISIONS.md`.

- [x] `feat(models): strategy and plan_status fields` — поля в `LLMResponse`/`MoveRecord` + `PlanStatus` Literal.
- [x] `feat(prompts): strategy/plan_status in response protocol` — `STRATEGY_KEYS`, гейтед-вариант промпта (`include_strategy`: reasoning↔strategy + контракт непрерывности + приватность), `parse_response` читает `strategy`/`plan_status` мягко (нормализация статуса, дефолт `start`).
- [x] `feat(config): strategy settings` — `StrategyConfig`/`ArenaConfig.strategy` + `config.yaml` + `PlayerSettings.strategy_enabled` (дефолт on); мост `ArenaConfig.to_player_settings()` (config.yaml теперь реально драйвит настройки партии — закрыт латентный пробел), проброс в `system` (раннер) + entry-points (web/cli/tournament).
- [ ] `feat(prompts): inject current plan into context` — блок текущего плана из последнего хода стороны, первый ход, приватность, под флагом.
- [ ] `feat(arena): persist strategy on move` — `_apply_move` пишет `strategy`/`plan_status`; план хода N виден стороне на ходу N+2.
- [ ] `feat(report): show move plan and status badge` — строка плана + бейдж статуса в отчёте.
- [ ] (опц.) `feat(analysis): plan-adherence commentary` — комментарий учитывает следование плану.

## Бэклог (после Phase 8)
- [ ] Веб-UI для турниров (старт/наблюдение/таблица в браузере).
- [x] CLI-обёртка прогона партии/турнира (`python -m arena.cli …`) — команды `models`/`play`/`tournament`, переиспользуют `GameRunner`/`TournamentRunner`/`storage`; UTF-8 вывод на Windows.
