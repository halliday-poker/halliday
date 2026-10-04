"""Cheap, uncertainty-weighted classification of anonymous opponents.

The exported beta distributions include variation between members of a group.
Tempered beta-binomial evidence avoids treating correlated public statistics as
independent exact measurements of a single fixed strategy.
"""
from math import exp, lgamma, log

if __package__:
    from .group_observer import FEATURES
else:
    from group_observer import FEATURES


FEATURE_WEIGHTS = (.45, .45, .35, .65, .70, .50, .35, .30, .25)


def distribution(group, seats):
    context='short' if seats<=3 else 'tournament' if seats<=6 else 'full'
    return group.get('contexts',{}).get(context,group)


def posterior(counts, groups, temperature=1.0, seats=None):
    scores = []
    for group in groups:
        score = log(group['prior'])
        shape = distribution(group,seats) if seats is not None else group
        for (s,n),mean,k,weight in zip(counts,shape['mean'],shape['concentration'],FEATURE_WEIGHTS):
            if not n:
                continue
            # No single abundant statistic can dominate indefinitely.
            scale = min(1.0, 60.0/n)
            s,n = s*scale,n*scale
            a,b = mean*k,(1-mean)*k
            score += temperature*weight*(lgamma(a+s)+lgamma(b+n-s)-lgamma(a+b+n)
                                           -lgamma(a)-lgamma(b)+lgamma(a+b))
        scores.append(score)
    if not scores:
        return ()
    maximum = max(scores)
    mass = [exp(s-maximum) for s in scores]
    total = sum(mass)
    return tuple(m/total for m in mass)


def confidence(probabilities, groups, hands, threshold=.7):
    if len(probabilities) == 0 or hands < 4:
        return 0.0
    best = max(range(len(probabilities)), key=probabilities.__getitem__)
    p,prior = probabilities[best],groups[best]['prior']
    if p <= threshold:
        return 0.0
    odds_gain = log(max(1e-12,p/(1-p+1e-12)*(1-prior)/prior))
    evidence = min(1.0,max(0.0,odds_gain/log(4)))
    return min(1.0,hands/12.0)*(p-threshold)/(1-threshold)*evidence


class GroupModel:
    def __init__(self, observer, groups, config):
        self.observer,self.groups,self.config = observer,groups,config
        self._cache = {}

    def classify(self, player):
        revision = self.observer.revision
        cached = self._cache.get(player)
        if cached and cached[0] == revision:
            return cached[1]
        counts = self.observer.counts[player]
        probabilities = posterior(counts,self.groups,self.config['temperature'],getattr(self.observer,'table_size',None))
        weight = confidence(probabilities,self.groups,self.observer.hands[player],self.config['threshold'])
        top = max(range(len(probabilities)),key=probabilities.__getitem__)
        # An opponent far outside every observed group should remain uncertain.
        surprises = []
        for group in self.groups:
            shape=distribution(group,getattr(self.observer,'table_size',6))
            distance,total = 0.0,0.0
            for (s,n),mean,k,w in zip(counts,shape['mean'],shape['concentration'],FEATURE_WEIGHTS):
                if n >= 8:
                    variance=mean*(1-mean)*(1/(k+1)+1/n)
                    distance+=w*((s/n-mean)**2/max(variance,1e-5));total+=w
            surprises.append(distance/max(1,total))
        weight *= min(1.0,4.0/max(4.0,min(surprises)))
        result = dict(top=top,probability=probabilities[top],weight=weight,posterior=probabilities,
                      hands=self.observer.hands[player],drift=self.observer.drift(player))
        self._cache[player] = revision,result
        return result

    def parameters(self, player, base, counters=True, strength=1.0):
        result = self.classify(player)
        weight = result['weight']*strength
        if not weight:
            return base
        changes = {}
        field = 'counter' if counters else 'range_prior'
        for group,probability in zip(self.groups,result['posterior']):
            for name,target in group[field].items():
                changes[name] = changes.get(name,0.0)+probability*(target-base[name])
        return dict(base,**{name:base[name]+weight*delta for name,delta in changes.items()})

    def adaptive_weight(self, player):
        result=self.classify(player)
        prior=sum(g['adaptive']*p for g,p in zip(self.groups,result['posterior']))
        # A fitted adaptive trait is uncertain. Observed conditional drift adds
        # evidence but never claims to distinguish adaptation from other changes.
        return result['weight']*min(1.0,.35*prior+.65*result['drift'])
