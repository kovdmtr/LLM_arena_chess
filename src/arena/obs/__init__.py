"""Наблюдаемость: структурное логирование с маскированием секретов (Phase 7)."""

from arena.obs.log import (
    ROOT_NAME,
    StructuredFormatter,
    clear_secrets,
    configure_logging,
    get_logger,
    redact,
    register_secret,
    register_secrets,
)

__all__ = [
    "ROOT_NAME",
    "StructuredFormatter",
    "clear_secrets",
    "configure_logging",
    "get_logger",
    "redact",
    "register_secret",
    "register_secrets",
]
