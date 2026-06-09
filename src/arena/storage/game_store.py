"""Хранение партии на диске: ``GameRecord`` ↔ ``games/<id>/game.json`` (D-004).

``game.json`` — единственный источник истины по партии (D-004); PGN и HTML-отчёт
порождаются из него позже. Этот модуль отвечает только за сериализацию/чтение:

- ``game_dir`` — путь к папке партии ``games/<id>/`` (с проверкой ``id``);
- ``save_game`` — записать ``GameRecord`` в ``games/<id>/game.json`` (атомарно);
- ``load_game`` — прочитать ``GameRecord`` из файла или из папки партии.

Секреты в ``GameRecord`` отсутствуют по построению моделей (``PlayerInfo`` хранит
лишь ``model_id``, D-003), поэтому отдельной фильтрации при записи не требуется.
"""

from __future__ import annotations

from pathlib import Path

from arena.models import GameRecord

# Имя канонического файла партии внутри её папки (D-004).
GAME_JSON_NAME = "game.json"

# Корень для артефактов партий по умолчанию (совпадает с ``OutputConfig.games_dir``).
DEFAULT_GAMES_ROOT = "games"


class StorageError(ValueError):
    """Ошибка хранения партии: некорректный ``id``, отсутствие файла, битый JSON."""


def _validate_game_id(game_id: str) -> str:
    """Проверить, что ``game_id`` — безопасный одиночный сегмент пути.

    Защита от обхода каталога: ``id`` не должен быть пустым, содержать разделители
    пути (``/``/``\\``), точки-навигацию (``.``/``..``) или абсолютный путь.
    """
    if not game_id or game_id in {".", ".."}:
        raise StorageError(f"некорректный id партии: {game_id!r}")
    if "/" in game_id or "\\" in game_id:
        raise StorageError(
            f"id партии не должен содержать разделители пути: {game_id!r}"
        )
    return game_id


def game_dir(game_id: str, *, games_root: str | Path = DEFAULT_GAMES_ROOT) -> Path:
    """Вернуть путь к папке партии ``games_root/<id>`` (без создания на диске)."""
    return Path(games_root) / _validate_game_id(game_id)


def save_game(
    record: GameRecord, *, games_root: str | Path = DEFAULT_GAMES_ROOT
) -> Path:
    """Записать ``record`` в ``games_root/<id>/game.json`` и вернуть путь к файлу.

    Папка партии создаётся при необходимости. Запись атомарна (через временный
    файл + ``replace``), чтобы не оставить полупустой ``game.json`` при сбое.
    ``id`` берётся из самого ``record`` и проверяется как безопасный сегмент пути.
    """
    directory = game_dir(record.id, games_root=games_root)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / GAME_JSON_NAME

    payload = record.model_dump_json(indent=2)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(target)
    return target


def load_game(source: str | Path) -> GameRecord:
    """Прочитать ``GameRecord`` из ``source`` — файла ``game.json`` или папки партии.

    Если ``source`` — папка, читается ``source/game.json``. ``StorageError`` при
    отсутствии файла или невалидном содержимом.
    """
    path = Path(source)
    if path.is_dir():
        path = path / GAME_JSON_NAME
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise StorageError(f"файл партии не найден: {path}") from exc
    try:
        return GameRecord.model_validate_json(raw)
    except ValueError as exc:
        raise StorageError(f"не удалось разобрать {path}: {exc}") from exc
