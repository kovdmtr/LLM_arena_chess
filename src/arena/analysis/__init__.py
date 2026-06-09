"""★ Разметка качества ходов: centipawn loss, классификация (D-009) и LLM-комментарий."""

from arena.analysis.analyzer import EvalEngine, analyze_game
from arena.analysis.classify import ClassificationThresholds, classify_cpl
from arena.analysis.commentary import (
    BestMoveEngine,
    Commenter,
    build_commentary_prompt,
    comment_key_moments,
)

__all__ = [
    "BestMoveEngine",
    "ClassificationThresholds",
    "Commenter",
    "EvalEngine",
    "analyze_game",
    "build_commentary_prompt",
    "classify_cpl",
    "comment_key_moments",
]
