"""Sparring opponent: the calling station. Limps and calls preflop with most
hands, calls down with any pair, and only raises with very strong hands.
Exploit: never bluff it, value-bet thin and big. Never submitted."""

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


class StationBot(Bot):
    def act(self, state):
        if state.street == "preflop":
            score = chen(state.hole)
            if score >= 12 and state.can_raise:
                return state.raise_to(state.min_raise_to)
            if score >= 3 and state.to_call <= 30:
                return state.call() if state.to_call else state.check()
            return state.check() if state.to_call == 0 else state.fold()

        strength = made(state)
        if strength >= 3 and state.can_raise and random.random() < 0.5:
            return state.raise_to(state.min_raise_to)
        if strength >= 1:
            return state.call() if state.to_call else state.check()
        # high card: floats small bets on the flop, gives up later
        if state.street == "flop" and state.to_call <= state.pot // 2:
            return state.call() if state.to_call else state.check()
        return state.check() if state.to_call == 0 else state.fold()
