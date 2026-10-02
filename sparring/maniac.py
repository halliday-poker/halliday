"""Sparring opponent: the maniac. Raises half its hands preflop, bets the pot
whenever checked to, and re-raises often regardless of strength.
Exploit: call down lighter, let it bluff into strong hands. Never submitted."""

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


class ManiacBot(Bot):
    def act(self, state):
        pot_bet = state.pot + 2 * state.to_call
        if state.street == "preflop":
            score = chen(state.hole)
            if state.can_raise and (score >= 6 or random.random() < 0.25):
                return state.raise_to(max(state.min_raise_to, pot_bet))
            if state.to_call <= 20 or score >= 9:
                return state.call() if state.to_call else state.check()
            return state.fold()

        strength = made(state)
        if state.can_raise and (strength >= 1 or random.random() < 0.6):
            return state.raise_to(max(state.min_raise_to, pot_bet))
        if state.to_call == 0:
            return state.check()
        if strength >= 1 or state.to_call <= state.pot // 2:
            return state.call()
        return state.fold()
