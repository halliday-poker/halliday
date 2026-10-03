# Fitted competitors

The completed 400-table Halliday evaluation is recorded in [EVALUATION.md](EVALUATION.md).

The 67 bots derived from the analysis live in `from_data/`, alongside their
profile manifest and pool files. `build.py` and these documents remain here.

These bots use `../param.py` with the exact `surrogate_style` from each
identity's most recent collection-time segment. `from_data/profiles.json` preserves the
selected segments, parameter uncertainties, observed statistics, residuals,
match IDs, and analysis/input hashes. No replay cards or analysis dependencies
are loaded during play.

Each generated `.py` file is an ordinary harness/SDK opponent. The shared
`from_data/competitor_base.py` loads the existing ParamBot scaffold relative to its own
location. Counters, style dictionaries and random generators are fresh per game.
The harness passes its seat seed through `make_seeded_bot(seed)` for repeatable
decisions independent of other bots' constructors.

`from_data/pool.txt` gives each of the 66 external identities equal weight. The updated
`bot/` replaces the historical Halliday fit for evaluation. `from_data/all.txt` includes
all 67 fitted identities, including `from_data/halliday.py`, for other experiments.
Collection frequency is not a tournament sampling weight. Historical names
remain separate identities because the analysis cannot resolve renames.

From the repository root:

```sh
python sparring/competitors/build.py analysis/results/opponent-estimates.json
python harness/eval.py run bot --no-league --pool sparring/competitors/from_data/pool.txt --tables 400 --deals 100 --sizes 4,5,5,6 --workers 8 --seed competitors-latest-20261003 --label latest-competitor-segments
```

The generator checks that `param.py` matches the scaffold fingerprint in the
analysis. It selects segments by their observed timestamps, even if the JSON
array is out of order. It preserves best fits and the report's executable
defaults for unobserved parameters; it does not convert null estimates into
measured zeros or sample independent confidence intervals as new styles.

These are surrogate opponents, not recovered source code. Sparse and
unidentified settings may have arbitrary equivalent fits, and observed rates
can differ from the scaffold's simulated rates. Check each profile's statuses
and residuals. The analysis used all 1,537 metadata matches; 13 extra action-log
matches without metadata were excluded from the audited snapshot.

The harness evaluates random duplicate tables with tournament game/round
scoring. It does not reproduce the tournament's four-round cumulative-score
regrouping or predict final standings. Results are written to the ignored
`harness/results/` directory. The fitted field stays in `sparring/` and is not
part of the submitted bot.
