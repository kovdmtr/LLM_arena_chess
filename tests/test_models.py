"""Тесты pydantic-моделей данных: дефолты, валидация, round-trip game.json."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from arena import (
    AnalysisSummary,
    GameRecord,
    HintRecord,
    IllegalAttempt,
    KeyMoment,
    LLMResponse,
    MessageRecord,
    MoveRecord,
    PlayerAnalysis,
    PlayerInfo,
    PlayerSettings,
)


# --- LLMResponse: протокол ответа модели (D-007) ----------------------------


def test_llm_response_defaults_are_empty_and_non_committal():
    resp = LLMResponse()
    assert resp.reasoning == ""
    assert resp.move is None
    assert resp.request_hint is False
    assert resp.resign is False


def test_llm_response_accepts_full_payload():
    resp = LLMResponse(
        reasoning="контроль центра", move="e4", request_hint=True, resign=False
    )
    assert resp.move == "e4"
    assert resp.request_hint is True


# --- MessageRecord -----------------------------------------------------------


def test_message_record_roles_are_constrained():
    msg = MessageRecord(role="system", content="rules")
    assert msg.role == "system"
    with pytest.raises(ValidationError):
        MessageRecord(role="tool", content="x")


# --- HintRecord --------------------------------------------------------------


def test_hint_record_minimal_and_full():
    minimal = HintRecord(best_move="e2e4")
    assert minimal.eval_cp is None and minimal.mate_in is None
    full = HintRecord(best_move="d2d4", eval_cp=30, mate_in=None)
    assert full.eval_cp == 30


# --- MoveRecord --------------------------------------------------------------


def _move(**overrides) -> MoveRecord:
    base = dict(
        ply=1,
        side="white",
        san="e4",
        uci="e2e4",
        fen_before="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        fen_after="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
    )
    base.update(overrides)
    return MoveRecord(**base)


def test_move_record_analysis_fields_default_to_none():
    move = _move()
    assert move.illegal_attempts == []
    assert move.hint_used is False
    assert move.hint is None
    assert move.engine_eval_cp is None
    assert move.classification is None


def test_move_record_ply_must_be_positive():
    with pytest.raises(ValidationError):
        _move(ply=0)


def test_move_record_side_is_constrained():
    with pytest.raises(ValidationError):
        _move(side="grey")


def test_move_record_classification_is_constrained():
    assert _move(classification="blunder").classification == "blunder"
    with pytest.raises(ValidationError):
        _move(classification="awesome")


def test_move_record_keeps_illegal_attempts_and_hint():
    move = _move(
        illegal_attempts=[IllegalAttempt(raw="Ke9", reason="нелегальный ход")],
        hint_used=True,
        hint=HintRecord(best_move="g1f3", eval_cp=20),
    )
    assert move.illegal_attempts[0].raw == "Ke9"
    assert move.hint.best_move == "g1f3"


# --- AnalysisSummary ---------------------------------------------------------


def test_analysis_summary_defaults():
    summary = AnalysisSummary()
    assert isinstance(summary.white, PlayerAnalysis)
    assert summary.black.blunders == 0
    assert summary.key_moments == []


def test_key_moment_validation():
    moment = KeyMoment(ply=34, classification="blunder", comment="зевок ферзя")
    assert moment.ply == 34
    with pytest.raises(ValidationError):
        KeyMoment(ply=1, classification="oops")


# --- PlayerInfo: без секретов, допускает model_id ----------------------------


def test_player_info_allows_model_id_field():
    # ``model_id`` начинается с зарезервированного префикса model_ — должно
    # работать без предупреждений/ошибок благодаря снятой защите namespace.
    player = PlayerInfo(model_id="gpt-4o", provider="openai", display_name="GPT-4o")
    assert player.model_id == "gpt-4o"
    assert "api_key" not in player.model_dump()


# --- GameRecord: round-trip и дефолты ----------------------------------------


def _game_record() -> GameRecord:
    return GameRecord(
        id="2026-06-09T12-00-00__gpt-4o__vs__claude",
        created_at=datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc),
        players={
            "white": PlayerInfo(
                model_id="gpt-4o", provider="openai", display_name="GPT-4o"
            ),
            "black": PlayerInfo(
                model_id="claude-opus-4-8",
                provider="anthropic",
                display_name="Claude Opus 4.8",
            ),
        },
        moves=[_move()],
    )


def test_game_record_defaults():
    game = _game_record()
    assert game.result == "*"
    assert game.termination is None
    assert game.analysis is None
    assert game.settings == PlayerSettings()
    assert game.messages == {"white": [], "black": []}
    assert game.hints_used == {"white": 0, "black": 0}


def test_game_record_round_trips_through_json():
    game = _game_record()
    game.messages["white"].append(MessageRecord(role="user", content="ход 1"))
    game.analysis = AnalysisSummary(
        white=PlayerAnalysis(accuracy=0.9, blunders=0),
        key_moments=[KeyMoment(ply=1, classification="good")],
    )

    dumped = game.model_dump_json()
    restored = GameRecord.model_validate_json(dumped)

    assert restored == game
    assert restored.players["black"].display_name == "Claude Opus 4.8"
    assert restored.moves[0].uci == "e2e4"
    assert restored.created_at == game.created_at


def test_game_record_default_collections_are_independent():
    # default_factory должен давать каждой записи свои коллекции, не общий объект.
    a = GameRecord(
        id="a",
        created_at=datetime(2026, 6, 9, tzinfo=timezone.utc),
        players={
            "white": PlayerInfo(model_id="m", provider="p", display_name="M"),
            "black": PlayerInfo(model_id="m", provider="p", display_name="M"),
        },
    )
    b = GameRecord(
        id="b",
        created_at=datetime(2026, 6, 9, tzinfo=timezone.utc),
        players={
            "white": PlayerInfo(model_id="m", provider="p", display_name="M"),
            "black": PlayerInfo(model_id="m", provider="p", display_name="M"),
        },
    )
    a.hints_used["white"] = 2
    a.messages["white"].append(MessageRecord(role="system", content="x"))
    assert b.hints_used["white"] == 0
    assert b.messages["white"] == []
