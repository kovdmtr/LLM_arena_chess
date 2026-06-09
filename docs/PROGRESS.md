# PROGRESS — LLM Chess Arena

Живой трекер состояния проекта. Обновляется **в конце каждой сессии**.
Это первый файл, который читается в начале новой сессии (после `CLAUDE.md`).

> Правило: здесь хранится «где мы сейчас», а не «что строить» (это `ROADMAP.md`/`TODO.md`)
> и не «почему» (`DECISIONS.md`). Коротко и фактически.

## Текущее состояние

- **Фаза:** Phase 2 — Провайдеры LLM. Базовый интерфейс, фабрика, OpenAI,
  Anthropic и Gemini готовы — все три провайдера реализованы. Дальше:
  `test(providers): mocked transport` и `feat(arena): model player`.
- **Последняя завершённая задача:** `feat(providers): gemini` —
  `providers/gemini_provider.py`: `GeminiProvider(LLMProvider)` поверх SDK
  `google-genai` (`client.models.generate_content`). `complete` выносит
  system-реплики в `system_instruction` параметра `GenerateContentConfig` (через
  `\n\n`, как у Anthropic), маппит роль `assistant`→`model` в `contents`
  (`{"role", "parts": [{"text"}]}`), `temperature`/`max_tokens`(→`max_output_tokens`)
  тоже в конфиг; имя модели — `ResolvedModel.id`. Ответ — `response.text`;
  пустой/`None` → `ProviderError`. Клиент `genai.Client(api_key=...)` создаётся
  **лениво и кэшируется**, ошибки SDK оборачиваются в `ProviderError` с маскированием
  ключа через `mask_secret`. Регистрация `@register_provider("gemini")` + импорт в
  `providers/__init__`. Без отдельного prompt caching (D-018: explicit-cache API —
  вне рамок задачи). Тесты `test_providers_gemini.py` (12 шт, мок `genai.Client`:
  system_instruction/слияние, маппинг ролей, отсутствие system_instruction,
  трансляция параметров, ленивое кэширование, обёртка ошибок + маскирование,
  пустой/`None`/битый ответ, `repr` без ключа). D-018 в DECISIONS.
- **Следующая задача:** `test(providers): mocked transport` из `docs/TODO.md`
  (Phase 2) — общий набор тестов парсинга ответов/обработки ошибок на моках.
  Примечание: каждый провайдер уже покрыт своими мок-тестами; оценить, нужен ли
  отдельный кросс-провайдерный блок или пункт закрывается уже написанным.
- **Открытые вопросы:** нет (см. `docs/DECISIONS.md`).

## Как запускать / тестировать (заполнять по мере появления кода)

- Установка: `pip install -e ".[dev]"` (Python 3.11+).
- **Окружение:** пакет `arena` установлен editable в `.venv` репозитория. Запускать
  тесты/код именно через него: `\.venv\Scripts\python.exe -m pytest`
  (системный `python` пакет `arena` не видит → `ModuleNotFoundError: No module named 'arena'`).
- Тесты: `\.venv\Scripts\python.exe -m pytest` (сейчас 155 passed: config + catalog + board + endgame + move parsing + models + pgn + pgn export + providers base + providers openai + providers anthropic + providers gemini + smoke).
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
| 2026-06-09 | `feat(providers): gemini`: `providers/gemini_provider.py` (`GeminiProvider` поверх SDK `google-genai`, `generate_content`); system → `system_instruction`, маппинг роли `assistant`→`model`, параметры в `GenerateContentConfig`, ответ `response.text`, ленивое кэширование клиента, обёртка ошибок + `mask_secret`; регистрация `@register_provider("gemini")` + импорт в `__init__`; тесты `test_providers_gemini.py` (12 шт на моках); D-018 в DECISIONS; **все 3 провайдера готовы**; pytest зелёный (155 passed) | _pending_ | `test(providers): mocked transport` |
