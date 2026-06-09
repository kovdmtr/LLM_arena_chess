"""Глобальная настройка pytest.

Если в репозитории лежит локально установленный движок (``tools/bin``, например
скачанный пребилт Stockfish), добавляем эту папку в ``PATH`` **только на время
прогона тестов**. Это позволяет интеграционным тестам, которые ищут бинарник
через ``shutil.which("stockfish")``, найти комплектный движок — без изменения
системного окружения пользователя. Если папки нет, ничего не происходит и
такие тесты по-прежнему корректно пропускаются (skip if absent, D-008).
"""

from __future__ import annotations

import os
from pathlib import Path

_LOCAL_BIN = Path(__file__).resolve().parent / "tools" / "bin"

if _LOCAL_BIN.is_dir():
    _path = os.environ.get("PATH", "")
    if str(_LOCAL_BIN) not in _path.split(os.pathsep):
        os.environ["PATH"] = (
            f"{_LOCAL_BIN}{os.pathsep}{_path}" if _path else str(_LOCAL_BIN)
        )
