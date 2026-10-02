Get started

# Installation

Install the macpoker SDK, grab the scaffold and see exactly what the tournament sandbox runs.

## Requirements

Python 3.10 or newer. The SDK has no dependencies.

## Install the SDK

``` sh
pip install https://poker.monashcoding.com/dl/macpoker-0.1.0-py3-none-any.whl
```

Terminal window

A virtual environment is a good idea:

``` sh
python -m venv .venv
source .venv/bin/activate        # windows: .venv\Scripts\activate
pip install https://poker.monashcoding.com/dl/macpoker-0.1.0-py3-none-any.whl
```

Terminal window

Check it works:

``` sh
macpoker play house:call house:random --deals 10
```

Terminal window

## The scaffold

The quickest start is the [scaffold zip](https://poker.monashcoding.com/dl/macpoker-scaffold.zip): a folder with a working `main.py` and a README. Edit, test, zip, upload.

## What runs in the tournament

Your bot runs inside a sandbox with:

- Python 3.12
- the `macpoker` SDK
- `numpy`
- the Python standard library
- **no network access**, no other packages, no GPU

If your bot imports anything outside that list, it will fail validation.

| Limit      | Value                                                |
|------------|------------------------------------------------------|
| CPU        | 1 core                                               |
| Memory     | 512 MB                                               |
| Filesystem | read-only, plus a 64 MB `/tmp` wiped after each game |
| Submission | zip up to 20 MB unpacked, at most 300 files          |
| Clock      | 30 s time bank per game, plus 0.1 s per hand         |

[Previous  
Quickstart](/quickstart/)[Next  
Writing a bot](/writing-a-bot/)

Stuck on something?

Ask in the hackathon Discord. Mentors and the organisers are in there all weekend.

[Join the Discord](https://discord.gg/kkv2hJyzGp)

Monash Association of Coding[poker.monashcoding.com](https://poker.monashcoding.com)
