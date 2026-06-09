# PROGRESS — LLM Chess Arena

Живой трекер состояния проекта. Обновляется **в конце каждой сессии**.
Это первый файл, который читается в начале новой сессии (после `CLAUDE.md`).

> Правило: здесь хранится «где мы сейчас», а не «что строить» (это `ROADMAP.md`/`TODO.md`)
> и не «почему» (`DECISIONS.md`). Коротко и фактически.

## Текущее состояние

- **Фаза:** Phase 1 — Шахматное ядро (почти закрыта: остался `test(core): pgn export`).
- **Последняя завершённая задача:** `feat(core): build PGN from GameRecord` —
  `src/arena/core/pgn.py`: публичная `build_pgn(game) -> str` собирает текстовый PGN
  из `GameRecord` через `python-chess` (D-004 — PGN порождается из `game.json`).
  Теги: семь обязательных (Event/Site/Date/Round/White/Black/Result) + служебные
  `Termination`, `WhiteModel`/`BlackModel`, `WhiteProvider`/`BlackProvider` (D-016).
  Ходы применяются из `MoveRecord.uci` → корректные SAN и нумерация; рассуждения
  идут комментариями `{...}` (опц. флаг `include_reasoning`); `_clean_comment`
  обезвреживает фигурные скобки (`{`/`}` → `(`/`)`) и переводы строк. Секретов в PGN
  нет (D-003) — в тегах только `model_id`. Экспорт из `arena.core`. Тесты
  `tests/test_pgn.py` (9 шт): семь тегов, служебные теги без секретов, SAN-порядок,
  комментарии-рассуждения и их отключение, санитайз скобок/переводов строк,
  round-trip через `chess.pgn.read_game`, пустая партия.
- **Следующая задача:** `test(core): pgn export` из `docs/TODO.md` (Phase 1) —
  расширенный блок тестов на валидность/совместимость PGN (полноценная партия,
  перепарсинг тегов, кромочные случаи). После — переход в Phase 2 (провайдеры).
- **Открытые вопросы:** нет (см. `docs/DECISIONS.md`).

## Как запускать / тестировать (заполнять по мере появления кода)

- Установка: `pip install -e ".[dev]"` (Python 3.11+).
- **Окружение:** пакет `arena` установлен editable в `.venv` репозитория. Запускать
  тесты/код именно через него: `\.venv\Scripts\python.exe -m pytest`
  (системный `python` пакет `arena` не видит → `ModuleNotFoundError: No module named 'arena'`).
- Тесты: `\.venv\Scripts\python.exe -m pytest` (сейчас 100 passed: config + catalog + board + endgame + move parsing + models + pgn + smoke).
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
