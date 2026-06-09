# PROGRESS — LLM Chess Arena

Живой трекер состояния проекта. Обновляется **в конце каждой сессии**.
Это первый файл, который читается в начале новой сессии (после `CLAUDE.md`).

> Правило: здесь хранится «где мы сейчас», а не «что строить» (это `ROADMAP.md`/`TODO.md`)
> и не «почему» (`DECISIONS.md`). Коротко и фактически.

## Текущее состояние

- **Фаза:** Phase 4 (артефакты) закрыта; **Phase 5 (★ движок: подсказки и анализ)
  в работе.** Phase 0–3 закрыты. Готов `GameRunner` (теперь **с протоколом подсказок**,
  D-010), слой `storage` (`game.json` + `game.pgn` + `report.html`), слой `report`
  (SVG/опц. PNG + Jinja2-отчёт) и ★ обёртка движка `engine/stockfish.py`
  (`best_move`/`evaluate`, деградация без бинарника). Дальше в Phase 5 — centipawn-loss
  анализ с классификацией (D-009).
- **Последняя завершённая задача:** `feat(arena): hint protocol` ★ — протокол подсказок
  движка в `GameRunner` (D-010): `request_hint: true` → `_serve_hint` тратит 1 из 3
  подсказок (`engine.best_move(fen)→HintRecord`, инкремент `hints_used[side]` **только
  при фактической выдаче**) и **перезапрашивает** ход с инъекцией подсказки в контекст
  (через уже готовый `context_message(hint=...)`); подсказка остаётся в контексте до
  конца полухода (в т.ч. при ретраях), пишется в `MoveRecord` (`hint_used`/`hint`),
  испускается событие `EVENT_HINT`. Не более одной подсказки на ход; без движка/при
  исчерпанном лимите/при `EngineUnavailableError` запрос игнорируется (база без
  Stockfish, D-008). Новый параметр `GameRunner(engine=...)` + Protocol `HintEngine`.
  Тесты `test_arena_runner.py` (+7): расход и запись `HintRecord`, инъекция в контекст +
  декремент остатка, событие, деградация без движка / при лимите 0 / при отказе движка,
  «одна подсказка на ход». До неё — `test(engine): stockfish (skip if absent)` и
  `feat(engine): stockfish wrapper` (обёртка UCI, D-008).
- **Следующая задача:** `feat(analysis): centipawn loss and classification` ★ из
  `docs/TODO.md` (Phase 5) — пороги из конфига, centipawn-loss относительно лучшего
  хода (`engine.evaluate`), классификация `blunder/…/brilliant`, заполнение
  `AnalysisSummary` (D-009).
- **Открытые вопросы:** нет (см. `docs/DECISIONS.md`).

## Как запускать / тестировать (заполнять по мере появления кода)

- Установка: `pip install -e ".[dev]"` (Python 3.11+).
- **Окружение:** пакет `arena` установлен editable в `.venv` репозитория. Запускать
  тесты/код именно через него: `\.venv\Scripts\python.exe -m pytest`
  (системный `python` пакет `arena` не видит → `ModuleNotFoundError: No module named 'arena'`).
- Тесты: `\.venv\Scripts\python.exe -m pytest` (сейчас 349 passed, 1 skipped: config + catalog + board + endgame + move parsing + models + pgn + pgn export + providers base/openai/anthropic/gemini/transport + arena player + arena runner (вкл. протокол подсказок ★) + prompts system + prompts context (+ fixtures) + storage game store (+ pgn export + pgn opens as valid game) + report board image (PNG skip без cairosvg) + report html template + report render from fixture + engine stockfish (real-binary тест проходит — движок в `tools/bin`) + arena e2e + smoke; единственный skip — PNG-рендер без `cairosvg`).
- Запуск веб-UI: _TBD (`uvicorn ...`)_
- Служебный прогон партии: _TBD (`python -m arena.cli ...`)_

## Открытые хвосты / заметки

- Stockfish (опциональная зависимость) **установлен и проверен** на машине разработки:
  пребилт Stockfish 18 (bmi2) лежит в `tools/bin/stockfish.exe` (в git не коммитится,
  `.gitignore`). Корневой `conftest.py` добавляет `tools/bin` в `PATH` только на время
  тестов, поэтому интеграционный тест движка теперь **выполняется** (не skip). Для
  прогона приложения вне pytest движок берётся из PATH или `engine.path` в `config.yaml`
  (provisioning PATH вне тестов — на усмотрение пользователя; систему не меняли).
- GitHub-remote не подключён (не требуется для локальной работы; можно добавить позже).

## Журнал сессий

Одна строка на сессию: дата · что сделано · коммит(ы) · что дальше.

| Дата       | Сделано                                              | Коммит(ы)        | Дальше              |
|------------|------------------------------------------------------|------------------|---------------------|
| 2026-06-09 | Документация проекта + инфраструктура сессий, git init | (initial commit) | `chore: init project` |
| 2026-06-09 | `chore: init project`: pyproject + скелет `src/arena/` (12 слоёв) + smoke-тест | `7bf8606` | `chore: add gitignore and env example` |
| 2026-06-09 | Добавлен «Критерий готовности задачи» (тесты + зелёный `pytest` обязательны перед коммитом) в `CLAUDE.md`/`TODO.md` | `4f69fd2`, `2ec354e` | `chore: add gitignore and env example` |
| 2026-06-09 | `chore: add gitignore and env example`: добавлен `.env.example` (3 ключа провайдеров); pytest зелёный (2 passed) | `12cd6f1` | `feat(config): load settings from .env and config.yaml` |
| 2026-06-09 | `feat(config): load settings`: дефолтный `config.yaml` + `config/settings.py` (`AppConfig.from_yaml`, `Secrets`, `Settings.load`); тесты `test_config.py`; pytest зелёный (9 passed) | `369da0c` | `feat(config): model catalog` |
| 2026-06-09 | `feat(config): model catalog`: `config/catalog.py` (`ModelCatalog`, `ResolvedModel`, `ConfigError`); резолв ключа по `api_key_env`, fail-fast, маскирование ключа; тесты `test_catalog.py`; pytest зелёный (19 passed) | `848d0fb` | `feat(core): board wrapper` |
| 2026-06-09 | `feat(core): board wrapper`: `core/board.py` (`Board`, `GameOutcome`); FEN/ходы/push/outcome, маппинг `chess.Termination`, `auto_claim_draws` (D-012); тесты `test_board.py`; pytest зелёный (28 passed) | `a11a011` | `test(core): board and endgame detection` |
| 2026-06-09 | `test(core): board and endgame detection`: `tests/test_board_endgame.py` (6 шт) — недостаток материала, 75 ходов, троекратное/пятикратное повторение, поведение `auto_claim_draws`; pytest зелёный (34 passed) | `6bb2225` | `feat(core): move parsing` |
| 2026-06-09 | `feat(core): move parsing`: `core/move_parsing.py` (`parse_move`/`ParsedMove`/`MoveParseError`) — SAN→UCI, снятие обёртки, причина при неудаче; публичные `Board.san_of/parse_san/parse_uci`; тесты `test_move_parsing.py` (20 шт); pytest зелёный (54 passed) | `c056fba` | `test(core): move parsing` |
| 2026-06-09 | `test(core): move parsing`: +11 тестов (en passant, регистр UCI, неоднозначность, null-move); guard против null-move `0000`/`--` в `_to_parsed` (D-015); pytest зелёный (65 passed) | `fae4aa2` | `feat(models): pydantic data models` |
| 2026-06-09 | `test(config): settings and catalog`: +11 краевых тестов загрузки/валидации (settings +7, catalog +4); Phase 0 закрыта; pytest зелёный (76 passed) | `5efa519` | `feat(models): pydantic data models` |
| 2026-06-09 | `feat(models): pydantic data models`: `src/arena/models.py` (11 моделей — `GameRecord` и др., Literal-типы, `protected_namespaces=()` для `model_id`), экспорт из `arena`; тесты `test_models.py` (15 шт, round-trip JSON); pytest зелёный (91 passed) | `8ff5ba8` | `feat(core): build PGN from GameRecord` |
| 2026-06-09 | `feat(core): build PGN from GameRecord`: `core/pgn.py` (`build_pgn`) — 7 тегов + служебные (D-016), ходы из uci → SAN, рассуждения как `{...}`, санитайз скобок/переносов; экспорт из `arena.core`; тесты `test_pgn.py` (9 шт); pytest зелёный (100 passed) | `8fd138a` | `test(core): pgn export` |
| 2026-06-09 | `test(core): pgn export`: `tests/test_pgn_export.py` (13 шт) — полная партия (детский мат) с round-trip, STR в каноническом порядке, рокировка/en passant/превращение, токены результата, override тегов, Unicode, без секретов; **Phase 1 закрыта**; pytest зелёный (113 passed) | `f2c2c04` | `feat(providers): base interface and factory` |
| 2026-06-09 | `feat(providers): base interface and factory`: `providers/base.py` (`LLMProvider.complete`, `ProviderError`, реестр + `register_provider`/`create_provider`); фабрика по имени, fail-fast, ключ не в `repr`; экспорт из `arena.providers`; тесты `test_providers_base.py` (10 шт); pytest зелёный (123 passed) | `c758e68` | `feat(providers): openai` |
| 2026-06-09 | `feat(providers): openai`: `providers/openai_provider.py` (`OpenAIProvider` поверх SDK `openai`, Chat Completions); ленивое кэширование клиента, обёртка ошибок SDK в `ProviderError`, утилита `mask_secret` в `base.py` (маскирование ключа); регистрация через `@register_provider("openai")` + импорт в `__init__`; тесты `test_providers_openai.py` (8 шт на моках); pytest зелёный (131 passed) | `fd70e0e` | `feat(providers): anthropic` |
| 2026-06-09 | `feat(providers): anthropic`: `providers/anthropic_provider.py` (`AnthropicProvider` поверх SDK `anthropic`, Messages API); system вынесен из `messages` в параметр `system` с `cache_control: ephemeral` (prompt caching, D-017), конкатенация text-блоков ответа, ленивое кэширование клиента, обёртка ошибок + `mask_secret`; регистрация `@register_provider("anthropic")` + импорт в `__init__`; тесты `test_providers_anthropic.py` (12 шт на моках); D-017 в DECISIONS; pytest зелёный (143 passed) | `f7d3ab1` | `feat(providers): gemini` |
| 2026-06-09 | `feat(providers): gemini`: `providers/gemini_provider.py` (`GeminiProvider` поверх SDK `google-genai`, `generate_content`); system → `system_instruction`, маппинг роли `assistant`→`model`, параметры в `GenerateContentConfig`, ответ `response.text`, ленивое кэширование клиента, обёртка ошибок + `mask_secret`; регистрация `@register_provider("gemini")` + импорт в `__init__`; тесты `test_providers_gemini.py` (12 шт на моках); D-018 в DECISIONS; **все 3 провайдера готовы**; pytest зелёный (155 passed) | `2ab06cc` | `test(providers): mocked transport` |
| 2026-06-09 | `test(providers): mocked transport`: `tests/test_providers_transport.py` (19 шт) — единый кросс-провайдерный контракт за фабрикой (реестр=3, тип провайдера, сырой текст, обёртка+маскирование ошибки, пустой ответ, ленивое кэширование, `repr` без ключа), параметризован по openai/anthropic/gemini через `_Case`/`_make_fake_client`; **Phase 2 закрыта**; pytest зелёный (174 passed) | `375b851` | `feat(arena): model player` |
| 2026-06-09 | `feat(arena): model player`: `src/arena/arena/player.py` (`ModelPlayer` + `parse_response`) — обёртка над провайдером: `respond` → `complete` → разбор сырого текста в `LLMResponse` (D-007); устойчивый JSON-парсер (баланс `{}` с учётом строк, выбор объекта с `move`, терпимость к типам, деградация без JSON → move=None); `info`/`repr` без ключа; **Phase 3 началась**; тесты `test_arena_player.py` (20 шт); pytest зелёный (194 passed) | `6a999ac` | `feat(prompts): system prompt and response format` |
| 2026-06-09 | `feat(prompts): system prompt and response format`: `src/arena/prompts/system.py` (`build_system_prompt`/`system_message`/`RESPONSE_KEYS`) — статичный системный промпт (правила + строгий JSON-протокол D-007), английский, зависит только от лимитов партии → кэшируем (D-019); ключи протокола вынесены в `RESPONSE_KEYS`, согласованность с `parse_response` под тестом; D-019 в DECISIONS; тесты `test_prompts_system.py` (11 шт); pytest зелёный (205 passed) | `99824d5` | `feat(prompts): context builder` |
| 2026-06-09 | `feat(prompts): context builder`: `src/arena/prompts/context.py` (`build_context`/`context_message`) — per-turn контекст (спека 3.6) из `GameRecord`+`Board`: цвет/номер хода, FEN, легальные ходы SAN, PGN-снимок (`core.build_pgn`, без комментариев), объяснения обеих сторон, остаток подсказок, опц. инъекция подсказки (D-010) и коррекция ретрая (D-006, причина = `IllegalAttempt`); тесты `test_prompts_context.py` (19 шт); pytest зелёный (224 passed) | `085514d` | `test(prompts): context builder` |
| 2026-06-09 | `test(prompts): context builder`: `test_prompts_context_fixtures.py` (8 шт) — фикстурные сценарии: точный блок объяснений, round-trip встроенного PGN-снимка, совпадение списка легальных ходов с доской, отслеживание очереди по префиксам, порядок секций, «подсказка+ретрай», остаток подсказок по стороне, без секретов; pytest зелёный (232 passed) | `e855a75` | `feat(arena): game runner core loop` |
| 2026-06-09 | `feat(arena): game runner core loop`: `src/arena/arena/runner.py` (`GameRunner`/`GameEvent`/`GameRunnerError`/`new_game_record` + `EVENT_*`) — главный цикл: чередование сторон, ведение `Board`+`GameRecord`, события, самодостаточный срез `[system, context]` на ход, запись `MoveRecord` и per-side истории; нелегальный/пустой ход и resign → `GameRunnerError` (швы под D-006/финализацию); экспорт из `arena.arena`; тесты `test_arena_runner.py` (10 шт, детский мат на `_ScriptedPlayer`); pytest зелёный (242 passed) | `cf4dc34` | `feat(arena): illegal move retry and technical loss` |
| 2026-06-09 | `feat(arena): illegal move retry and technical loss`: цикл ретраев в `_play_turn` (D-006) — нелегальный ход → `IllegalAttempt` + коррекция `context(retry=...)` + повтор; счётчик локален ходу, `illegal_move_retries` подряд → `_technical_loss` (result+`termination=technical_loss`); попытки в `MoveRecord.illegal_attempts`; событие `EVENT_ILLEGAL`, `EVENT_GAME_OVER` несёт result/termination; тесты `test_arena_runner.py` (17 шт); pytest зелёный (249 passed) | `22a6505` | `feat(arena): game end and result/termination` |
| 2026-06-09 | `feat(arena): game end and result/termination` (D-020): `_finalize` ставит result/termination из `Board.outcome()` для обычных окончаний (не перезаписывая техисходы), повторение → `repetition`; `resign` → `_resign` (termination=resign, победа соперника) вместо шва `GameRunnerError`; `max_plies` оставляет `"*"`; D-020 в DECISIONS; тесты `test_arena_runner.py` (23 шт); **Phase 3 — остался storage**; pytest зелёный (255 passed) | `684e3c9` | `feat(storage): persist and load game.json` |
| 2026-06-09 | `feat(storage): persist and load game.json` (D-004/D-003): `storage/game_store.py` — `save_game` (атомарная запись `games/<id>/game.json`, mkdir), `load_game` (из файла/папки), `game_dir`, `_validate_game_id` (анти-traversal), `StorageError`; экспорт из `arena.storage`; тесты `test_storage_game_store.py` (18 шт); **Phase 3 — остался e2e-тест**; pytest зелёный (273 passed) | `2459237` | `test(arena): e2e with fake players` |
| 2026-06-09 | `test(arena): e2e with fake players`: `test_arena_e2e.py` (6 шт) — фейковые игроки доигрывают мат Шольяра, `save_game`→`load_game` round-trip, детали ходов, сборка PGN из загруженной записи, путь файла, без секретов; **Phase 3 закрыта**; pytest зелёный (279 passed) | `adc6ec4` | `feat(storage): export game.pgn` |
| 2026-06-09 | `feat(storage): export game.pgn` (D-004): `storage.export_pgn` — PGN из `GameRecord` через `core.build_pgn` в `games/<id>/game.pgn` (атомарно, финальный `\n`, флаг `include_reasoning`); общий хелпер `_atomic_write` (переиспользует `save_game`); экспорт `PGN_NAME`/`export_pgn`; тесты `test_storage_game_store.py` (+7, всего 25); **Phase 4 началась**; pytest зелёный (286 passed) | `a4bdcb1` | `test(storage): pgn opens as valid game` |
| 2026-06-09 | `test(storage): pgn opens as valid game`: `test_storage_game_store.py` (+6, всего 31) — экспортированный **файл** перечитывается `chess.pgn.read_game` и сверяется с `GameRecord` (SAN/UCI, легальное перепроигрывание до мата, теги Result/Termination, ничья, round-trip `save→load→export`); фикстура «детского мата» через `python-chess`; pytest зелёный (292 passed) | `832dbe9` | `feat(report): board image rendering` |
| 2026-06-09 | `feat(report): board image rendering` (D-005): `report/board_image.py` — `render_board_svg(fen)`/`render_move_svg(MoveRecord)` поверх `chess.svg` (подсветка последнего хода и шаха, ориентация, размер); опц. PNG `svg_to_png` через `cairosvg` (extra `report-png`) с деградацией `PngUnavailableError`, `png_available`; тесты `test_report_board_image.py` (10, +1 skip без cairosvg); pytest зелёный (302 passed, 1 skipped) | `acd2d0c` | `feat(report): html report template` |
| 2026-06-09 | `feat(report): html report template`: `report/template.py` (`render_report_html`) + `report/templates/report.html.j2` — самодостаточный HTML: шапка (игроки/модели/итог), лента ходов с inline-SVG досками, рассуждения, бейджи классификации/оценки ★ (если есть), подсказки; автоэкран пользовательского текста, SVG как `Markup`; тесты `test_report_template.py` (15); pytest зелёный (317 passed, 1 skipped) | `7772f12` | `feat(report): render report from game.json` |
| 2026-06-09 | `feat(report): render report from game.json`: `storage.export_report` пишет self-contained `games/<id>/report.html` из `GameRecord` через `report.render_report_html` (атомарно, `_atomic_write`); inline SVG (D-013), флаг `include_boards`; экспорт `REPORT_NAME`/`export_report`; pytest зелёный | `4a02425` | `test(report): report renders from fixture` |
| 2026-06-09 | `test(report): report renders from fixture`: `test_report_render_from_fixture.py` (9 шт) — фикстура «детского мата» → `export_report` пишет файл, который self-contained (DOCTYPE/inline SVG/без `<img>`), показывает игроков/ходы/итог, рядом с `game.json`, без `.tmp`, валидирует id, без секретов, рендерится после save→load; **Phase 4 закрыта**; pytest зелёный | `86ecfbe` | `feat(engine): stockfish wrapper` |
| 2026-06-09 | `feat(engine): stockfish wrapper` (D-008): ★ `engine/stockfish.py` (`StockfishEngine` + `EngineUnavailableError`) поверх python-chess UCI — `best_move(fen)→HintRecord` (uci + eval_cp/mate_in, POV ходящей стороны, D-010), `evaluate(fen)→cp` (мат→±100000 для D-009); ленивый запуск, контекстный менеджер, `opener` инъектируется для тестов; нет бинарника → `EngineUnavailableError`; **Phase 5 началась**; pytest зелёный | `81c590f` | `test(engine): stockfish (skip if absent)` |
| 2026-06-09 | `test(engine): stockfish (skip if absent)`: ★ `test_engine_stockfish.py` (15 шт + 1 skip) — разбор оценок на фейковом движке (`.relative`/мат/глубина), жизненный цикл процесса (ленивый запуск/идемпотентный close/контекстный менеджер/переоткрытие), деградация в `EngineUnavailableError`; интеграция с реальным Stockfish пропускается без бинарника (`shutil.which`); pytest зелёный (341 passed, 2 skipped) | `3fd4183` | `feat(arena): hint protocol` ★ |
| 2026-06-09 | `feat(arena): hint protocol` ★ (D-010): протокол подсказок в `GameRunner` — `request_hint`→`_serve_hint` тратит 1 из 3 (только при выдаче), перезапрос с инъекцией подсказки в контекст, запись `MoveRecord.hint_used`/`hint`, событие `EVENT_HINT`; ≤1 подсказка на ход; деградация без движка/при лимите/`EngineUnavailableError` (D-008); параметр `GameRunner(engine=...)` + Protocol `HintEngine`; уточнения в D-010; тесты `test_arena_runner.py` (+7); pytest зелёный (349 passed, 1 skipped) | _pending_ | `feat(analysis): centipawn loss and classification` ★ |
