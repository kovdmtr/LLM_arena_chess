"""Тесты флага ``include_legal_moves`` (D-021).

Проверяем, что список легальных ходов кладётся в промпт/контекст только при
``include_legal_moves=True``, а при ``False`` модель ходит по FEN/PGN (легальность
проверяется уже после ответа — это делает ``GameRunner``, см. тесты раннера).
Также фиксируем дефолты: партия (``PlayerSettings``) и конфиг по умолчанию — без
списка; сами функции ``prompts`` по умолчанию ``True`` (обратная совместимость).
"""

from datetime import datetime

from arena.config import AppConfig
from arena.config.settings import DEFAULT_CONFIG_PATH
from arena.core import Board
from arena.models import GameRecord, IllegalAttempt, PlayerInfo, PlayerSettings
from arena.prompts import build_context, build_system_prompt


def _game() -> GameRecord:
    return GameRecord(
        id="g1",
        created_at=datetime(2026, 6, 9, 12, 0, 0),
        players={
            "white": PlayerInfo(model_id="m-w", provider="openai", display_name="W"),
            "black": PlayerInfo(model_id="m-b", provider="openai", display_name="B"),
        },
    )


# --- контекст хода ----------------------------------------------------------


def test_context_includes_list_when_flag_on():
    text = build_context(_game(), Board(), include_legal_moves=True)
    assert "Legal moves (SAN):" in text
    assert "Nf3" in text


def test_context_omits_list_when_flag_off():
    board = Board()
    text = build_context(_game(), board, include_legal_moves=False)
    assert "Legal moves (SAN):" not in text
    # Но позиция и партия по-прежнему переданы — модель ходит по FEN/PGN.
    assert board.fen() in text
    assert "Game so far (PGN):" in text


def test_context_default_keeps_list_for_direct_callers():
    # Дефолт самой функции — True (обратная совместимость прямых вызовов/тестов).
    assert "Legal moves (SAN):" in build_context(_game(), Board())


def test_retry_wording_depends_on_flag():
    retry = IllegalAttempt(raw="Zz9", reason="ход не распознан")
    on = build_context(_game(), Board(), retry=retry, include_legal_moves=True)
    off = build_context(_game(), Board(), retry=retry, include_legal_moves=False)
    assert "Choose one move from the legal moves listed above." in on
    assert "legal in the current position" in off
    assert "listed above" not in off


# --- системный промпт -------------------------------------------------------


def test_system_prompt_promises_list_only_when_on():
    on = build_system_prompt(include_legal_moves=True)
    off = build_system_prompt(include_legal_moves=False)
    assert "the full list of legal moves" in on
    assert "the full list of legal moves" not in off
    # В обоих режимах остаются формат хода и запрет на пропуск.
    for prompt in (on, off):
        assert "SAN" in prompt and "UCI" in prompt
        assert "skipping a move is not allowed" in prompt
        assert '"reasoning"' in prompt and '"move"' in prompt


def test_system_prompt_off_has_no_unfilled_placeholders():
    prompt = build_system_prompt(include_legal_moves=False)
    for placeholder in ("{moves_clause}", "{legality}", "{correction_detail}", "{strike_tail}"):
        assert placeholder not in prompt


# --- дефолты партии и конфига ----------------------------------------------


def test_player_settings_default_omits_list():
    assert PlayerSettings().include_legal_moves is False


def test_default_config_omits_list():
    cfg = AppConfig.from_yaml(DEFAULT_CONFIG_PATH)
    assert cfg.arena.include_legal_moves is False
