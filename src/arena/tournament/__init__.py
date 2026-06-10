"""★ Турниры из нескольких партий (round-robin), опц. (Phase 8, бэклог-1)."""

from arena.tournament.models import TournamentGame, TournamentRecord
from arena.tournament.pairings import new_tournament_record, round_robin
from arena.tournament.runner import (
    TournamentOutcome,
    TournamentRunner,
    export_tournament,
)

__all__ = [
    "TournamentGame",
    "TournamentOutcome",
    "TournamentRecord",
    "TournamentRunner",
    "export_tournament",
    "new_tournament_record",
    "round_robin",
]
