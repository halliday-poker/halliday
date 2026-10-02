Get started

# Quickstart

Install the SDK, write a bot, test it against the house and submit it, in about five minutes.

1.  **Install the SDK**

    ``` sh
    pip install https://poker.monashcoding.com/dl/macpoker-0.1.0-py3-none-any.whl
    ```

    Terminal window

    Or start from the [scaffold](https://poker.monashcoding.com/dl/macpoker-scaffold.zip), which contains a ready-to-run `main.py`.

2.  **Write a bot**

    ``` python
    from macpoker import Bot

    class MyBot(Bot):
        def act(self, state):
            if state.to_call == 0:
                return state.check()
            pot_odds = state.to_call / (state.pot + state.to_call)
            if pot_odds < 0.3:
                return state.call()
            return state.fold()
    ```

    main.py

    One `main.py`, one `Bot` subclass, one decision method. Everything your bot can see and do is on [`state`](/writing-a-bot/).

3.  **Test it**

    ``` sh
    macpoker play main.py house:call house:random --deals 50
    ```

    Terminal window

    Your bot plays three games of 50 hands against two house bots, once from each seat, and you get a chip count. See [testing locally](/local-testing/).

4.  **Submit it**

    Zip your folder with `main.py` at the root and upload it from the [app](https://poker.monashcoding.com/app). Each upload plays a validation game against the house; pick a passing upload as your **main** before the deadline. That is your tournament entry.

Iterate with a fixed seed

Add `--seed anything` while you tweak your bot. Same seed, same cards, so a change in chips is a change in your decisions.

[Previous  
Introduction](/)[Next  
Installation](/installation/)

Stuck on something?

Ask in the hackathon Discord. Mentors and the organisers are in there all weekend.

[Join the Discord](https://discord.gg/kkv2hJyzGp)

Monash Association of Coding[poker.monashcoding.com](https://poker.monashcoding.com)
