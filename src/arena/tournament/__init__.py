"""★ Турниры из нескольких партий (round-robin), опц. (Phase 8, бэклог-1)."""

from arena.tournament.models import TournamentGame, TournamentRecord
from arena.tournament.pairings import new_tournament_record, round_robin

__all__ = [
    "TournamentGame",
    "TournamentRecord",
    "new_tournament_record",
    "round_robin",
]
