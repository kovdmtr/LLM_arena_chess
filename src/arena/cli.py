"""Служебная точка входа для прогона партии из терминала.

Полноценная реализация переиспользует ``GameRunner`` и появится в Phase 3+.
Пока это заглушка, чтобы пакет был устанавливаемым (см. ``[project.scripts]``).
"""

from __future__ import annotations


def main() -> None:
    """Точка входа консольного скрипта ``arena``."""
    raise SystemExit("arena CLI ещё не реализован (см. docs/TODO.md, Phase 3).")


if __name__ == "__main__":
    main()
