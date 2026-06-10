"""★ Self-contained HTML-таблица агрегированной статистики (Phase 8, бэклог-2).

Производный артефакт из ``StatsTable`` (слой ``arena.stats``): standings-таблица —
строка на модель (партии, W/Н/П, очки, score%, средняя точность, счётчики ошибок,
подсказки). Внешних файлов и сети нет (инлайн-CSS), так что отчёт самодостаточен,
как и отчёт партии. Запись в файл — задача ``storage.export_stats_report``.
"""

from __future__ import annotations

from arena.report.template import _ENV
from arena.stats import StatsTable

# Имя шаблона таблицы статистики внутри ``templates/``.
_TEMPLATE_NAME = "stats.html.j2"


def render_stats_html(
    table: StatsTable, *, title: str = "Статистика моделей"
) -> str:
    """Собрать строку HTML standings-таблицы из ``table``.

    Строки идут в порядке ``table.models`` (агрегатор уже отсортировал по очкам);
    ранг — это позиция в списке. Пустая таблица рендерит заглушку «нет данных».
    """
    template = _ENV.get_template(_TEMPLATE_NAME)
    return template.render(table=table, title=title)
