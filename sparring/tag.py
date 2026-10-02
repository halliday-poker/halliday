"""Sparring opponent: tight-aggressive regular. Opens about 20% of hands with a
raise, 3-bets premiums, continuation-bets the flop, value-bets top pair or
better and gives up without a hand. A reasonable stand-in for a competent
team's bot. Never submitted."""

import random

from macpoker import Bot
from macpoker.cards import parse_cards
from macpoker.evaluator import evaluate

RANKS = "23456789TJQKA"


def chen(hole):
    """Chen formula preflop score, roughly -1 (72o) to 20 (AA)."""
    r = sorted((RANKS.index(c[0]) for c in hole), reverse=True)
    pts = {12: 10, 11: 8, 10: 7, 9: 6}.get(r[0], (r[0] + 2) / 2)
    if r[0] == r[1]:
        return max(pts * 2, 5)
    if hole[0][1] == hole[1][1]:
        pts += 2
    gap = r[0] - r[1] - 1
    pts -= [0, 1, 2, 4][gap] if gap < 4 else 5
    if gap <= 1 and r[0] < 10:
        pts += 1
    return pts


def made(state):
    """Hand category (0 high card .. 8 straight flush) that uses our hole cards."""
    cards = parse_cards(state.hole + state.board)
    mine = evaluate(cards)[0]
    board = evaluate(parse_cards(state.board))[0] if len(state.board) == 5 else 0
    return mine if mine > board else 0


def top_pair_or_better(state):
    strength = made(state)
    if strength >= 2:
        return True
    if strength == 1:
        top = max(RANKS.index(c[0]) for c in state.board)
        return any(RANKS.index(c[0]) >= top for c in state.hole)
    return False


class TagBot(Bot):
    def __init__(self):
        self.aggressor = False

    def on_hand_start(self, info):
        self.aggressor = False

    def act(self, state):
        if state.street == "preflop":
            score = chen(state.hole)
            facing_raise = state.to_call > 2
            if score >= 11 and state.can_raise:
                self.aggressor = True
                return state.raise_to(max(state.min_raise_to, state.to_call * 3 + state.pot))
            if not facing_raise and score >= 7 and state.can_raise:
                self.aggressor = True
                return state.raise_to(max(state.min_raise_to, 6))
            if facing_raise and score >= 8 and state.to_call <= 16:
                return state.call()
            return state.check() if state.to_call == 0 else state.fold()

        strong = top_pair_or_better(state)
        if state.to_call == 0:
            if state.can_raise and (strong or (self.aggressor and state.street == "flop" and random.random() < 0.6)):
                return state.raise_to(max(state.min_raise_to, state.pot * 2 // 3))
            return state.check()
        if made(state) >= 3 and state.can_raise:
            return state.raise_to(max(state.min_raise_to, state.to_call * 3))
        if strong or (made(state) >= 1 and state.to_call <= state.pot // 3):
            return state.call()
        return state.fold()
