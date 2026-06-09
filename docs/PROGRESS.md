# PROGRESS — LLM Chess Arena

Живой трекер состояния проекта. Обновляется **в конце каждой сессии**.
Это первый файл, который читается в начале новой сессии (после `CLAUDE.md`).

> Правило: здесь хранится «где мы сейчас», а не «что строить» (это `ROADMAP.md`/`TODO.md`)
> и не «почему» (`DECISIONS.md`). Коротко и фактически.

## Текущее состояние

- **Фаза:** Phase 3 — Игровой цикл (идёт). Phase 0–2 закрыты. Готовы `ModelPlayer`
  и системный промпт; дальше — context builder (`feat(prompts): context builder`).
- **Последняя завершённая задача:** `feat(prompts): system prompt and response
  format` — `src/arena/prompts/system.py` (`build_system_prompt`, `system_message`,
  `RESPONSE_KEYS`). Статичный системный промпт (D-017): описывает правила (классика,
  без контроля времени, запрет пропуска хода D-015) и строгий JSON-протокол ответа
  D-007 (`{ reasoning, move, request_hint, resign }`, ход SAN/UCI из списка
  легальных, 3-strike → technical_loss, 3 подсказки/партию, сдача). Текст на
  английском, зависит только от лимитов партии (`hints_per_player`,
  `illegal_move_retries`), которые в игре неизменны → промпт кэшируем (D-019).
  Канонические ключи вынесены в `RESPONSE_KEYS` (единый источник для текста и
  тестов); пример-объект из промпта разбирается тем же `parse_response`, что и
  реальные ответы (тест согласованности). `system_message` оборачивает текст в
  `MessageRecord(role="system")`. Тесты `tests/test_prompts_system.py` (11 шт):
  все ключи протокола в тексте, подстановка дефолтных/кастомных лимитов, нет
  неподставленных плейсхолдеров, обе нотации + запрет пропуска, пример = валидный
  JSON с ключами протокола, round-trip через `parse_response`, обёртка в
  `MessageRecord`, стабильность текста, отсутствие секретов.
- **Следующая задача:** `feat(prompts): context builder` из `docs/TODO.md`
  (Phase 3) — сборка per-turn контекста: цвет+номер хода, FEN, легальные ходы
  (SAN), PGN, история, объяснения обеих сторон, остаток подсказок, причина ретрая.
- **Открытые вопросы:** нет (см. `docs/DECISIONS.md`).

## Как запускать / тестировать (заполнять по мере появления кода)

- Установка: `pip install -e ".[dev]"` (Python 3.11+).
- **Окружение:** пакет `arena` установлен editable в `.venv` репозитория. Запускать
  тесты/код именно через него: `\.venv\Scripts\python.exe -m pytest`
  (системный `python` пакет `arena` не видит → `ModuleNotFoundError: No module named 'arena'`).
- Тесты: `\.venv\Scripts\python.exe -m pytest` (сейчас 205 passed: config + catalog + board + endgame + move parsing + models + pgn + pgn export + providers base + providers openai + providers anthropic + providers gemini + providers transport (кросс-провайдерный) + arena player + prompts system + smoke).
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
