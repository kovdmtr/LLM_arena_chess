# PROGRESS — LLM Chess Arena

Живой трекер состояния проекта. Обновляется **в конце каждой сессии**.
Это первый файл, который читается в начале новой сессии (после `CLAUDE.md`).

> Правило: здесь хранится «где мы сейчас», а не «что строить» (это `ROADMAP.md`/`TODO.md`)
> и не «почему» (`DECISIONS.md`). Коротко и фактически.

## Текущее состояние

- **Фаза:** Phase 3 — Игровой цикл (почти закрыта). Phase 0–2 закрыты. Готов
  `GameRunner` целиком: happy path, ретрай/техпоражение (D-006), финализация
  result/termination и resign (D-020). Остался один пункт Phase 3 —
  `feat(storage): persist and load game.json`, затем e2e-тест фейковыми игроками.
- **Последняя завершённая задача:** `feat(arena): game end and result/termination`
  (D-020) — `GameRunner._finalize` после остановки цикла проставляет
  `result`/`termination` из `Board.outcome()` для обычных окончаний (мат/пат/ничьи),
  не перезаписывая уже зафиксированные технические исходы; коды повторения сводятся
  к `repetition` (`_normalize_termination`). `resign: true` (D-007) теперь
  обрабатывается `_resign` (раньше был шов `GameRunnerError`): `termination=resign`,
  результат = победа соперника. Обрыв по `max_plies` оставляет `result="*"`.
  `GameRunnerError` оставлен зарезервированным типом ошибки раннера (на штатных
  путях не поднимается). D-020 в DECISIONS. Тесты `tests/test_arena_runner.py`
  (23 шт: +resign обе стороны, +resign в game_over, +insufficient_material сразу,
  +stalemate после хода, +max_plies оставляет "*", +юнит `_normalize_termination`;
  fool's mate теперь финализируется в `0-1`/`checkmate`).
- **Следующая задача:** `feat(storage): persist and load game.json` из `docs/TODO.md`
  (Phase 3) — папка партии `games/<id>/`, запись/чтение `GameRecord` ↔ `game.json`
  (D-004), без секретов (D-003). Затем `test(arena): e2e with fake players`.
- **Открытые вопросы:** нет (см. `docs/DECISIONS.md`).

## Как запускать / тестировать (заполнять по мере появления кода)

- Установка: `pip install -e ".[dev]"` (Python 3.11+).
- **Окружение:** пакет `arena` установлен editable в `.venv` репозитория. Запускать
  тесты/код именно через него: `\.venv\Scripts\python.exe -m pytest`
  (системный `python` пакет `arena` не видит → `ModuleNotFoundError: No module named 'arena'`).
- Тесты: `\.venv\Scripts\python.exe -m pytest` (сейчас 255 passed: config + catalog + board + endgame + move parsing + models + pgn + pgn export + providers base + providers openai + providers anthropic + providers gemini + providers transport (кросс-провайдерный) + arena player + arena runner + prompts system + prompts context (+ fixtures) + smoke).
- Запуск веб-UI: _TBD (`uvicorn ...`)_
- Служебный прогон партии: _TBD (`python -m arena.cli ...`)_

## Открытые хвосты / заметки

- Stockfish — опциональная зависимость; на машине разработки бинарник пока не проверен.
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
