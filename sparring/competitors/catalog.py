"""Data-only fitted opponents, shared by the builder and simulation loader."""
from copy import deepcopy
from functools import lru_cache
import json
import math
from pathlib import Path
import re

PARAMETERS = ("vpip", "pfr", "threebet", "limp", "aggression", "cbet", "bluff",
              "stickiness", "size", "adaptive")


def validate_style(name, style):
    if set(style) != set(PARAMETERS):
        raise ValueError(f"{name}: expected all ten surrogate parameters")
    for key, value in style.items():
        low, high = (.25, 1.5) if key == "size" else (0, 1)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"{name}: invalid {key}={value}")
    if not style["threebet"] <= style["pfr"] <= style["vpip"] or style["adaptive"] not in (0, 1):
        raise ValueError(f"{name}: inconsistent surrogate style")


def validate_catalog(value):
    if value.get('schema_version') != 1 or not isinstance(value.get('bots'), dict):
        raise ValueError('Expected a schema-1 opponent catalogue with a bots mapping')
    for identity, record in value['bots'].items():
        if not re.fullmatch(r'[a-z0-9_]+', identity):
            raise ValueError(f'Invalid opponent ID: {identity!r}')
        if not isinstance(record.get('name'), str) or not record['name']:
            raise ValueError(f'{identity}: missing display name')
        validate_style(identity, record.get('style', {}))
        patterns=record.get('patterns',{})
        if not isinstance(patterns,dict):
            raise ValueError(f'{identity}: invalid patterns')
        slopes=patterns.get('preflop_progress',[0]*4)
        if not isinstance(slopes,list) or len(slopes)!=4 or any(not isinstance(x,(int,float)) or not math.isfinite(x) or abs(x)>8 for x in slopes):
            raise ValueError(f'{identity}: invalid preflop progress coefficients')
        for policy in (record.get('policy'),patterns.get('sizing_policy')):
            if policy is None:
                continue
            if not isinstance(policy.get('file'), str) or not policy['file']:
                raise ValueError(f'{identity}: missing policy file')
            if any(type(policy.get(key)) is not int or policy[key] < 0 for key in ('bot', 'epoch')):
                raise ValueError(f'{identity}: invalid policy bot/epoch index')
            weight = policy.get('weight', 1)
            if not isinstance(weight, (int, float)) or not math.isfinite(weight) or not 0 <= weight <= 1:
                raise ValueError(f'{identity}: invalid policy weight')
    return value


def spec(catalog, identity):
    """Use @ rather than #, which pool files reserve for comments."""
    return f'fitted:{Path(catalog).as_posix()}@{identity}'


def record(name, profile):
    value = dict(name=name, style={key: profile['surrogate_style'][key] for key in PARAMETERS})
    if profile.get('behavior'):
        value['policy'] = deepcopy(profile['behavior'])
    return value


def write_catalog(path, bots):
    value = validate_catalog(dict(schema_version=1, bots=bots))
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n')


@lru_cache(maxsize=16)
def _read(path, mtime_ns, size):
    return validate_catalog(json.loads(Path(path).read_text()))


def load_record(path, identity):
    path = Path(path).resolve()
    stat = path.stat()
    bots = _read(str(path), stat.st_mtime_ns, stat.st_size)['bots']
    if identity not in bots:
        raise ValueError(f'{path}: unknown opponent ID {identity!r}')
    # Mutable per-game settings must never alias a cached catalogue entry.
    return deepcopy(bots[identity])
