"""Strategy settings. Values never change during a game; this game's
opponent counters only decide whether the shover/station rules apply."""

from types import MappingProxyType


DEFAULT_PARAMS = MappingProxyType({
    "big_blind": 2,
    "open_bb": 2.5,
    "limper_bb": 1.0,
    "threebet_ip": 3.0,
    "threebet_oop": 4.0,
    "fourbet_multiplier": 2.3,
    "max_open_call_bb": 6,
    "max_threebet_call_bb": 16,
    "large_bet_bb": 15,
    "preflop_call_margin": 0.06,
    "value_threshold": 0.64,
    "multiway_value_margin": 0.04,
    "raise_threshold": 0.85,
    "multiway_raise_margin": 0.02,
    "call_margin_flop": 0.07,
    "call_margin_turn": 0.06,
    "call_margin_river": 0.04,
    "multiway_call_margin": 0.02,
    "large_bet_margin": 0.08,
    "reraise_margin": 0.08,
    "size_dry": 0.40,
    "size_wet": 0.67,
    "raise_pot_fraction": 0.75,
    "cbet_equity": 0.50,
    # Field exploits (bot/FIELD_EXPLOITS.md). Ladder bots fold ~74% to a
    # pot-sized heads-up flop c-bet and c-bet ~56% air themselves.
    "cbet_pot_fraction": 1.0,
    "cbet_defence_margin": 0.02,
    "shover_min_hands": 8,
    "shover_min_shoves": 3,
    "shover_min_rate": 0.25,
    "shover_call_margin": 0.03,
    "station_min_faced": 8,
    "station_max_fold": 0.15,
    "station_max_raise": 0.05,
    # Per-opponent aggression: estimated fold rate to our bets, starting
    # from the field's and updated by this game's responses. A pot-sized
    # bluff needs about half the bets to win the pot.
    "bluff_fold_prior": 0.70,
    "bluff_prior_weight": 4,
    "bluff_min_fold": 0.50,
    "bluff_frequency": 1.0,
    "shove_equity": 0.90,
    "shove_spr": 1.0,
    "equity_iters": 768,
    "equity_budget_ms": 35,
    "equity_min_samples": 128,
    "low_clock_ms": 5000,
    "low_clock_iters": 192,
    "low_clock_budget_ms": 10,
    "skip_equity_clock_ms": 250,
})
