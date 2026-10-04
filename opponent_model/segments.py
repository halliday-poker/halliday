"""Penalized global segmentation with independent held-out confirmation."""

from hashlib import sha256
import math

import numpy as np
import torch


def split_discovery(match_ids, timestamps, seed):
    """Same timestamp stays together. The split never examines bot actions."""
    groups = {}
    for mid, timestamp in zip(match_ids, timestamps):
        groups.setdefault(timestamp, []).append(mid)
    chosen = {}
    for timestamp, ids in groups.items():
        key = f"{seed}|{timestamp}|{'|'.join(sorted(ids))}"
        chosen[timestamp] = int.from_bytes(sha256(key.encode()).digest()[:8], "big") % 2 == 0
    return np.asarray([chosen[t] for t in timestamps], dtype=bool)


def standardize(discovery, values):
    finite = torch.isfinite(discovery)
    count = finite.sum(0)
    clean = torch.nan_to_num(discovery)
    mean = clean.sum(0) / count.clamp(min=1)
    variance = ((clean - mean) ** 2 * finite).sum(0) / (count - 1).clamp(min=1)
    usable = (count >= 4) & (variance > 1e-10)
    return (values[:, usable] - mean[usable]) / variance[usable].sqrt(), int(usable.sum().item())


def optimal_partition(values, timestamps, *, minimum=6, penalty=None, max_segments=6):
    """Globally minimize standardized within-segment SSE + penalty per cut.

    GPU prefix tensors compute all segment costs. Only the tiny dynamic
    programming control loop runs on the host. Tied times cannot be split.
    """
    n, d = values.shape
    if n < 2 * minimum or not d:
        return [], dict(null_cost=None, penalized_cost=None, penalty=penalty)
    penalty = (d + 1) * math.log(n) if penalty is None else penalty
    finite = torch.isfinite(values)
    clean = torch.nan_to_num(values)
    prefix = lambda x: torch.cat([x.new_zeros((1, d)), x.cumsum(0)], dim=0)
    sums, squares, counts = prefix(clean), prefix(clean ** 2), prefix(finite.to(values.dtype))
    delta = lambda x: x[None, :, :] - x[:, None, :]
    nn, ss, sq = delta(counts), delta(sums), delta(squares)
    cost = (sq - ss ** 2 / nn.clamp(min=1)).clamp(min=0).sum(2)
    valid = [0] + [i for i in range(1, n) if timestamps[i-1] < timestamps[i]] + [n]
    score = values.new_full((max_segments + 1, n + 1), float("inf"))
    score[0, 0] = -penalty
    previous = {}
    for k in range(1, max_segments + 1):
        for end in valid[1:]:
            starts = [j for j in valid if j <= end - minimum]
            if not starts:
                continue
            indices = torch.tensor(starts, dtype=torch.long, device=values.device)
            options = score[k-1, indices] + cost[indices, end] + penalty
            value, index = options.min(0)
            score[k, end] = value
            previous[k, end] = starts[index.item()]
    k = int(score[:, n].argmin().item())
    objective = score[k, n].item()
    cuts, end = [], n
    while k > 1:
        end = previous[k, end]
        cuts.append(end)
        k -= 1
    return sorted(cuts), dict(null_cost=cost[0, n].item(), penalized_cost=objective, penalty=penalty,
                             objective="standardized within-segment SSE + penalty per boundary")


def permutation_difference(values, left_count, compute, *, permutations=4999, batch=256):
    """Fixed-boundary test; permute entire held-out match feature vectors."""
    n = len(values)
    if left_count < 2 or n-left_count < 2 or not values.shape[1]:
        return dict(p_value=None, statistic=None, reason="insufficient held-out matches/features")
    finite = torch.isfinite(values).to(values.dtype)
    clean = torch.nan_to_num(values)
    total, total_count = clean.sum(0), finite.sum(0)

    def statistic(membership):
        count_left = membership @ finite
        count_right = total_count - count_left
        sum_left = membership @ clean
        difference = sum_left/count_left.clamp(min=1) - (total-sum_left)/count_right.clamp(min=1)
        effective = count_left * count_right / total_count.clamp(min=1)
        usable = (count_left >= 2) & (count_right >= 2)
        return (difference.square() * effective * usable).sum(1)

    observed_membership = compute.zeros(1, n)
    observed_membership[0, :left_count] = 1
    observed = statistic(observed_membership)[0]
    exceed = 0
    for start in range(0, permutations, batch):
        b = min(batch, permutations-start)
        index = torch.rand((b, n), device=compute.device, generator=compute.generator).argsort(1)[:, :left_count]
        membership = compute.zeros(b, n)
        membership.scatter_(1, index, 1)
        exceed += int((statistic(membership) >= observed - 1e-12).sum().item())
    p = (exceed+1) / (permutations+1)
    return dict(p_value=p, statistic=observed.item(), permutations=permutations,
                monte_carlo_standard_error=math.sqrt(p*(1-p)/(permutations+1)),
                null_hypothesis="held-out match parameter vectors are exchangeable across the fixed boundary")


def propose_changes(values, timestamps, match_ids, compute, *, seed=20261003,
                    minimum=6, penalty_scale=1.0, max_segments=6, permutations=4999):
    if minimum < 2 or penalty_scale <= 0 or max_segments < 1 or permutations < 19:
        raise ValueError("Invalid segmentation settings")
    discovery = split_discovery(match_ids, timestamps, seed)
    train = np.flatnonzero(discovery)
    test = np.flatnonzero(~discovery)
    # Binary adaptation mode is model selection, not a continuous parameter.
    continuous = values[:, :-1]
    normalized, dimensions = standardize(continuous[train], continuous)
    train_times = [timestamps[i] for i in train]
    penalty = penalty_scale * (dimensions + 1) * math.log(max(2, len(train)))
    cuts, objective = optimal_partition(normalized[train], train_times, minimum=minimum,
                                        penalty=penalty, max_segments=max_segments)
    cut_times = [(train_times[i-1] + train_times[i])/2 for i in cuts]
    proposals = []
    bounds = [-float("inf"), *cut_times, float("inf")]
    for j, (cut, timestamp) in enumerate(zip(cuts, cut_times)):
        left = [i for i in test if bounds[j] <= timestamps[i] < timestamp]
        right = [i for i in test if timestamp <= timestamps[i] < bounds[j+2]]
        evidence = (permutation_difference(normalized[left+right], len(left), compute, permutations=permutations)
                    if min(len(left), len(right)) >= minimum else
                    dict(p_value=None, statistic=None, reason="too few held-out matches on at least one side"))
        proposals.append(dict(cut_at=timestamp, last_discovery_before=train_times[cut-1],
                              first_discovery_after=train_times[cut], heldout_left=len(left),
                              heldout_right=len(right), **evidence))
    return dict(discovery_matches=len(train), heldout_matches=len(test), usable_dimensions=dimensions,
                minimum_matches_per_side_per_split=minimum, objective=objective, proposals=proposals,
                accepted_cut_times=[], split_seed=seed)


def confirm_family(plans, *, alpha=.05):
    """Holm control across ALL proposed bot/boundary tests in this report."""
    tests = [proposal for plan in plans for proposal in plan["proposals"] if proposal["p_value"] is not None]
    ordered = sorted(tests, key=lambda x: x["p_value"])
    running = 0
    for i, proposal in enumerate(ordered):
        running = max(running, min(1.0, proposal["p_value"] * (len(ordered)-i)))
        proposal["adjusted_p_value"] = running
        proposal["accepted"] = running <= alpha
    for plan in plans:
        plan["accepted_cut_times"] = [p["cut_at"] for p in plan["proposals"] if p.get("accepted", False)]
        for p in plan["proposals"]:
            p.setdefault("adjusted_p_value", None)
            p.setdefault("accepted", False)
        plan["correction"] = dict(method="Holm", family_tests=len(tests), alpha=alpha,
                                  scope="all candidate bot/boundary tests in this invocation")
