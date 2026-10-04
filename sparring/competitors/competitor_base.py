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


def cached_policy(directory, config):
    path=(Path(directory)/config['file']).resolve()
    stat=path.stat(); key=(stat.st_mtime_ns,stat.st_size)
    if path not in _policies or _policies[path][0] != key:
        _policies[path]=(key,_policy.Policy(path))
    return _policies[path][1]


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
            self.policy=cached_policy(directory,self.policy_config)
        self.patterns=record.get('patterns',{})
        self.sizing_config=self.patterns.get('sizing_policy')
        self.sizing_policy=cached_policy(directory,self.sizing_config) if self.sizing_config else None
        self.public_history=None
        self.public_actions=[]
        self.history_vector=None

    def on_match_start(self, info):
        if self.patterns:
            from sparring.competitors.patterns import PublicHistory
            self.me=info['player']
            self.public_history=PublicHistory(list(range(info['num_players'])))

    def on_hand_start(self, info):
        if self.public_history is not None:
            self.public_actions=[]
            self.history_vector=self.public_history.before(self.me)

    def on_action(self, event):
        super().on_action(event)
        if self.public_history is not None:
            self.public_actions.append(dict(bot=event['players'][event['seat']],street=event['street'],
                                            action=event['action'],amount=event['amount']))

    def on_hand_end(self, info):
        if self.public_history is not None:
            self.public_history.finish(self.public_actions,dict(zip(info['players'],info['deltas'])))

    def act(self,state):
        if self.DISPLAY_NAME=='house:call':
            return self.passive(state,True)
        if self.policy is None or self.rng.random()>=self.policy_config.get('weight',1):
            return super().act(state)
        self.me=state.player
        row=_policy.state_row(state,self.stats,_param)
        probability,sizing=self.policy.predict(row,self.policy_config['bot'],self.policy_config['epoch'],
                                              history=self.history_vector,hand=state.hand)
        slopes=self.patterns.get('preflop_progress')
        if slopes and state.street=='preflop':
            probability=_policy.softmax(_policy.np.log(probability.clip(1e-12))+
                _policy.np.asarray(slopes)*(min(state.hand,99)/99-.5),_policy.legal_actions(row))
        action=self.rng.choices(range(4),weights=probability[0],k=1)[0]
        if action==0:return state.fold()
        if action==1:return state.check()
        if action==2:return state.call()
        if self.sizing_policy is not None:
            _,temporal=self.sizing_policy.predict(row,self.sizing_config['bot'],self.sizing_config['epoch'],
                                                 history=self.history_vector,hand=state.hand)
            weight=self.sizing_config.get('weight',1)
            sizing=(1-weight)*sizing+weight*temporal
        bucket=self.rng.choices(range(10),weights=sizing[0],k=1)[0]
        return self.bet(state,_policy.size_targets(row)[0,bucket])


def make_from_catalog(path, identity, seed):
    return FittedBot(load_record(path, identity), Path(path).parent, seed=seed)
