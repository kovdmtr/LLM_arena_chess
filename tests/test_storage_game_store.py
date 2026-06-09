"""Тесты хранения партии: ``GameRecord`` ↔ ``games/<id>/game.json`` (D-004, D-003)."""

from datetime import datetime, timezone

import pytest

from arena import (
    GameRecord,
    HintRecord,
    IllegalAttempt,
    MessageRecord,
    MoveRecord,
    PlayerInfo,
    PlayerSettings,
)
from arena.storage import (
    GAME_JSON_NAME,
    StorageError,
    game_dir,
    load_game,
    save_game,
)


def _record(game_id: str = "g-001") -> GameRecord:
    """Содержательный ``GameRecord`` для round-trip (ходы, история, попытки)."""
    return GameRecord(
        id=game_id,
        created_at=datetime(2026, 6, 9, 12, 0, tzinfo=timezone.utc),
        players={
            "white": PlayerInfo(
                model_id="gpt-x", provider="openai", display_name="GPT"
            ),
            "black": PlayerInfo(
                model_id="claude-x", provider="anthropic", display_name="Claude"
            ),
        },
        settings=PlayerSettings(illegal_move_retries=3, hints_per_player=3),
        result="1-0",
        termination="checkmate",
        moves=[
            MoveRecord(
                ply=1,
                side="white",
                san="e4",
                uci="e2e4",
                fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                fen_after="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                reasoning="контроль центра",
                illegal_attempts=[IllegalAttempt(raw="Ke2", reason="нелегальный")],
                hint=HintRecord(best_move="e2e4", eval_cp=30),
            ),
        ],
        messages={
            "white": [MessageRecord(role="system", content="rules")],
            "black": [],
        },
        hints_used={"white": 1, "black": 0},
    )


# --- game_dir: путь и валидация id ------------------------------------------


def test_game_dir_joins_root_and_id(tmp_path):
    path = game_dir("g-42", games_root=tmp_path)
    assert path == tmp_path / "g-42"


@pytest.mark.parametrize("bad", ["", ".", "..", "a/b", "a\\b"])
def test_game_dir_rejects_unsafe_id(bad):
    with pytest.raises(StorageError):
        game_dir(bad)


# --- save_game --------------------------------------------------------------


def test_save_game_writes_game_json_in_id_folder(tmp_path):
    target = save_game(_record("g-001"), games_root=tmp_path)
    assert target == tmp_path / "g-001" / GAME_JSON_NAME
    assert target.is_file()


def test_save_game_creates_missing_parent_dirs(tmp_path):
    root = tmp_path / "nested" / "games"
    target = save_game(_record(), games_root=root)
    assert target.is_file()


def test_save_game_overwrites_existing(tmp_path):
    save_game(_record("g-001"), games_root=tmp_path)
    rec = _record("g-001")
    rec.result = "0-1"
    save_game(rec, games_root=tmp_path)
    assert load_game(tmp_path / "g-001").result == "0-1"


def test_save_game_leaves_no_tmp_file(tmp_path):
    save_game(_record("g-001"), games_root=tmp_path)
    leftovers = list((tmp_path / "g-001").glob("*.tmp"))
    assert leftovers == []


def test_save_game_validates_id_from_record(tmp_path):
    bad = _record()
    bad.id = "../escape"
    with pytest.raises(StorageError):
        save_game(bad, games_root=tmp_path)


# --- load_game --------------------------------------------------------------


def test_round_trip_preserves_record(tmp_path):
    original = _record("g-rt")
    save_game(original, games_root=tmp_path)
    loaded = load_game(tmp_path / "g-rt")
    assert loaded == original


def test_load_game_accepts_file_path(tmp_path):
    target = save_game(_record("g-001"), games_root=tmp_path)
    loaded = load_game(target)
    assert loaded.id == "g-001"


def test_load_game_accepts_directory(tmp_path):
    save_game(_record("g-001"), games_root=tmp_path)
    loaded = load_game(tmp_path / "g-001")
    assert loaded.id == "g-001"


def test_load_game_missing_file_raises(tmp_path):
    with pytest.raises(StorageError):
        load_game(tmp_path / "nope" / GAME_JSON_NAME)


def test_load_game_invalid_json_raises(tmp_path):
    path = tmp_path / GAME_JSON_NAME
    path.write_text("{ not valid json", encoding="utf-8")
    with pytest.raises(StorageError):
        load_game(path)


def test_load_game_schema_mismatch_raises(tmp_path):
    path = tmp_path / GAME_JSON_NAME
    path.write_text('{"id": "x"}', encoding="utf-8")  # нет обязательных полей
    with pytest.raises(StorageError):
        load_game(path)


# --- D-003: никаких секретов в game.json ------------------------------------


def test_saved_game_json_has_no_secret_keys(tmp_path):
    target = save_game(_record("g-001"), games_root=tmp_path)
    text = target.read_text(encoding="utf-8")
    assert "api_key" not in text
    # Сохраняется только несекретное описание игрока (D-003).
    assert "model_id" in text and "gpt-x" in text
