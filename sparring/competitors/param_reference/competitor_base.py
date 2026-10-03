"""Shared ParamBot scaffold for the generated offline competitors."""

import importlib.util
from pathlib import Path
import random


# Resolve the scaffold relative to this file, including when the SDK loads a
# competitor from outside the repository root. Do not shadow another bot's
# top-level `param` module or change the process import path.
_path = Path(__file__).resolve().parents[2] / "param.py"
_spec = importlib.util.spec_from_file_location("_competitor_param", _path)
_param = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_param)

_policy_spec = importlib.util.spec_from_file_location('_competitor_policy',Path(__file__).resolve().parents[1]/'policy.py')
_policy = importlib.util.module_from_spec(_policy_spec)
_policy_spec.loader.exec_module(_policy)
_policies = {}


class FittedBot(_param.ParamBot):
    """Use the fitted style unchanged; every game gets fresh counters and RNG."""

    def __init__(self, seed=None):
        super().__init__(style=self.STYLE,
                         seed=seed if seed is not None else random.getrandbits(128))
        self.policy_config = getattr(self,'POLICY',None)
        self.policy = None
        if self.policy_config:
            path=Path(__file__).resolve().parent/self.policy_config['file']
            if path not in _policies:
                _policies[path]=_policy.Policy(path)
            self.policy=_policies[path]

    def act(self,state):
        if self.policy is None or self.rng.random()>=self.policy_config.get('weight',1):
            return super().act(state)
        self.me=state.player
        row=_policy.state_row(state,self.stats,_param)
        probability,sizing=self.policy.predict(row,self.policy_config['bot'],self.policy_config['epoch'])
        action=self.rng.choices(range(4),weights=probability[0],k=1)[0]
        if action==0:return state.fold()
        if action==1:return state.check()
        if action==2:return state.call()
        bucket=self.rng.choices(range(10),weights=sizing[0],k=1)[0]
        return self.bet(state,_policy.size_targets(row)[0,bucket])
