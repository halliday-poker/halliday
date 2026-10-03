"""Strategy settings. Values never change during a game; this game's
opponent counters decide whether the shover/station rules apply and how
wide ranges.py assumes each player's ranges are."""

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
    # pot-sized heads-up flop c-bet and c-bet ~44% air themselves.
    "cbet_pot_fraction": 1.0,
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
    # Fold rate to anyone's postflop bets, prior 0.55: players under 0.35
    # after 6 bets fold only ~38% later in the game, so bluffs lose.
    "bluff_any_prior": 0.55,
    "bluff_any_min_faced": 6,
    "bluff_min_fold_any": 0.35,
    # Bluff turn/river when we did not bet the previous street.
    "stab": True,
    # Turn barrel after a called heads-up flop c-bet (FIELD_EXPLOITS.md).
    "turn_barrel": True,
    # Size of every heads-up turn/river bet: value, barrels and stabs.
    "late_pot_fraction": 1.0,
    "barrel_bluffs": True,
    "barrel_weak_pairs": False,
    "shove_equity": 0.90,
    "shove_spr": 1.0,
    "equity_iters": 768,
    "equity_budget_ms": 35,
    "equity_min_samples": 128,
    "low_clock_ms": 5000,
    "low_clock_iters": 192,
    "low_clock_budget_ms": 10,
    "skip_equity_clock_ms": 250,

    # --- Range tracking (ranges.py, RANGES.md) ---
    # Switches: track ranges at all; use them when 2+ opponents are in the
    # pot; learn per-player cutoffs from this game's showdowns.
    "range_enabled": True,
    "range_multiway": True,
    "range_learn_showdowns": True,
    # Field priors for preflop widths (share of hands played / raised /
    # 3-bet per chance), worth range_prior_hands hands of this game's counts.
    "range_prior_vpip": 0.35,
    "range_prior_pfr": 0.20,
    "range_prior_threebet": 0.08,
    "range_prior_hands": 12,
    # How hard each action narrows a range. temper is an exponent on every
    # likelihood: 1 = full Bayesian update, 0 = actions change nothing.
    # floor is the least likely any combo becomes per action, so the true
    # hand never vanishes. Softness is the width of each cutoff's ramp:
    # larger = gentler, smaller = sharper. Preflop it is a share of the
    # range's width (0.25 = a quarter of it); postflop it is in strength units.
    "range_temper": 0.8,
    "range_floor": 0.03,
    "range_preflop_softness": 0.25,
    "range_postflop_softness": 0.08,
    # Each further preflop re-raise range is this share of the previous one.
    "range_4bet_ratio": 0.5,
    # Share of strong hands that check or just call instead of raising.
    # 0.5: a check caps a range only mildly (checks compound across streets).
    "range_slowplay": 0.25,
    # Postflop priors before showdowns: strength (share of combos beaten,
    # 1 = nuts) where betting and calling become likely; raises over a bet
    # need range_raise_shift more; each extra half-pot of size adds
    # range_size_slope / 2. Draws count as range_draw_bonus stronger.
    "range_bet_cut": 0.60,
    "range_call_cut": 0.35,
    # Per-player cutoffs from frequencies: betting when checked to sets
    # bet_cut = 1 - bet rate, continuing vs bets sets call_cut = 1 - continue
    # rate; the field cutoffs above count as range_frequency_weight chances.
    # Showdowns then refine these instead of the field cutoffs. Off: with
    # the river factors above it tested worse vs aggressive pools (EV.md).
    "range_frequency_cuts": False,
    "range_frequency_weight": 10,
    "range_raise_shift": 0.15,
    "range_size_slope": 0.15,
    "range_draw_bonus": 0.20,
    # Prior: hands below the betting cutoff bet range_bluff_floor times as
    # often as hands above it. Ladder bettors are 44% air on flop c-bets but
    # 12-15% on big turn/river bets; replaying real river calls, 0.3 lifts
    # call EV from +0.19 to +0.36 pot (both halves). Showdowns update it.
    "range_bluff_floor": 0.30,
    # Optional extra scaling of the floor on later streets, as a share of the
    # flop's. Lower values read big late bets as stronger; ~0.7 / 0.35 with
    # range_slowplay 0.5 lost to the sparring pools' river bluffs (EV.md).
    "range_bluff_turn_factor": 1.0,
    "range_bluff_river_factor": 1.0,
    # Showdown learning: the priors above are worth range_showdown_prior
    # shown samples. A shown bet whose call ended the hand counts fully;
    # earlier bets that survived later streets count `indirect`, shown calls
    # count `passive` (both are biased samples: winning bluffs and folded
    # hands are never shown).
    "range_showdown_prior": 6,
    "range_showdown_weight_indirect": 0.5,
    "range_showdown_weight_passive": 0.4,
    # Engine input: keep the heaviest combos only, and pass a range as
    # random cards when its effective share of combos is above this.
    "range_max_combos": 400,
    "range_uniform_skip": 0.90,
    # Margins used instead of the random-card ones when equity came from
    # tracked ranges; the originals compensate for random-card equity.
    "range_call_margin_flop": 0.03,
    "range_call_margin_turn": 0.03,
    "range_call_margin_river": 0.02,
    "range_large_bet_margin": 0.02,
    "range_reraise_margin": 0.03,
    "range_preflop_call_margin": 0.03,

    # --- EV action selection (ev.py, EV.md): postflop only ---
    # Off by default: it wins chips from passive callers but tested worse
    # than the rule chain against aggressive and drifting pools (EV.md).
    # When on, the rules still take over beyond ev_max_opponents live
    # opponents, on a low clock, or if a spot fails.
    "ev_enabled": False,
    "ev_max_opponents": 3,
    # Candidate sizes as fractions of the pot after calling, plus all in.
    "ev_bet_sizes": (0.33, 0.66, 1.0),
    "ev_raise_sizes": (0.75, 1.25),
    # How opponents respond to our bets: each combo keeps playing with a
    # chance from floor to ceiling, crossing halfway at strength cut (share
    # of combos beaten, 1 = nuts) over a ramp of width softness. Bigger bets
    # and raises move the cut up (range_size_slope per pot, range_raise_shift)
    # to at most cut_max; above pot size the floor shrinks in proportion.
    # Bets we make out of position are called wider by oop_continue_shift.
    # The defaults follow the field: ~3/4 fold to an in-position pot c-bet,
    # air folds ~3/4, top pair ~1/6.
    "ev_continue_floor": 0.20,
    "ev_continue_ceiling": 0.92,
    "ev_continue_cut": 0.62,
    "ev_continue_cut_max": 0.95,
    "ev_continue_softness": 0.10,
    "ev_oop_continue_shift": 0.15,
    # The modelled fold rate counts as this many of our bets; this game's
    # actual folds to our bets pull it toward the truth. The same weight
    # pulls each opponent's re-raise rate (share of its continues that are
    # raises) from ev_raise_prior toward its actual rate this game.
    "ev_fold_evidence": 6,
    "ev_raise_prior": 0.10,
    # A re-raise is assumed to go to this multiple of our bet.
    "ev_reraise_multiple": 3.0,
    # Share of showdown equity we keep when acting first.
    "ev_realize_oop": 0.92,
    # Extra EV (x pot) a bet needs over checking/calling, and a call over
    # folding, to cover what the model ignores (re-raises, later streets).
    "ev_bet_margin": 0.03,
    "ev_call_margin": 0.0,
    # Bet sizes within this much EV (x pot) of the best count as equal; the
    # smallest wins, so model error is risked with the fewest chips.
    "ev_size_tolerance": 0.02,
    # All in is a candidate only when our stack is at most this x the pot.
    "ev_allin_spr": 3.0,
    # Compute: combos per opponent, flop runouts sampled, time budget and
    # the fewest runouts worth trusting.
    "ev_max_combos": 300,
    "ev_flop_runouts": 40,
    "ev_time_budget_ms": 60,
    "ev_min_runouts": 8,
})


def margin(params, name, ranged):
    """The range-mode version of a margin when equity came from tracked ranges."""
    return params.get("range_" + name, params[name]) if ranged else params[name]
