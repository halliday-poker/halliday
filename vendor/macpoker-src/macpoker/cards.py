"""Card representation: a card is an int 0..51, rank = card % 13 (0 = deuce,
12 = ace), suit = card // 13 (clubs, diamonds, hearts, spades)."""

from __future__ import annotations

import random

RANKS = "23456789TJQKA"
SUITS = "cdhs"


def card_rank(card: int) -> int:
    return card % 13


def card_suit(card: int) -> int:
    return card // 13


def card_str(card: int) -> str:
    return RANKS[card % 13] + SUITS[card // 13]


def parse_card(s: str) -> int:
    s = s.strip()
    if len(s) != 2:
        raise ValueError(f"bad card {s!r}")
    rank = RANKS.index(s[0].upper())
    suit = SUITS.index(s[1].lower())
    return suit * 13 + rank


def cards_str(cards: list[int]) -> list[str]:
    return [card_str(c) for c in cards]


def parse_cards(strs: list[str]) -> list[int]:
    return [parse_card(s) for s in strs]


def new_deck() -> list[int]:
    return list(range(52))


def shuffled_deck(rng: random.Random) -> list[int]:
    deck = new_deck()
    rng.shuffle(deck)
    return deck
