# PROGRESS — LLM Chess Arena

Живой трекер состояния проекта. Обновляется **в конце каждой сессии**.
Это первый файл, который читается в начале новой сессии (после `CLAUDE.md`).

> Правило: здесь хранится «где мы сейчас», а не «что строить» (это `ROADMAP.md`/`TODO.md`)
> и не «почему» (`DECISIONS.md`). Коротко и фактически.

## Текущее состояние

- **Фаза:** Phase 1 — Шахматное ядро (`Board` wrapper + парсинг ходов с полным покрытием).
- **Последняя завершённая задача:** `feat(models): pydantic data models` —
  `src/arena/models.py`: типизированная форма `game.json` (D-004). Модели
  `LLMResponse` (протокол D-007), `MessageRecord`, `IllegalAttempt`, `HintRecord`,
  `MoveRecord`, `PlayerInfo`, `PlayerSettings`, `PlayerAnalysis`, `KeyMoment`,
  `AnalysisSummary`, `GameRecord`. Стороны/роли/классы хода — через `Literal`
  (`Side`/`Role`/`Classification`); `model_id` потребовал `protected_namespaces=()`
  у `PlayerInfo` (иначе pydantic ругается на префикс `model_`). Все модели
  экспортированы из `arena`. Тесты `tests/test_models.py` (15 шт): дефолты,
  валидация (плохой `ply`/`side`/`classification`/`role`), независимость коллекций
  у `default_factory`, round-trip `GameRecord` через JSON. Секреты в модели не
  попадают (D-003).
- **Следующая задача:** `feat(core): build PGN from GameRecord` из `docs/TODO.md`
  (Phase 1) — сборка PGN из `GameRecord`: стандартные теги, ходы SAN,
  комментарии-рассуждения (`{...}`). Затем `test(core): pgn export`.
- **Открытые вопросы:** нет (см. `docs/DECISIONS.md`).

## Как запускать / тестировать (заполнять по мере появления кода)

- Установка: `pip install -e ".[dev]"` (Python 3.11+).
- **Окружение:** пакет `arena` установлен editable в `.venv` репозитория. Запускать
  тесты/код именно через него: `\.venv\Scripts\python.exe -m pytest`
  (системный `python` пакет `arena` не видит → `ModuleNotFoundError: No module named 'arena'`).
- Тесты: `\.venv\Scripts\python.exe -m pytest` (сейчас 91 passed: config + catalog + board + endgame + move parsing + models + smoke).
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
