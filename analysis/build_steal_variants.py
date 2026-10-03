"""Build public-evidence steal experiments from the frozen merged-main bot."""
from hashlib import sha256
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'snapshots/analysis_main_20261004'
COMMON = dict(steal_min_faced=6, steal_prior_weight=8, steal_fold_prior=.65,
              steal_min_ev=.15, steal_frequency=1., steal_max_opponents=2)
VARIANTS = {
    'adaptive_steal': {},
    'mixed_steal_65': dict(steal_frequency=.65),
    'adaptive_steal_cutoff': dict(steal_max_opponents=3),
    'minimum_steal': dict(steal_open_bb=2.0),
}


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Frozen baseline changed; inspect the candidate patch')
    return source.replace(old, new)


def build(names=None):
    for name, changes in VARIANTS.items():
        if names and name not in names:
            continue
        dest = ROOT/'analysis/candidates'/name
        if dest.exists():
            raise ValueError(f'Refusing to overwrite {dest}')
        shutil.copytree(BASE, dest, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copyfile(ROOT/'analysis/steal_policy.py', dest/'steals.py')
        params = COMMON | changes
        if 'steal_open_bb' in changes:
            path = dest/'steals.py'
            source = replace_once(path.read_text(), "target = round(params['big_blind'] * params['open_bb'])",
                                  "target = round(params['big_blind'] * params['steal_open_bb'])")
            path.write_text(source)
        path = dest/'params.py'
        path.write_text(path.read_text()+f'\n# Isolated adaptive steal experiment.\nDEFAULT_PARAMS = MappingProxyType({{**DEFAULT_PARAMS, **{params!r}}})\n')
        path = dest/'main.py'
        source = replace_once(path.read_text(), 'class MyBot(Bot):',
                              'if __package__:\n    from .steals import StealTracker\nelse:\n    from steals import StealTracker\n\n\nclass MyBot(Bot):')
        source = replace_once(source, 'self.opponents = OpponentTracker()', 'self.opponents = StealTracker()')
        path.write_text(source)
        path = dest/'preflop.py'
        source = replace_once(path.read_text(), '    from .params import margin',
                              '    from .params import margin\n    from .steals import should_steal')
        source = replace_once(source, '    from params import margin',
                              '    from params import margin\n    from steals import should_steal')
        if 'steal_open_bb' in changes:
            source = replace_once(source,
                                  '        return passive\n\n    # The whitelist',
                                  '        if should_steal(state, opp_profiles, params):\n'
                                  '            return "raise", round(bb * params["steal_open_bb"])\n'
                                  '        return passive\n\n    # The whitelist')
        else:
            source = replace_once(source, '        if hand in opening:',
                                  '        if hand in opening or should_steal(state, opp_profiles, params):')
        path.write_text(source)
        record = dict(name=name, baseline=str(BASE.relative_to(ROOT)),
                      baseline_sha256={p.name:sha256(p.read_bytes()).hexdigest() for p in BASE.glob('*.py')},
                      parameter_overrides=params, status='unselected experiment',
                      change='Widen only unopened late-position raises after sufficient in-game small-open fold evidence; original opening hands retain their actions.',
                      caveat='Product of marginal defense probabilities is approximate; the screening EV omits later betting.')
        (dest/'variant.json').write_text(json.dumps(record, indent=2)+'\n')
        print(dest.relative_to(ROOT))


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only',nargs='+',choices=sorted(VARIANTS))
    build(parser.parse_args().only)
