"""Сгенерировать пример партии (``game.json`` + ``game.pgn`` + ``report.html``).

Детерминированно, без сети и без ключей: два скриптованных игрока доигрывают
короткую решительную партию (детский мат), белым по ходу выдаётся подсказка
движка (★, D-010), затем выполняется пост-анализ (★, D-009). Если рядом есть
Stockfish (``tools/bin/stockfish.exe`` или в ``PATH``) — оценки и классификация
настоящие; без него артефакты всё равно создаются (база, деградация D-008).

Результат кладётся в ``examples/sample-game/`` (коммитится — это образец вывода
для документации). Перегенерировать: ``python scripts/generate_sample_game.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from arena.analysis import analyze_game
from arena.arena import GameRunner, new_game_record
from arena.config import AnalysisConfig, EngineConfig
from arena.core import Board
from arena.engine import build_engine
from arena.models import LLMResponse, PlayerInfo
from arena.storage import export_pgn, export_report, save_game

_REPO_ROOT = Path(__file__).resolve().parents[1]
_EXAMPLES_DIR = _REPO_ROOT / "examples"
_STOCKFISH = _REPO_ROOT / "tools" / "bin" / "stockfish.exe"

SAMPLE_ID = "sample-game"
CREATED_AT = datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc)

# Детский мат (Scholar's mate): белые матуют на 4-м ходу. Рассуждения — иллюстративные.
WHITE = [
    ("e4", "Открываю центр и освобождаю ферзя со слоном."),
    ("Bc4", "Слон нацеливается на f7 — самое слабое поле чёрных."),
    ("Qh5", "Создаю двойную угрозу на f7 вместе со слоном."),
    ("Qxf7#", "Беру на f7 — это мат: король не уходит, фигуры не закрывают."),
]
BLACK = [
    ("e5", "Симметрично борюсь за центр."),
    ("Nc6", "Развиваю коня и держу e5."),
    ("Nf6", "Атакую ферзя h5 — но это упускает угрозу мата на f7."),
]


class _ScriptedPlayer:
    """Скриптованный игрок: ходы+рассуждения по очереди; опц. просит подсказку."""

    def __init__(self, info: PlayerInfo, script, *, hint_on_first=False):
        self._info = info
        self._script = list(script)
        self._idx = 0
        self._hint_on_first = hint_on_first
        self._hinted = False

    @property
    def info(self) -> PlayerInfo:
        return self._info

    def respond(self, messages) -> LLMResponse:
        move, reasoning = self._script[self._idx]
        if self._hint_on_first and not self._hinted:
            self._hinted = True
            return LLMResponse(reasoning=reasoning, move=move, request_hint=True)
        self._idx += 1
        return LLMResponse(reasoning=reasoning, move=move, request_hint=False)


def main() -> None:
    players = {
        "white": _ScriptedPlayer(
            PlayerInfo(model_id="gpt-4o", provider="openai", display_name="GPT-4o"),
            WHITE,
            hint_on_first=True,
        ),
        "black": _ScriptedPlayer(
            PlayerInfo(
                model_id="claude-opus-4-8",
                provider="anthropic",
                display_name="Claude Opus 4.8",
            ),
            BLACK,
        ),
    }
    game = new_game_record(players, game_id=SAMPLE_ID, created_at=CREATED_AT)

    engine_path = str(_STOCKFISH) if _STOCKFISH.is_file() else "stockfish"
    engine = build_engine(EngineConfig(enabled=True, path=engine_path))
    try:
        runner = GameRunner(players, game, board=Board(), engine=engine)
        runner.play()
        if engine is not None:
            from arena.analysis import ClassificationThresholds

            game.analysis = analyze_game(
                game,
                engine,
                thresholds=ClassificationThresholds.from_config(AnalysisConfig()),
            )
    finally:
        if engine is not None:
            engine.close()

    save_game(game, games_root=_EXAMPLES_DIR)
    export_pgn(game, games_root=_EXAMPLES_DIR)
    export_report(game, games_root=_EXAMPLES_DIR)

    folder = _EXAMPLES_DIR / SAMPLE_ID
    status = "with engine (star analysis)" if engine is not None else "no engine (base)"
    print(f"Sample game generated [{status}]: {folder}")
    print(f"  result: {game.result} ({game.termination})")
    if game.analysis is not None:
        print(f"  key moments: {len(game.analysis.key_moments)}")


if __name__ == "__main__":
    main()
