"""Strict replay reconstruction for the collector's normalized JSONL format."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path

import numpy as np

from sparring import param
from sparring.param import hand_percentile, strength

FIELDS = ("match", "street", "seat", "players", "pct", "strength", "draw",
          "facing", "can_raise", "pre_raises", "cbet", "action", "amount",
          "pot", "minimum", "maximum", "call", "stack", "top", "bet",
          "agg_high", "fold_high", "fold_low", "hand")
COL = {name: i for i, name in enumerate(FIELDS)}
STREETS = {"preflop": 0, "flop": 1, "turn": 2, "river": 3}
ACTIONS = {"fold": 0, "check": 1, "call": 2, "raise": 3}


@dataclass
class Dataset:
    matches: list[dict]
    observations: dict[str, np.ndarray]
    hands: dict[str, dict[int, list[int]]]
    audit: dict


@lru_cache(maxsize=100_000)
def _strength(hole, board):
    # Use the actual surrogate's heuristic, not a different notion of equity.
    return strength(list(hole), list(board))


def read_metadata(matches_path, state_path):
    matches_bytes, state_bytes = Path(matches_path).read_bytes(), Path(state_path).read_bytes()
    matches, state = json.loads(matches_bytes), json.loads(state_bytes)
    if not isinstance(matches, list) or not isinstance(state.get("collected"), dict):
        raise ValueError("Expected matches.json list and state.json collected mapping")
    found, audit = {}, Counter()
    for item in matches:
        mid = item["id"]
        if mid in found:
            raise ValueError(f"Duplicate match id {mid}")
        meta = state["collected"].get(mid)
        if not meta or meta.get("status") != "collected":
            audit["metadata_matches_without_collected_state"] += 1
            continue
        timestamp = meta.get("collected_at")
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or not isfinite(timestamp):
            raise ValueError(f"Missing/invalid collected_at for {mid}")
        names = item.get("names")
        if not names or len(set(names)) != len(names) or not 2 <= len(names) <= 9:
            raise ValueError(f"Missing or ambiguous bot names for {mid}")
        if item.get("collected_at") is not None and abs(item["collected_at"] - timestamp) > 1e-6:
            audit["timestamp_disagreements_state_used"] += 1
        found[mid] = dict(id=mid, collected_at=float(timestamp), names=names,
                          kind=item.get("kind", "unknown"), source=meta.get("source"))
    rows = sorted(found.values(), key=lambda x: (x["collected_at"], x["id"]))
    audit.update({"metadata_matches": len(rows)})
    hashes = {"matches_sha256": sha256(matches_bytes).hexdigest(),
              "state_sha256": sha256(state_bytes).hexdigest()}
    return rows, dict(audit) | hashes


def reconstruct_hand(events, metadata, match_index, stats, *, stack=200, sb=1, bb=2):
    """Return observations and per-bot hand outcomes; update public match stats.

    Collector rows store pot AFTER the action. Button is physical seat zero
    in this tournament. Identify the per-hand seat rotation from actual rows,
    never from hole-dict insertion order or a bot name's sort order.
    """
    names, n = metadata["names"], len(metadata["names"])
    actions = [e for e in events if "action" in e]
    if not actions or events[-1].get("event") != "hand_end":
        raise ValueError("Incomplete hand: action rows and final hand_end are required")
    first = actions[0]
    shift = (first["seat"] - names.index(first["bot"])) % n
    seats = [names[(seat - shift) % n] for seat in range(n)]
    if any(seats[e["seat"]] != e["bot"] for e in actions):
        raise ValueError("Inconsistent seat-to-bot mapping")
    stacks, bets, folded, reopen = [stack] * n, [0] * n, [False] * n, [True] * n
    for seat, blind in ((0 if n == 2 else 1, sb), (1 if n == 2 else 2, bb)):
        bets[seat] = min(blind, stacks[seat])
        stacks[seat] -= bets[seat]
    pot, current, increment, street = sum(bets), max(bets), bb, 0
    board, acted, pre_raises, street_raises, pre_aggressor = [], set(), 0, 0, None
    hand_metrics = {name: [1, 0, 0] for name in seats}  # dealt, VPIP, PFR
    result = []
    for event in events:
        if event.get("event") == "board":
            new_street = STREETS[event["street"]]
            new_board = event["board"]
            if new_street <= street or len(new_board) != {1: 3, 2: 4, 3: 5}[new_street] or new_board[:len(board)] != board:
                raise ValueError("Invalid board/street progression")
            board, street = list(new_board), new_street
            bets, current, increment, reopen, acted, street_raises = [0] * n, 0, bb, [True] * n, set(), 0
            continue
        if "action" not in event:
            continue
        seat, bot, kind, amount = event["seat"], event["bot"], event["action"], event["amount"]
        if STREETS[event["street"]] != street or folded[seat] or stacks[seat] <= 0:
            raise ValueError("Action on wrong street or from inactive seat")
        if kind not in ACTIONS or not isinstance(amount, int) or amount < 0:
            raise ValueError("Unknown action or invalid amount")
        if kind in ("fold", "check") and amount != 0:
            raise ValueError("Fold/check amount must be zero")
        call = min(current - bets[seat], stacks[seat])
        maximum = bets[seat] + stacks[seat]
        minimum = min(maximum, current + increment if current else bb)
        can_raise = reopen[seat] and maximum > current and sum(not f and s > 0 for f, s in zip(folded, stacks)) > 1
        if (kind == "raise" and (not can_raise or not minimum <= amount <= maximum)
                or kind in ("call", "fold") and call <= 0 or kind == "check" and call != 0):
            raise ValueError("Illegal recorded action")
        if kind == "call" and amount != call:
            raise ValueError("Recorded call differs from reconstructed to_call")
        hole = event.get("holes", {}).get(bot)
        pct, made, draw = np.nan, np.nan, False
        if hole:
            if len(hole) != 2 or len(set(hole + board)) != len(hole + board):
                raise ValueError("Invalid/duplicate visible cards")
            pct = hand_percentile(hole)
            if street:
                made, draw = _strength(tuple(hole), tuple(board))
        seen = [stats[name] for i, name in enumerate(seats)
                if i != seat and not folded[i] and stats[name][0] >= 10]
        agg = sum(x[1] / x[0] for x in seen) / len(seen) if seen else 0
        folds = sum(x[2] / max(x[3], 1) for x in seen) / len(seen) if seen else 0.3
        cbet = street == 1 and pre_aggressor == seat and street_raises == 0
        result.append((bot, (match_index, street, seat, n, pct, made, draw, call > 0,
                            can_raise, pre_raises, cbet, ACTIONS[kind], amount, pot,
                            minimum, maximum, call, stacks[seat], current, bets[seat],
                            agg > .3, folds > .5, folds < .25, event["hand"])))
        if street == 0:
            hand_metrics[bot][1] |= kind in ("call", "raise")
            hand_metrics[bot][2] |= kind == "raise"
        acted.add(seat)
        if kind == "fold":
            folded[seat] = True
        elif kind == "call":
            stacks[seat] -= call
            bets[seat] += call
            pot += call
        elif kind == "raise":
            paid, inc = amount - bets[seat], amount - current
            stacks[seat] -= paid
            pot += paid
            bets[seat], current = amount, amount
            if inc >= increment:
                increment, reopen, acted = inc, [True] * n, {seat}
            else:
                for previous in acted:
                    reopen[previous] = False
            street_raises += 1
            if street == 0:
                pre_raises += 1
                pre_aggressor = seat
        if pot != event["pot"]:
            raise ValueError(f"Pot mismatch: reconstructed {pot}, recorded {event['pot']}")
        counters = stats[bot]
        counters[0] += 1
        counters[1] += kind == "raise"
        counters[2] += kind == "fold"
        counters[3] += kind in ("fold", "call", "raise")
    return result, hand_metrics


def load_dataset(actions_path, matches_path, state_path, *, stack=200, sb=1, bb=2):
    """Stream once, reject malformed/duplicate/incomplete hands, join by id."""
    matches, audit = read_metadata(matches_path, state_path)
    by_id = {m["id"]: (i, m) for i, m in enumerate(matches)}
    observations, hands = defaultdict(list), defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    stats, completed, counts = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0])), set(), Counter()
    last_hand = {}
    path, digest = Path(actions_path), sha256()
    before = path.stat()
    key, group = None, []

    def consume(hand_key, events):
        if hand_key in completed:
            raise ValueError(f"Repeated/non-contiguous hand {hand_key}")
        completed.add(hand_key)
        mid, hand = hand_key
        if hand != last_hand.get(mid, -1) + 1:
            raise ValueError(f"Missing/out-of-order hand in {mid}: {hand}; match stats require complete replay order")
        last_hand[mid] = hand
        if mid not in by_id:
            raise ValueError(f"No collected metadata for match {mid}")
        index, meta = by_id[mid]
        try:
            rows, metrics = reconstruct_hand(events, meta, index, stats[mid], stack=stack, sb=sb, bb=bb)
        except (ValueError, KeyError, IndexError) as exc:
            raise ValueError(f"{hand_key}: {exc}") from exc
        for bot, row in rows:
            observations[bot].append(row)
        for bot, values in metrics.items():
            hands[bot][index] = [a + b for a, b in zip(hands[bot][index], values)]
        counts["hands"] += 1
        counts["actions"] += len(rows)

    with path.open("rb") as source:
        for line_number, line in enumerate(source, 1):
            digest.update(line)
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                new_key = (event["match"], event["hand"])
            except (ValueError, KeyError, TypeError) as exc:
                raise ValueError(f"Invalid JSONL record at line {line_number}") from exc
            if key is not None and key != new_key:
                consume(key, group)
                group = []
            key = new_key
            group.append(event)
            counts["rows"] += 1
    if key is not None:
        consume(key, group)
    if not completed:
        raise ValueError("No complete hands were found in actions.jsonl")
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("actions.jsonl changed during reading; retry from a stable snapshot")
    arrays = {b: np.asarray(rows, dtype=np.float64) for b, rows in observations.items()}
    for b in hands:
        arrays.setdefault(b, np.empty((0, len(FIELDS))))
    audit.update(counts)
    audit.update(actions_sha256=digest.hexdigest(), bots=len(arrays),
                 matches_with_actions=len({mid for mid, _ in completed}),
                 missing_hole_actions=int(sum(np.isnan(a[:, COL["pct"]]).sum() for a in arrays.values())),
                 timestamp_basis="state.collected[match_id].collected_at", stack=stack, sb=sb, bb=bb)
    return Dataset(matches, arrays, {b: dict(v) for b, v in hands.items()}, audit)


def save_dataset(dataset, path):
    """Safe NumPy cache: no pickles and no source files modified."""
    bots = sorted(dataset.observations)
    metadata = dict(format_version=1, fields=list(FIELDS), matches=dataset.matches,
                    hands=dataset.hands, audit=dataset.audit, bots=bots,
                    feature_source_sha256=sha256(Path(param.__file__).read_bytes()).hexdigest())
    arrays = {f"bot_{i}": dataset.observations[b] for i, b in enumerate(bots)}
    np.savez_compressed(path, metadata=np.asarray(json.dumps(metadata)), **arrays)


def load_cache(path):
    with np.load(path, allow_pickle=False) as cache:
        meta = json.loads(str(cache["metadata"]))
        if meta.get("format_version") != 1 or meta.get("fields") != list(FIELDS):
            raise ValueError("Incompatible feature cache; rebuild it from the input JSON files")
        if meta.get("feature_source_sha256") != sha256(Path(param.__file__).read_bytes()).hexdigest():
            raise ValueError("sparring/param.py changed since this feature cache was built; rebuild it")
        arrays = {b: cache[f"bot_{i}"].copy() for i, b in enumerate(meta["bots"])}
    return Dataset(meta["matches"], arrays,
                   {b: {int(k): v for k, v in x.items()} for b, x in meta["hands"].items()}, meta["audit"])
