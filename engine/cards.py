from __future__ import annotations
import random
from treys import Card as TreysCard

RANKS = "23456789TJQKA"
SUITS = "hdcs"

ALL_CARDS: list[int] = [TreysCard.new(r + s) for r in RANKS for s in SUITS]


def parse_card(s: str) -> int:
    """'As', '2h', 'Td' → treys int representation."""
    s = s.strip()
    if len(s) != 2:
        raise ValueError(f"Invalid card: '{s}'. Use format like 'As', '2h', 'Td'.")
    rank, suit = s[0].upper(), s[1].lower()
    if rank not in RANKS:
        raise ValueError(f"Invalid rank '{rank}'. Valid: {RANKS}")
    if suit not in SUITS:
        raise ValueError(f"Invalid suit '{suit}'. Valid: {SUITS} (h=hearts, d=diamonds, c=clubs, s=spades)")
    return TreysCard.new(rank + suit)


def card_str(c: int) -> str:
    """treys int → 'As', '2h'."""
    return TreysCard.int_to_str(c)


def parse_cards(s: str) -> list[int]:
    """Parse space-separated cards: 'As Kd Qh' → list of ints."""
    s = s.strip()
    if not s:
        return []
    return [parse_card(tok) for tok in s.split()]


class Deck:
    def __init__(self, exclude: list[int] | None = None):
        excluded = set(exclude or [])
        self._cards = [c for c in ALL_CARDS if c not in excluded]
        random.shuffle(self._cards)

    def deal(self, n: int) -> list[int]:
        if n > len(self._cards):
            raise ValueError(f"Cannot deal {n} cards, only {len(self._cards)} remaining.")
        cards, self._cards = self._cards[:n], self._cards[n:]
        return cards

    def __len__(self) -> int:
        return len(self._cards)
