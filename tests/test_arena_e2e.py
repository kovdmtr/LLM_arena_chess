"""E2E-тест Phase 3: фейковые игроки доигрывают партию, результат сохраняется.

Связывает воедино весь игровой слой и хранение: ``GameRunner`` с
детерминированными игроками доигрывает партию до мата, ``storage.save_game``
пишет ``GameRecord`` в ``games/<id>/game.json`` (D-004), затем ``load_game``
читает его обратно. Проверяем, что персист — точный round-trip и что ``game.json``
лежит по ожидаемому пути и не содержит секретов (D-003).

В отличие от юнит-тестов ``GameRunner`` (там проверяется механика цикла), здесь
важна именно сквозная цепочка: партия → запись на диск → чтение → совпадение.
"""

from __future__ import annotations

from datetime import datetime, timezone

from arena.arena import GameRunner, new_game_record
from arena.core import Board, build_pgn
from arena.models import LLMResponse, PlayerInfo
from arena.storage import GAME_JSON_NAME, load_game, save_game

CREATED_AT = datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc)

# Мат Шольяра (scholar's mate): белые матуют на 4-м ходу.
WHITE_MOVES = ["e4", "Bc4", "Qh5", "Qxf7#"]
BLACK_MOVES = ["e5", "Nc6", "Nf6"]


class _FakePlayer:
    """Детерминированный игрок без сети: отдаёт ходы из скрипта по очереди.

    Дублирует утиный контракт ``ModelPlayer`` (``info`` + ``respond``), которого
    достаточно раннеру.
    """

    def __init__(self, model_id: str, moves: list[str]) -> None:
        self._info = PlayerInfo(
            model_id=model_id, provider="fake", display_name=model_id.upper()
        )
        self._moves = list(moves)
        self._idx = 0

    @property
    def info(self) -> PlayerInfo:
        return self._info

    def respond(self, messages) -> LLMResponse:
        move = self._moves[self._idx]
        self._idx += 1
        return LLMResponse(reasoning=f"play {move}", move=move)


def _play_full_game(game_id: str = "e2e-001"):
    """Доиграть мат Шольяра фейковыми игроками; вернуть заполненный ``GameRecord``."""
    players = {
        "white": _FakePlayer("white-model", WHITE_MOVES),
        "black": _FakePlayer("black-model", BLACK_MOVES),
    }
    game = new_game_record(players, game_id=game_id, created_at=CREATED_AT)
    runner = GameRunner(players, game, board=Board())
    return runner.play()


def test_full_game_reaches_checkmate():
    game = _play_full_game()

    assert [m.san for m in game.moves] == [
        "e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6", "Qxf7#",
    ]
    assert game.result == "1-0"
    assert game.termination == "checkmate"


def test_game_persists_to_id_folder(tmp_path):
    game = _play_full_game("e2e-001")
    target = save_game(game, games_root=tmp_path)

    assert target == tmp_path / "e2e-001" / GAME_JSON_NAME
    assert target.is_file()


def test_saved_game_round_trips_through_disk(tmp_path):
    game = _play_full_game()
    save_game(game, games_root=tmp_path)

    loaded = load_game(tmp_path / game.id)
    assert loaded == game


def test_loaded_game_carries_full_move_detail(tmp_path):
    game = _play_full_game()
    save_game(game, games_root=tmp_path)
    loaded = load_game(tmp_path / game.id)

    assert len(loaded.moves) == 7
    first = loaded.moves[0]
    assert first.uci == "e2e4"
    assert first.reasoning == "play e4"
    assert first.fen_before == Board().fen()
    # FEN-цепочка не рвётся при сериализации.
    assert first.fen_after == loaded.moves[1].fen_before
    # История сообщений по сторонам сохранена.
    assert loaded.messages["white"][0].role == "system"


def test_persisted_game_is_pgn_buildable(tmp_path):
    """game.json — источник истины: из загруженной записи строится валидный PGN."""
    game = _play_full_game()
    save_game(game, games_root=tmp_path)
    loaded = load_game(tmp_path / game.id)

    pgn = build_pgn(loaded)
    # Рассуждения идут комментариями {...}, поэтому ходы не стоят подряд.
    assert "1. e4 { play e4 }" in pgn
    assert "Qxf7#" in pgn
    assert pgn.rstrip().endswith("1-0")


def test_persisted_game_has_no_secrets(tmp_path):
    game = _play_full_game()
    target = save_game(game, games_root=tmp_path)

    text = target.read_text(encoding="utf-8")
    assert "api_key" not in text
    assert "fake" in text  # несекретное описание провайдера сохранено (D-003)
