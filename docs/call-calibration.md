# Call corrections from the newest-opponent study

The prior audit identified missed terminal preflop calls, river calls with
overoptimistic equity, and a full-house fold after a timed estimate fell below
the usual 128-sample minimum. This feature evaluates targeted corrections on
newly fitted opponent replicas, keeping ordinary opening ranges unchanged.

* `terminal_range_calls`: allow tracked-range equity to justify a preflop
  call outside QQ+/AK when the public action history shows that calling ends
  all betting. Keep the existing margin and random-card safeguards.
* `partial_terminal_equity`: for 32–127 Monte Carlo samples, use the lower
  bound `equity - sqrt(log(n*(n+1)/alpha)/(2*n))`, clipped at zero, with
  `alpha=0.01`. The per-count error allocations sum to at most alpha, so the
  bound is conservative across possible stopping counts. It addresses sampling
  uncertainty conditional on the ranges; it does not correct range-model bias.
  This fallback may call but never raise, and does not apply when later betting
  remains possible.
* `range_call_margin_river`: the selected pilot variant increases the margin
  from 0.02 to 0.06. The separate final comparison measures its combined effect
  with the core fixes. It does not identify the causal contribution of each fix.

All inference in the submitted bot uses public game state, its own cards and
per-game opponent counters. Replica training and GPU evaluation are offline
tools. The optional engine batch hook leaves ordinary CPU execution intact.

See the [comparison report](../analysis/reports/call-calibration-20261004.md)
and [reproduction commands](../analysis/reports/call-calibration-20261004-reproduce.md).
