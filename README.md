# MAC Poker Bot

Entry for the MAC Poker Bot Tournament. Submissions close **Sun 4 Oct 2026, 6pm AEST**.

## What's where

| Path | What it is |
|---|---|
| `bot/` | **The submission.** Zip this folder with `main.py` at the root and upload it at https://poker.monashcoding.com/app |
| `bot/main.py` | Your bot. It started as the scaffold's template bot |
| `bot/README.md` | The scaffold's own README: setup, testing, submission |
| `sparring/` | Local opponents for testing. These are never submitted |
| `sparring/template.py` | Untouched copy of the template bot (calls at pot odds under 0.3, otherwise checks or folds) |
| `sparring/{nit,station,maniac,tag}.py` | Stereotyped opponents for the harness pool |
| `harness/` | Evaluation harness: A/B bot versions over random tables. See [harness/README.md](harness/README.md) |
| `snapshots/` | Frozen versions of our bot (`v0` = the template), for A/B tests and as sparring opponents |
| `docs/` | Markdown snapshot of https://docs.poker.monashcoding.com, one file per page |
| `docs/writing-a-bot.md` | `state` fields, actions and observer hooks. Start here |
| `docs/game-format*.md` | Table format, clocks, duplicate deals, scoring |
| `docs/rules.md` | What's allowed (stdlib + numpy only, no network or AI at runtime) |
| `docs/local-testing.md` | `macpoker play` usage and flags |
| `vendor/macpoker-src/macpoker/` | Unpacked SDK source, the ground truth for engine behaviour |
| `vendor/macpoker-src/macpoker/hand.py` | The engine: betting, action coercion, showdowns |
| `vendor/macpoker-src/macpoker/bots/builtin.py` | House bots: `call`, `checkfold`, `allin`, `random` |
| `vendor/*.whl`, `vendor/*.zip` | Original SDK wheel and scaffold downloads |
| `.venv/` | Python 3.12 (same as the sandbox) with macpoker + numpy |

## Running locally

For comparing versions use the harness: `python harness/eval.py run snapshots/v0 bot`. Raw engine:

```sh
source .venv/bin/activate
macpoker play bot/main.py sparring/template.py house:call house:random --deals 100 --seed 1
macpoker play bot/main.py house:call --deals 100 --subprocess --history out.json   # before every upload
```

Each argument after `play` is one seat at the table.
