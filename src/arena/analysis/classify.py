"""★ Классификация качества хода по centipawn loss (D-009).

Centipawn loss (cpl) хода — насколько оценка позиции (с точки зрения **ходившей**
стороны) просела относительно лучшего хода движка. По cpl ход относится к одному
из градиентных классов по **конфигурируемым** порогам (D-009: универсально
«правильных» значений нет, поэтому они в конфиге):

- ``good`` (``!``) — cpl ≤ ``good_cp`` (лучший/почти лучший, сильный ход);
- ``normal`` — ``good_cp`` < cpl < ``inaccuracy_cp`` (просто ход, без улучшения/ухудшения);
- ``inaccuracy`` (``?!``) — cpl ≥ ``inaccuracy_cp`` (сомнительный ход);
- ``mistake`` (``?``) — cpl ≥ ``mistake_cp`` (ошибка);
- ``blunder`` (``??``) — cpl ≥ ``blunder_cp`` (грубейшая ошибка/зевок).

Классы ``brilliant`` (``!!``) и ``interesting`` (``!?``) — отдельные эвристики
(жертва материала, D-009), решаются в ``analyzer`` поверх позиции, а не по одному
cpl. ``book`` (дебютная теория) здесь не присваивается.
"""

from __future__ import annotations

from dataclasses import dataclass

from arena.models import Classification


@dataclass(frozen=True)
class ClassificationThresholds:
    """Пороги классификации (в сантипешках) + параметры эвристики «блестящий».

    ``good_cp``/``inaccuracy_cp``/``mistake_cp``/``blunder_cp`` — границы cpl для
    соответствующих классов (должны возрастать). ``good_cp`` отделяет «хороший» ход
    (``!``) от «просто хода» (``normal``). ``brilliant_max_cpl`` — верхняя граница
    cpl, при которой ход считается «лучшим» для эвристик блестящего/интересного;
    ``brilliant_min_eval_cp`` — минимальный перевес (POV ходившей стороны) после
    хода, при котором жертва признаётся блестящей (``!!``); жертва ниже этого порога,
    но не проигрышная — «интересная» (``!?``).
    """

    good_cp: int = 20
    inaccuracy_cp: int = 50
    mistake_cp: int = 120
    blunder_cp: int = 300
    brilliant_max_cpl: int = 10
    brilliant_min_eval_cp: int = 100

    def __post_init__(self) -> None:
        if not (
            0 <= self.good_cp <= self.inaccuracy_cp <= self.mistake_cp <= self.blunder_cp
        ):
            raise ValueError(
                "пороги cpl должны возрастать: "
                f"0 ≤ good_cp({self.good_cp}) ≤ inaccuracy_cp({self.inaccuracy_cp}) ≤ "
                f"mistake_cp({self.mistake_cp}) ≤ blunder_cp({self.blunder_cp})"
            )

    @classmethod
    def from_config(cls, analysis_config) -> "ClassificationThresholds":
        """Построить пороги из ``config.AnalysisConfig`` (или совместимого объекта)."""
        return cls(
            good_cp=analysis_config.good_cp,
            inaccuracy_cp=analysis_config.inaccuracy_cp,
            mistake_cp=analysis_config.mistake_cp,
            blunder_cp=analysis_config.blunder_cp,
            brilliant_max_cpl=analysis_config.brilliant_max_cpl,
            brilliant_min_eval_cp=analysis_config.brilliant_min_eval_cp,
        )


def classify_cpl(cpl: int, thresholds: ClassificationThresholds) -> Classification:
    """Классифицировать ход по его centipawn loss (D-009).

    ``cpl`` — потеря в сантипешках относительно лучшего хода (отрицательные значения,
    возможные из-за шума поиска, приравниваются к нулю). Возвращает градиентный класс
    (``good``/``normal``/``inaccuracy``/``mistake``/``blunder``); ``brilliant`` и
    ``interesting`` решаются отдельно.
    """
    cpl = max(0, cpl)
    if cpl >= thresholds.blunder_cp:
        return "blunder"
    if cpl >= thresholds.mistake_cp:
        return "mistake"
    if cpl >= thresholds.inaccuracy_cp:
        return "inaccuracy"
    if cpl <= thresholds.good_cp:
        return "good"
    return "normal"


# Аннотационные глифы в стиле chess.com/PGN-нотации для классов качества хода.
# ``normal`` (просто ход) и ``book`` (дебютная теория) глифом не помечаются (пустая
# строка) — они и есть «ход без улучшения или ухудшения».
CLASSIFICATION_GLYPHS: dict[Classification, str] = {
    "brilliant": "!!",
    "good": "!",
    "interesting": "!?",
    "inaccuracy": "?!",
    "mistake": "?",
    "blunder": "??",
    "normal": "",
    "book": "",
}


def classification_glyph(classification: Classification | None) -> str:
    """Вернуть аннотационный глиф класса (``!!``/``!``/``!?``/``?!``/``?``/``??``).

    ``None``, ``normal``, ``book`` и неизвестные значения дают пустую строку
    (глиф не рисуется).
    """
    if classification is None:
        return ""
    return CLASSIFICATION_GLYPHS.get(classification, "")
