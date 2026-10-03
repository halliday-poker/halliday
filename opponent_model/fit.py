"""Opportunity-conditioned inverse estimators for sparring.param's settings.

The fitted parameters describe a surrogate, not the opponent's source code.
All likelihood, grid fitting, and cluster-bootstrap matrix operations run
on the explicitly selected torch device. NumPy is used for input grouping.
"""

from dataclasses import dataclass
from itertools import product
import math

import numpy as np
import torch

from sparring.param import ARCHETYPES
from .data import COL

PARAMETERS = ("vpip", "pfr", "threebet", "limp", "aggression", "cbet", "bluff", "stickiness", "size", "adaptive")
REFERENCE = ARCHETYPES["tag"]


@dataclass
class Block:
    names: tuple
    candidates: torch.Tensor
    loss: torch.Tensor                 # matches x candidates
    counts: torch.Tensor               # opportunities per match
    features: torch.Tensor
    totals: torch.Tensor               # matches x unique feature bins
    successes: torch.Tensor
    probability: object
    contamination: float

    def scores(self, weights):
        return weights @ self.loss

    def choose(self, scores, allowed=None):
        if allowed is not None:
            scores = scores.masked_fill(~allowed, float("inf"))
        reference = self.candidates.new_tensor([REFERENCE[n] for n in self.names])
        tie_break = ((self.candidates - reference) ** 2).sum(1) * 1e-9
        index = (scores + tie_break).argmin(1)
        return self.candidates[index], scores.gather(1, index[:, None]).squeeze(1), scores


def free_bet_probability(features, candidates, adaptive):
    """Marginalize all value/cbet/draw/bluff branches in ParamBot.postflop."""
    strength, draw, cbet_spot, agg_high, fold_high, fold_low = features.T
    aggression, cbet, bluff = (candidates[:, i][None, :] for i in range(3))
    if adaptive:
        bluff = (bluff - .05 * agg_high[:, None]).expand(len(features), -1)
        bluff = torch.where(fold_high[:, None].bool(), bluff + .15,
                            torch.where(fold_low[:, None].bool(), bluff * .3, bluff)).clamp(0, 1)
        cbet = (cbet + .15 * fold_high[:, None]).clamp(0, 1)
    value = strength[:, None] >= .8 - .3 * aggression
    continuation = cbet_spot[:, None] * cbet
    semi = draw[:, None] * aggression * .6
    probability = continuation + (1 - continuation) * (semi + (1 - semi) * bluff * .5)
    return torch.where(value, 1.0, probability)


class BotModel:
    def __init__(self, observations, hand_counts, compute, *, grid_step=.05, contamination=.05):
        if not 0 < grid_step <= .25 or not 0 < contamination < .5:
            raise ValueError("grid_step must be in (0,.25]; contamination in (0,.5)")
        self.compute, self.contamination = compute, contamination
        self.observations = observations
        self.matches = sorted(hand_counts)
        self.match_lookup = {m: i for i, m in enumerate(self.matches)}
        self.hand_counts = compute.array([hand_counts[m] for m in self.matches])
        self.blocks = {}
        c = lambda name: observations[:, COL[name]]
        match = np.asarray([self.match_lookup[int(m)] for m in c("match")], dtype=np.int64)
        self.local_match = match
        pre, known = c("street") == 0, np.isfinite(c("pct"))
        free_pre = pre & known & (c("pre_raises") == 0)
        raised = c("action") == 3
        fine = np.linspace(0, 1, 101)
        coarse = np.linspace(0, 1, round(1 / grid_step) + 1)
        self.grid_step = float(coarse[1] - coarse[0])

        def block(key, names, mask, success, features, candidates, probability):
            x = np.asarray(features)[mask]
            if x.ndim == 1:
                x = x[:, None]
            unique, inverse = np.unique(x, axis=0, return_inverse=True)
            m = match[mask]
            bins = max(1, len(unique))
            flat = compute.array(m * bins + inverse, torch.long)
            totals = torch.bincount(flat, minlength=len(self.matches) * bins).reshape(len(self.matches), bins).to(compute.dtype)
            wins = torch.bincount(flat, weights=compute.array(np.asarray(success)[mask]),
                                  minlength=len(self.matches) * bins).reshape(len(self.matches), bins).to(compute.dtype)
            values = compute.array(np.asarray(candidates).reshape(-1, len(names)))
            unique_tensor = compute.array(unique if len(unique) else np.zeros((1, x.shape[1])))
            loss = compute.zeros(len(self.matches), len(values))
            batch = compute.batch_size or len(values)
            for start in range(0, len(values), batch):
                p = probability(unique_tensor, values[start:start + batch]).to(compute.dtype)
                p = contamination / 2 + (1 - contamination) * p
                loss[:, start:start + batch] = -(wins @ p.log() + (totals - wins) @ torch.log1p(-p))
            result = Block(names, values, loss, totals.sum(1), unique_tensor, totals, wins, probability, contamination)
            self.blocks[key] = result
            return result

        threshold = lambda x, p: (x[:, :1] < p[:, 0][None, :]).to(compute.dtype)
        block("vpip", ("vpip",), free_pre & c("facing").astype(bool),
              c("action") >= 2, c("pct"), fine, threshold)
        # pfr and limp are jointly estimated; an observed PFR is NOT s['pfr'].
        block("open", ("pfr", "limp"), free_pre & c("can_raise").astype(bool), raised,
              c("pct"), list(product(fine, coarse)),
              lambda x, p: (x[:, :1] < p[:, 0][None, :]) * (1 - p[:, 1][None, :]))
        block("threebet", ("threebet",), pre & known & (c("pre_raises") == 1) & c("can_raise").astype(bool),
              raised, c("pct"), fine, threshold)
        free_post = ~pre & np.isfinite(c("strength")) & ~c("facing").astype(bool) & c("can_raise").astype(bool)
        free_features = np.column_stack([c(n) for n in ("strength", "draw", "cbet", "agg_high", "fold_high", "fold_low")])
        # A disallowed attempted raise is coerced to a call by ParamBot.bet;
        # those calls do not identify its ordinary calling threshold.
        call_mask = (~pre & np.isfinite(c("strength")) & c("facing").astype(bool)
                     & c("can_raise").astype(bool) & ~raised)
        need = (c("call") / np.maximum(1, c("pot") + c("call")) + .2
                - c("strength") - .1 * c("draw") * (c("street") != 3)) / .3
        for adaptive in (0, 1):
            block(f"post{adaptive}", ("aggression", "cbet", "bluff"), free_post, raised,
                  free_features, list(product(coarse, coarse, coarse)),
                  lambda x, p, a=adaptive: free_bet_probability(x, p, a))
            block(f"stick{adaptive}", ("stickiness",), call_mask, c("action") == 2,
                  np.column_stack([need, c("agg_high")]), fine,
                  lambda x, p, a=adaptive: (x[:, :1] <= (p[:, 0][None, :] + .15 * a * x[:, 1:2]).clamp(0, 1)).to(compute.dtype))
        # Exclude cbet-eligible openings: their 0.8 size multiplier is latent.
        # Min/max clipped observations remain in the censored likelihood.
        size_mask = free_post & raised & ~c("cbet").astype(bool)
        size_features = np.column_stack([c(n) for n in ("amount", "pot", "minimum", "maximum")])[size_mask]
        size_grid = np.linspace(.25, 1.5, 251)[:, None]
        self._size_block(size_features, match[size_mask], size_grid)

    def _size_block(self, features, matches, candidates):
        compute = self.compute
        x, values = compute.array(features), compute.array(candidates)
        amount, pot, minimum, maximum = (x[:, i:i+1] for i in range(4))
        low, high = pot * values[:, 0][None, :] * .85, pot * values[:, 0][None, :] * 1.15
        left = torch.where(amount == minimum, -float("inf"), amount)
        right = torch.where(amount == maximum, float("inf"), amount + 1)
        mass = (torch.minimum(high, right) - torch.maximum(low, left)).clamp(min=0) / (high - low).clamp(min=1e-12)
        noise = 1 / (maximum - minimum + 1).clamp(min=1)
        p = (1 - self.contamination) * mass + self.contamination * noise
        loss = compute.zeros(len(self.matches), len(candidates))
        counts = compute.zeros(len(self.matches))
        indices = compute.array(matches, torch.long)
        self.size_match_indices = indices
        loss.index_add_(0, indices, -p.clamp(min=1e-300).log())
        counts.index_add_(0, indices, torch.ones(len(indices), dtype=compute.dtype, device=compute.device))
        self.blocks["size"] = Block(("size",), values, loss, counts, x,
                                    compute.zeros(len(self.matches), 0), compute.zeros(len(self.matches), 0), None, self.contamination)

    def fit_weights(self, weights, *, profiles=False):
        """Fit all bootstrap replicates in parallel on the selected device."""
        batch = self.compute.batch_size
        if batch is not None and len(weights) > batch:
            chunks, first = [], None
            for start in range(0, len(weights), batch):
                values, details = self.fit_weights(weights[start:start + batch], profiles=profiles and start == 0)
                chunks.append(values)
                if start == 0:
                    first = details
            return torch.cat(chunks), first
        scores = {}
        vpip, _, scores["vpip"] = self.blocks["vpip"].choose(self.blocks["vpip"].scores(weights))
        opening, _, scores["open"] = self.blocks["open"].choose(
            self.blocks["open"].scores(weights), self.blocks["open"].candidates[:, 0][None, :] <= vpip)
        threebet, _, scores["threebet"] = self.blocks["threebet"].choose(
            self.blocks["threebet"].scores(weights), self.blocks["threebet"].candidates[:, 0][None, :] <= opening[:, :1])
        size, _, scores["size"] = self.blocks["size"].choose(self.blocks["size"].scores(weights))
        alternatives = []
        for adaptive in (0, 1):
            post, post_loss, scores[f"post{adaptive}"] = self.blocks[f"post{adaptive}"].choose(self.blocks[f"post{adaptive}"].scores(weights))
            stick, stick_loss, scores[f"stick{adaptive}"] = self.blocks[f"stick{adaptive}"].choose(self.blocks[f"stick{adaptive}"].scores(weights))
            alternatives.append((post, stick, post_loss + stick_loss))
        n = weights @ (self.blocks["post0"].counts + self.blocks["stick0"].counts)
        # Explicit complexity preference for the extra discrete adaptive mode.
        penalty = .5 * n.clamp(min=2).log()
        adaptive = (alternatives[1][2] + penalty < alternatives[0][2] - 1e-8)
        post = torch.where(adaptive[:, None], alternatives[1][0], alternatives[0][0])
        stick = torch.where(adaptive[:, None], alternatives[1][1], alternatives[0][1])
        values = torch.column_stack([vpip[:, 0], opening[:, 0], threebet[:, 0], opening[:, 1],
                                      post[:, 0], post[:, 1], post[:, 2], stick[:, 0], size[:, 0], adaptive])
        details = dict(adaptive_log_likelihood_gain=(alternatives[0][2][0] - alternatives[1][2][0]).item(),
                       adaptive_penalty=penalty[0].item())
        if profiles:
            details["scores"] = {k: v[0].clone() for k, v in scores.items()}
        return values, details

    def per_match(self, min_opportunities=10):
        weights = torch.eye(len(self.matches), dtype=self.compute.dtype, device=self.compute.device)
        values, _ = self.fit_weights(weights)
        for i, name in enumerate(PARAMETERS):
            block = self.blocks[self.block_for(name, 0)]
            counts = block.counts
            if name == "cbet":
                counts = (block.totals * block.features[:, 2][None, :]).sum(1)
            values[counts < min_opportunities, i] = float("nan")
        return values

    @staticmethod
    def block_for(name, adaptive):
        if name in ("pfr", "limp"):
            return "open"
        if name in ("aggression", "cbet", "bluff", "adaptive"):
            return f"post{adaptive}"
        if name == "stickiness":
            return f"stick{adaptive}"
        return name

    def estimate(self, selected, *, bootstrap=500, confidence=.95):
        if not selected:
            raise ValueError("Cannot fit an empty segment")
        weights = self.compute.bootstrap_weights(selected, len(self.matches), bootstrap)
        values, details = self.fit_weights(weights, profiles=True)
        alpha, output = 1 - confidence, {}
        point = values[0]
        adaptive = int(point[-1].item())
        for i, name in enumerate(PARAMETERS):
            key = self.block_for(name, adaptive)
            block = self.blocks[key]
            count = weights[0] @ block.counts
            matches = int(((weights[0] > 0) & (block.counts > 0)).sum().item())
            if name == "cbet":
                opportunities = (block.totals * block.features[:, 2][None, :]).sum(1)
                count = weights[0] @ opportunities
                matches = int(((weights[0] > 0) & (opportunities > 0)).sum().item())
            elif name == "adaptive":
                opportunities = self.blocks["post0"].counts + self.blocks["stick0"].counts
                count = weights[0] @ opportunities
                matches = int(((weights[0] > 0) & (opportunities > 0)).sum().item())
            sample = values[1:, i]
            variance = sample.var(unbiased=True).item() if bootstrap > 1 and matches > 1 else None
            interval = torch.quantile(sample, self.compute.array([alpha / 2, 1 - alpha / 2])).tolist() if bootstrap and matches > 1 else None
            if name == "adaptive":
                # A model selection frequency is not a probability of adaptation.
                flat, support = [0, 1], [0, 1]
            else:
                score = details["scores"][key]
                j = block.names.index(name)
                best = score.min()
                flat_values = block.candidates[score <= best + 1e-7, j]
                support_values = block.candidates[score <= best + 1.920729, j]
                flat = [flat_values.min().item(), flat_values.max().item()]
                support = [support_values.min().item(), support_values.max().item()]
            domain = 1.25 if name == "size" else 1
            status = "estimated"
            if count < 20 or matches < 3:
                status = "insufficient_data"
            elif name != "adaptive" and flat[1] - flat[0] >= .95 * domain:
                status = "not_identified"
            elif name != "adaptive" and support[1] - support[0] > .5 * domain:
                status = "weakly_identified"
            elif variance == 0 or interval is not None and interval[0] == interval[1]:
                status = "grid_limited"
            if name == "adaptive":
                status = "model_comparison_only" if count >= 20 and matches >= 3 else "insufficient_data"
            # Meaningful reference evidence needs both resampling uncertainty
            # and the likelihood-support set; no Wald p-values for step rules.
            envelope = ([min(interval[0], support[0]), max(interval[1], support[1])]
                        if interval else None)
            ref = REFERENCE[name]
            output[name] = dict(estimate=point[i].item() if count else None, status=status,
                                opportunities=int(count.item()), matches=matches, variance=variance,
                                standard_error=math.sqrt(variance) if variance is not None else None,
                                confidence_interval=interval, confidence_level=confidence,
                                interval_method="whole-match percentile bootstrap; conditional on selected boundaries and grid",
                                flat_likelihood_interval=flat, likelihood_support_interval=support,
                                reference_value=ref, reference_name="param:tag",
                                reference_outside_uncertainty=(not envelope[0] <= ref <= envelope[1]) if envelope else None,
                                p_value=None,
                                significance_note="No regular Wald p-value for discontinuous, partially identified surrogate parameters; use intervals and held-out change tests.")
        details.pop("scores")
        details["adaptive_selection_frequency"] = values[1:, -1].mean().item() if bootstrap else None
        details["bootstrap_replicates"] = bootstrap
        details["covariance_parameter_order"] = list(PARAMETERS)
        details["covariance"] = torch.cov(values[1:].T).tolist() if bootstrap > 1 and len(selected) > 1 else None
        empirical = self.empirical(weights, confidence)
        diagnostics = self.diagnostics(weights[0], point)
        style = {name: point[i].item() for i, name in enumerate(PARAMETERS)}
        style["adaptive"] = int(style["adaptive"])
        return dict(parameters=output, surrogate_style=style, uncertainty=details,
                    observed_statistics=empirical, model_diagnostics=diagnostics)

    def empirical(self, weights, confidence):
        c = lambda name: self.observations[:, COL[name]]
        pre, raised = c("street") == 0, c("action") == 3
        specifications = {
            "threebet_opportunity_rate": ((pre & (c("pre_raises") == 1) & c("can_raise").astype(bool)), raised),
            "limp_given_unraised_price": (pre & (c("pre_raises") == 0) & c("facing").astype(bool), c("action") == 2),
            "postflop_raise_given_can_raise": (~pre & c("can_raise").astype(bool), raised),
            "flop_cbet_opportunity_rate": (c("cbet").astype(bool) & ~c("facing").astype(bool) & c("can_raise").astype(bool), raised),
            "call_given_postflop_price": (~pre & c("facing").astype(bool), c("action") == 2),
        }
        counts = {"vpip_per_dealt_hand": (self.hand_counts[:, 1], self.hand_counts[:, 0]),
                  "pfr_per_dealt_hand": (self.hand_counts[:, 2], self.hand_counts[:, 0])}
        for name, (mask, success) in specifications.items():
            idx = self.compute.array(self.local_match[mask], torch.long)
            numerator = torch.bincount(idx, weights=self.compute.array(success[mask]), minlength=len(self.matches)).to(self.compute.dtype)
            denominator = torch.bincount(idx, minlength=len(self.matches)).to(self.compute.dtype)
            counts[name] = (numerator, denominator)
        output = {}
        for name, (success, total) in counts.items():
            n = weights @ total
            ratio = (weights @ success) / n.clamp(min=1)
            usable = ratio[1:][n[1:] > 0]
            matches = int(((weights[0] > 0) & (total > 0)).sum().item())
            point = ratio[0].item() if n[0] else None
            output[name] = dict(estimate=point, opportunities=int(n[0].item()), matches=matches,
                               observation_variance=point * (1 - point) if point is not None else None,
                               estimator_variance=usable.var(unbiased=True).item() if len(usable) > 1 and matches > 1 else None,
                               confidence_interval=torch.quantile(usable, self.compute.array([(1-confidence)/2, (1+confidence)/2])).tolist() if len(usable) and matches > 1 else None,
                               degenerate_bootstrap=bool(len(usable) and usable.max() == usable.min()),
                               p_value=None, null_hypothesis="No empirical-rate null specified; these are not param.py's latent settings.")
        return output

    def diagnostics(self, weights, point):
        """Opportunity-bin residuals expose context/model misspecification."""
        style = dict(zip(PARAMETERS, point.tolist()))
        result = {}
        for key in ("vpip", "open", "threebet", f"post{int(style['adaptive'])}", f"stick{int(style['adaptive'])}"):
            block = self.blocks[key]
            candidate = self.compute.array([[style[n] for n in block.names]])
            raw = block.probability(block.features, candidate).squeeze(1).to(self.compute.dtype)
            p = raw * (1 - self.contamination) + self.contamination / 2
            n, yes = weights @ block.totals, weights @ block.successes
            total = n.sum()
            if not total:
                result[key] = dict(opportunities=0)
                continue
            residual = yes - n * p
            brier = (yes * (1-p)**2 + (n-yes) * p**2).sum() / total
            incompatible = ((raw == 0) * yes + (raw == 1) * (n-yes)).sum() / total
            result[key] = dict(opportunities=int(total.item()), brier_score=brier.item(),
                               log_loss=(-(yes*p.log() + (n-yes)*torch.log1p(-p)).sum()/total).item(),
                               incompatible_action_fraction=incompatible.item(),
                               residual_rms_by_opportunity_bin=torch.sqrt(((residual/n.clamp(min=1))**2*n).sum()/total).item(),
                               warning="High residuals can reflect missing strategy variables, context shifts or a poor surrogate family.")
        size = self.blocks["size"]
        w = weights[self.size_match_indices]
        if w.sum():
            amount, pot, minimum, maximum = (size.features[:, i] for i in range(4))
            low, high = pot * style["size"] * .85, pot * style["size"] * 1.15
            left = torch.where(amount == minimum, -float("inf"), amount)
            right = torch.where(amount == maximum, float("inf"), amount + 1)
            incompatible = torch.minimum(high, right) <= torch.maximum(low, left)
            ratio = amount / pot.clamp(min=1)
            mean = (w*ratio).sum()/w.sum()
            result["size"] = dict(opportunities=int(w.sum().item()),
                                  censored_fraction=((w*((amount == minimum) | (amount == maximum))).sum()/w.sum()).item(),
                                  incompatible_amount_fraction=((w*incompatible).sum()/w.sum()).item(),
                                  observed_pot_fraction_mean=mean.item(),
                                  observed_pot_fraction_variance=((w*(ratio-mean)**2).sum()/w.sum()).item(),
                                  warning="Observed ratios include integer rounding and legal clipping; they are not latent target sizes.")
        else:
            result["size"] = dict(opportunities=0)
        return result
