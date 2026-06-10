"""Тесты аннотационных глифов классификации (chess.com-стиль: ! !! ? ?? ?!)."""

from __future__ import annotations

import typing

from arena.analysis import CLASSIFICATION_GLYPHS, classification_glyph
from arena.models import Classification


def test_glyph_for_each_class():
    assert classification_glyph("brilliant") == "!!"
    assert classification_glyph("good") == "!"
    assert classification_glyph("inaccuracy") == "?!"
    assert classification_glyph("mistake") == "?"
    assert classification_glyph("blunder") == "??"
    assert classification_glyph("book") == ""


def test_glyph_none_and_unknown_are_empty():
    assert classification_glyph(None) == ""
    assert classification_glyph("nonsense") == ""  # type: ignore[arg-type]


def test_glyph_map_covers_all_classification_values():
    classes = set(typing.get_args(Classification))
    assert set(CLASSIFICATION_GLYPHS) == classes
