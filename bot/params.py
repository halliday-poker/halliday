"""Strategy settings. Values never change during a game; this game's
opponent counters decide whether the shover/station rules apply and how
wide ranges.py assumes each player's ranges are."""

from types import MappingProxyType


DEFAULT_PARAMS = MappingProxyType({
    "big_blind": 2,
    "open_bb": 2.5,
    "limper_bb": 1.0,
    "threebet_ip": 2.5,
    "threebet_oop": 3.0,
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
    # --- Research upgrades (bot/RESEARCH.md). On: light 3-bets (safe
    # settings), open_wide + steal_wide, bb_defend_wide, call_vs_loose,
    # vs_light3. Off (no reliable gain): squeeze, iso_wide, station_value,
    # bluffcatch. threebet_ip/oop above were lowered to 2.5/3.0 for them. ---
    # Light 3-bets: 3-bet the top light3_range of hands (by equity vs a
    # random hand) against an opener whose fold-to-3-bet rate, pulled toward
    # light3_prior over light3_prior_weight chances, is at least
    # light3_min_fold (a 3x 3-bet risks ~15 to win ~8: break-even ~65%,
    # less with equity when called).
    "light3bet": True,
    "light3_range": 0.55,
    "light3_prior": 0.60,
    "light3_prior_weight": 4,
    "light3_min_fold": 0.65,
    # Use recency-weighted fold-to-3-bet evidence (old chances decay by
    # opponents.RECENT_DECAY each new chance), so changes are noticed fast.
    "light3_recent": True,
    # Squeeze: also light 3-bet when the opener has callers, with the range
    # cut to squeeze_share of light3_range, sized up by one per caller.
    "squeeze": False,
    "squeeze_share": 0.5,
    # Against a 3-bettor whose 3-bet rate (pulled toward vs_light3_prior over
    # vs_light3_prior_weight chances) is at least vs_light3_min_rate, call
    # and 4-bet wider ranges instead of folding most hands.
    "vs_light3": True,
    "vs_light3_prior": 0.08,
    "vs_light3_prior_weight": 10,
    "vs_light3_min_rate": 0.20,
    # Wider big blind defence against opens of at most 3bb (pot odds 3.5:1).
    "bb_defend_wide": True,
    # Wider steals: open the top steal_range from CO/BTN/SB when every player
    # still to act folds to steals at least steal_min_fold (prior-shrunk).
    "steal_wide": True,
    "steal_range": 0.60,
    "steal_prior": 0.55,
    "steal_prior_weight": 4,
    "steal_min_fold": 0.65,
    # Wider opens from any position: open the top open_wide_range when the
    # chance that every player still to act folds (product of their
    # fold-to-open rates, each pulled toward open_wide_prior) is at least
    # open_wide_min_all_fold. A 2.5bb open risks 5 to win 3.
    "open_wide": True,
    "open_wide_range": 0.50,
    "open_wide_prior": 0.75,
    "open_wide_prior_weight": 6,
    "open_wide_min_all_fold": 0.55,
    # Flat-call wider (top call_vs_loose_range) against an opener whose raise
    # rate, pulled toward the prior, is at least call_vs_loose_min_pfr.
    "call_vs_loose": True,
    "call_vs_loose_prior": 0.18,
    "call_vs_loose_prior_weight": 12,
    "call_vs_loose_min_pfr": 0.30,
    "call_vs_loose_range": 0.35,
    # Isolation: with limpers in and nobody raised, raise the top iso_range
    # of hands, iso_extra_bb bigger than a normal open over limpers.
    "iso_wide": False,
    "iso_range": 0.45,
    "iso_extra_bb": 1.0,
    # Value against stations: thinner (threshold lowered by delta) and bigger.
    "station_value": False,
    "station_value_delta": 0.10,
    "station_value_size": 0.90,
    # Bluff-catching: against a heads-up bettor who bets when not facing a
    # bet at least bluffcatch_min_rate of the time (pulled toward
    # bluffcatch_prior over bluffcatch_prior_weight chances), shrink the
    # call margin by bluffcatch_margin.
    "bluffcatch": False,
    "bluffcatch_prior": 0.40,
    "bluffcatch_prior_weight": 10,
    "bluffcatch_min_rate": 0.60,
    "bluffcatch_margin": 0.06,
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
    "range_slowplay": 0.25,
    # Postflop priors before showdowns: strength (share of combos beaten,
    # 1 = nuts) where betting and calling become likely; raises over a bet
    # need range_raise_shift more; each extra half-pot of size adds
    # range_size_slope / 2. Draws count as range_draw_bonus stronger.
    "range_bet_cut": 0.60,
    "range_call_cut": 0.35,
    "range_raise_shift": 0.15,
    "range_size_slope": 0.15,
    "range_draw_bonus": 0.20,
    # Prior: hands below the betting cutoff bet range_bluff_floor times as
    # often as hands above it. Ladder bettors are 44% air on flop c-bets but
    # 12-15% on big turn/river bets; replaying real river calls, 0.3 lifts
    # call EV from +0.19 to +0.36 pot (both halves). Showdowns update it.
    "range_bluff_floor": 0.30,
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
})


def margin(params, name, ranged):
    """The range-mode version of a margin when equity came from tracked ranges."""
    return params.get("range_" + name, params[name]) if ranged else params[name]
