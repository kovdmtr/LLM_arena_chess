"""Прицельные тесты порогов классификации ходов (★, D-009).

В отличие от ``test_analysis_analyzer`` (поведение `analyze_game` целиком), здесь
проверяется чистая граница `classify_cpl` по cpl, согласованность и валидация
`ClassificationThresholds` (возрастание порогов, `from_config`) и их связь с
несекретным конфигом `config.AnalysisConfig` (значения по умолчанию из `config.yaml`).
"""

from __future__ import annotations

import pytest

from arena.analysis import ClassificationThresholds, classify_cpl
from arena.config.settings import AnalysisConfig, AppConfig

# Стандартные пороги для границ: good 20, inaccuracy 50, mistake 120, blunder 300.
T = ClassificationThresholds(
    good_cp=20, inaccuracy_cp=50, mistake_cp=120, blunder_cp=300
)


# --- границы classify_cpl ----------------------------------------------------

@pytest.mark.parametrize(
    "cpl, expected",
    [
        (0, "good"),
        (20, "good"),         # ровно порог хорошего хода
        (21, "normal"),       # на 1 выше → просто ход
        (49, "normal"),       # на 1 ниже порога неточности
        (50, "inaccuracy"),   # ровно порог неточности
        (119, "inaccuracy"),  # на 1 ниже порога ошибки
        (120, "mistake"),     # ровно порог ошибки
        (299, "mistake"),     # на 1 ниже порога зевка
        (300, "blunder"),     # ровно порог зевка
        (5000, "blunder"),    # большой cpl (потеря ферзя и т.п.)
    ],
)
def test_classify_cpl_boundaries(cpl, expected):
    assert classify_cpl(cpl, T) == expected


def test_negative_cpl_is_clamped_to_good():
    # Отрицательный cpl (шум поиска) приравнивается к нулю → good.
    assert classify_cpl(-1, T) == "good"
    assert classify_cpl(-1000, T) == "good"


def test_classify_cpl_never_returns_heuristic_classes():
    # classify_cpl даёт только градиентные классы; brilliant/interesting/book — отдельно.
    produced = {classify_cpl(cpl, T) for cpl in range(0, 1000, 7)}
    assert produced <= {"good", "normal", "inaccuracy", "mistake", "blunder"}
    assert "brilliant" not in produced
    assert "interesting" not in produced
    assert "book" not in produced


def test_custom_thresholds_change_classification():
    # Пороги конфигурируемы (D-009): тот же cpl при строгих порогах — другой класс.
    strict = ClassificationThresholds(
        good_cp=10, inaccuracy_cp=20, mistake_cp=40, blunder_cp=80
    )
    assert classify_cpl(30, T) == "normal"           # при стандартных — просто ход
    assert classify_cpl(30, strict) == "inaccuracy"  # при строгих — неточность
    assert classify_cpl(100, strict) == "blunder"


def test_equal_thresholds_are_allowed_and_skip_middle_class():
    # Совпадающие границы (mistake==blunder) допустимы: класс «ошибка» «схлопывается».
    collapsed = ClassificationThresholds(
        inaccuracy_cp=50, mistake_cp=200, blunder_cp=200
    )
    assert classify_cpl(199, collapsed) == "inaccuracy"
    assert classify_cpl(200, collapsed) == "blunder"  # mistake-диапазон пуст


# --- валидация порогов -------------------------------------------------------

def test_thresholds_must_be_non_decreasing():
    with pytest.raises(ValueError, match="должны возрастать"):
        ClassificationThresholds(inaccuracy_cp=120, mistake_cp=50, blunder_cp=300)
    with pytest.raises(ValueError, match="должны возрастать"):
        ClassificationThresholds(inaccuracy_cp=50, mistake_cp=300, blunder_cp=120)


def test_negative_threshold_rejected():
    with pytest.raises(ValueError):
        ClassificationThresholds(inaccuracy_cp=-1, mistake_cp=120, blunder_cp=300)


def test_default_thresholds_match_documented_values():
    d = ClassificationThresholds()
    assert (d.good_cp, d.inaccuracy_cp, d.mistake_cp, d.blunder_cp) == (20, 50, 120, 300)
    assert (d.brilliant_max_cpl, d.brilliant_min_eval_cp) == (10, 100)


def test_good_cp_must_not_exceed_inaccuracy():
    with pytest.raises(ValueError, match="должны возрастать"):
        ClassificationThresholds(good_cp=60, inaccuracy_cp=50)


# --- согласование с конфигом -------------------------------------------------

def test_from_config_reads_analysis_config():
    cfg = AnalysisConfig(
        inaccuracy_cp=40, mistake_cp=90, blunder_cp=250,
        brilliant_max_cpl=5, brilliant_min_eval_cp=150,
    )
    t = ClassificationThresholds.from_config(cfg)
    assert t == ClassificationThresholds(
        inaccuracy_cp=40, mistake_cp=90, blunder_cp=250,
        brilliant_max_cpl=5, brilliant_min_eval_cp=150,
    )
    # пороги из конфига действительно влияют на классификацию.
    assert classify_cpl(40, t) == "inaccuracy"
    assert classify_cpl(250, t) == "blunder"


def test_default_config_yaml_carries_analysis_thresholds():
    # Дефолтный config.yaml несёт секцию analysis с теми же значениями по умолчанию.
    config = AppConfig.from_yaml()
    assert config.analysis.enabled is True
    t = ClassificationThresholds.from_config(config.analysis)
    assert t == ClassificationThresholds()


def test_from_config_propagates_invalid_thresholds():
    # Несогласованные пороги в конфиге не проходят и через from_config.
    bad = AnalysisConfig(inaccuracy_cp=300, mistake_cp=120, blunder_cp=50)
    with pytest.raises(ValueError, match="должны возрастать"):
        ClassificationThresholds.from_config(bad)
