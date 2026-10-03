"""One ParamBot implementation for all data-defined offline competitors."""

import importlib.util
from pathlib import Path
import random

if __package__:
    from .catalog import load_record
else:
    from catalog import load_record

# Resolve the scaffold relative to this file, including when the SDK loads a
# competitor from outside the repository root. Do not shadow another bot's
# top-level `param` module or change the process import path.
_path = Path(__file__).resolve().parents[1] / "param.py"
_spec = importlib.util.spec_from_file_location("_competitor_param", _path)
_param = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_param)

_policy_spec = importlib.util.spec_from_file_location('_competitor_policy',Path(__file__).resolve().parent/'policy.py')
_policy = importlib.util.module_from_spec(_policy_spec)
_policy_spec.loader.exec_module(_policy)
_policies = {}


class FittedBot(_param.ParamBot):
    """Use the fitted style unchanged; every game gets fresh counters and RNG."""

    def __init__(self, record, directory, seed=None):
        self.DISPLAY_NAME = record['name']
        self.STYLE = dict(record['style'])
        super().__init__(style=self.STYLE,
                         seed=seed if seed is not None else random.getrandbits(128))
        self.policy_config = record.get('policy')
        self.policy = None
        if self.policy_config:
            path=(Path(directory)/self.policy_config['file']).resolve()
            stat=path.stat()
            key=(stat.st_mtime_ns,stat.st_size)
            if path not in _policies or _policies[path][0] != key:
                _policies[path]=(key,_policy.Policy(path))
            self.policy=_policies[path][1]

    def act(self,state):
        if self.DISPLAY_NAME=='house:call':
            return self.passive(state,True)
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


def make_from_catalog(path, identity, seed):
    return FittedBot(load_record(path, identity), Path(path).parent, seed=seed)
