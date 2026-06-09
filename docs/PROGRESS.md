# PROGRESS — LLM Chess Arena

Живой трекер состояния проекта. Обновляется **в конце каждой сессии**.
Это первый файл, который читается в начале новой сессии (после `CLAUDE.md`).

> Правило: здесь хранится «где мы сейчас», а не «что строить» (это `ROADMAP.md`/`TODO.md`)
> и не «почему» (`DECISIONS.md`). Коротко и фактически.

## Текущее состояние

- **Фаза:** Phase 1 — Шахматное ядро (есть `Board` wrapper + краевые тесты окончания).
- **Последняя завершённая задача:** `test(core): board and endgame detection` —
  `tests/test_board_endgame.py` (6 шт): недостаток материала (K/K, K+B/K, K+N/K),
  75-ходовое правило (автоматическое), троекратное повторение (зависит от
  `auto_claim_draws`) и пятикратное (автоматическое). Проверяет контракт кодов
  `termination` и поведение флага D-012.
- **Следующая задача:** `feat(core): move parsing` из `docs/TODO.md` (Phase 1) —
  извлечение хода из текста/JSON ответа модели (SAN→UCI), внятная причина при неудаче.
  (Опционально остаётся хвост Phase 0: `test(config): settings and catalog`.)
- **Открытые вопросы:** нет (см. `docs/DECISIONS.md`).

## Как запускать / тестировать (заполнять по мере появления кода)

- Установка: `pip install -e ".[dev]"` (Python 3.11+).
- **Окружение:** пакет `arena` установлен editable в `.venv` репозитория. Запускать
  тесты/код именно через него: `\.venv\Scripts\python.exe -m pytest`
  (системный `python` пакет `arena` не видит → `ModuleNotFoundError: No module named 'arena'`).
- Тесты: `\.venv\Scripts\python.exe -m pytest` (сейчас 34 passed: config + catalog + board + endgame + smoke).
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
| 2026-06-09 | `test(core): board and endgame detection`: `tests/test_board_endgame.py` (6 шт) — недостаток материала, 75 ходов, троекратное/пятикратное повторение, поведение `auto_claim_draws`; pytest зелёный (34 passed) | _pending_ | `feat(core): move parsing` |
