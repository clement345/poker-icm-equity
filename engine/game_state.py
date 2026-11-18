from __future__ import annotations
from dataclasses import dataclass, field
from .icm import TournamentInfo

VALID_STREETS = ("preflop", "flop", "turn", "river")
VALID_POSITIONS = ("BTN", "SB", "BB", "UTG", "UTG+1", "MP", "HJ", "CO")


@dataclass
class GameState:
    hole_cards: list[int]
    board: list[int]
    street: str
    num_players: int
    position: str
    hero_stack: float          # en BBs
    villain_stacks: list[float]
    pot: float                 # en BBs
    to_call: float             # en BBs
    # Tournament info (None = cash game, pas d'ICM)
    tournament: TournamentInfo | None = None
    # Payouts (fractions du prize pool, ex: [0.50, 0.30, 0.20])
    payouts: list[float] = field(default_factory=list)
    bet_sizes: list[float] = field(default_factory=lambda: [0.5, 1.0, 2.0])

    def __post_init__(self) -> None:
        if self.street not in VALID_STREETS:
            raise ValueError(f"street must be one of {VALID_STREETS}")
        if len(self.hole_cards) != 2:
            raise ValueError("hero must have exactly 2 hole cards")
        expected = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}[self.street]
        if len(self.board) != expected:
            raise ValueError(
                f"Street '{self.street}' requires {expected} board cards, got {len(self.board)}"
            )
        if len(self.villain_stacks) != self.num_players - 1:
            raise ValueError(
                f"num_players={self.num_players} but got {len(self.villain_stacks)} villain stacks"
            )

    @property
    def num_villains(self) -> int:
        return self.num_players - 1

    @property
    def all_stacks(self) -> list[float]:
        return [self.hero_stack] + list(self.villain_stacks)

    @property
    def can_check(self) -> bool:
        return self.to_call == 0

    @property
    def in_the_money(self) -> bool:
        return self.tournament is not None and self.tournament.is_itm

    @property
    def pressure_weight(self) -> float:
        """ICM pressure weight [0, 1] from tournament state."""
        if self.tournament is None:
            return 0.0
        return self.tournament.pressure_weight
