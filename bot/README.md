# MAC poker bot: fixed baseline

A non-adaptive strategy built on the Person A equity engine.

## Setup

```
pip install https://poker.monashcoding.com/dl/macpoker-0.1.0-py3-none-any.whl
```

Python 3.10 or newer. The tournament sandbox runs Python 3.12 with the SDK
and numpy preinstalled. Nothing else is available at runtime.

## Develop

Edit `main.py`. Split logic into extra modules in this folder if you like;
`main.py` can import them.

Test against the house bots (`house:call`, `house:checkfold`, `house:allin`, `house:random`). Every argument after `play` is one seat at the table, so you can mix several of your own files and house bots:

```
macpoker play main.py house:call house:random --deals 50
macpoker play main.py house:call --deals 100 --subprocess --history out.json
```

## Opponent ranges

`ranges.py` tracks each opponent's range through the hand and learns from this
game's showdowns; equity is computed against those ranges. See
[RANGES.md](RANGES.md) for how it works, the tunable `range_*` parameters, and
validation results.

## Person A: equity engine

The agreed API is available in `engine.py`:

```python
from engine import equity

eq = equity(hole, board, opp_ranges, n_iters, time_budget_ms)
```

It returns expected showdown pot share against separate weighted opponent
ranges. Optional `estimate_equity` diagnostics include each player's hand
probabilities, win/tie/loss, sample counts and Monte Carlo error.

See [EQUITY_ENGINE.md](EQUITY_ENGINE.md) for the complete B/C handoff,
range format, deadlines, failure handling, integration example and testing.

`main.py` connects the engine to the fixed policy in `strategy.py` and
`preflop.py`. Settings live in `params.py`. See [BASELINE.md](BASELINE.md)
for the policy, modelling assumptions, clock behaviour and validation commands.

## Submit

Zip this folder with `main.py` at the root and upload it at
https://poker.monashcoding.com/app. Every upload plays a validation game
against the house; pick a passing upload as your **main** before the
deadline. That is your tournament entry.

## Rules that matter here

No network calls, no AI/LLM calls at runtime, standard library plus numpy
only. The sandbox has no internet and submissions are audited.

Questions: https://discord.gg/kkv2hJyzGp
Docs: https://docs.poker.monashcoding.com
