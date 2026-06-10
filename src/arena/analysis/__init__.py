"""★ Разметка качества ходов: centipawn loss, классификация (D-009) и LLM-комментарий."""

from arena.analysis.analyzer import EvalEngine, analyze_game
from arena.analysis.classify import (
    CLASSIFICATION_GLYPHS,
    ClassificationThresholds,
    classification_glyph,
    classify_cpl,
)
from arena.analysis.commentary import (
    BestMoveEngine,
    Commenter,
    build_commentary_prompt,
    comment_key_moments,
)

__all__ = [
    "BestMoveEngine",
    "CLASSIFICATION_GLYPHS",
    "ClassificationThresholds",
    "Commenter",
    "EvalEngine",
    "analyze_game",
    "build_commentary_prompt",
    "classification_glyph",
    "classify_cpl",
    "comment_key_moments",
]
