"""Create isolated Halliday experiments from the preserved baseline copy."""
from hashlib import sha256
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'snapshots/analysis_baseline_20261004'
VARIANTS={
    'river_guard':dict(range_bluff_floor=.18,range_call_margin_river=.05,range_reraise_margin=.06),
    'turn_discipline':dict(range_call_margin_turn=.06,range_call_margin_river=.04,range_large_bet_margin=.05),
    'shove_callers':dict(shover_min_rate=.50,shover_call_margin=.05),
    'mixed_35':dict(bluff_frequency=.35),
    'mixed_65':dict(bluff_frequency=.65),
    'value_pressure':dict(cbet_pot_fraction=.75,late_pot_fraction=1.25,raise_pot_fraction=.9),
    'small_ball':dict(cbet_pot_fraction=.65,late_pot_fraction=.70,raise_pot_fraction=.6),
    'mixed_00':dict(bluff_frequency=0.),
    'mixed_85':dict(bluff_frequency=.85),
    'pressure_mixed_65':dict(cbet_pot_fraction=.75,late_pot_fraction=1.25,raise_pot_fraction=.9,bluff_frequency=.65),
    'shove_ranges_only':{},
    'field_mean_priors':dict(range_prior_vpip=.298,range_prior_pfr=.1745,range_prior_threebet=.072),
    'field_median_priors':dict(range_prior_vpip=.2211,range_prior_pfr=.1368,range_prior_threebet=.0424),
    'fast_adaptation':dict(range_prior_hands=4,range_showdown_prior=2),
}


def build(names=None):
    if not BASE.is_dir():raise ValueError('Preserve the baseline bot before creating variants')
    result={}
    baseline_hashes={p.name:sha256(p.read_bytes()).hexdigest() for p in BASE.glob('*.py')}
    for name,changes in VARIANTS.items():
        if names and name not in names:continue
        destination=ROOT/'analysis/candidates'/name
        if destination.exists():
            raise ValueError(f'Will not overwrite an existing experiment: {destination}')
        shutil.copytree(BASE,destination,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        params=destination/'params.py'
        params.write_text(params.read_text()+f'\n\n# Offline experiment; selected only through paired evaluation.\nDEFAULT_PARAMS = MappingProxyType({{**DEFAULT_PARAMS, **{changes!r}}})\n')
        if name in ('shove_callers','shove_ranges_only'):
            path=destination/'preflop.py'
            source=path.read_text()
            original='state.stacks[shover] == 0 and not called and equity is not None'
            replacement='state.stacks[shover] == 0 and (not called or ranged) and equity is not None'
            if source.count(original)!=1:raise ValueError('Baseline preflop decision changed; inspect the experiment')
            source=source.replace(original,replacement)
            source=source.replace('# Not when someone else has already called the shove.',
                                  '# With a cold caller, require separately tracked opponent ranges.')
            path.write_text(source)
            # A frequent shover receives an any-two range only if it actually
            # shoved in this hand. A caller retains its action-conditioned range.
            main=destination/'main.py'
            source=main.read_text()
            original='return [None if is_shover(profile_of(state, seat, self.opponents.profiles), p) else r\n                for seat, r in zip(opponents, ranges)]'
            replacement=('shoved = {a[1] for a in state.history if a[0] == "preflop" and a[2] == "raise" and state.stacks[a[1]] == 0 and len(self.opponents._start_stacks) > a[1] and a[3] >= self.opponents._start_stacks[a[1]]}\n'
                         '        return [None if seat in shoved and is_shover(profile_of(state, seat, self.opponents.profiles), p) else r\n'
                         '                for seat, r in zip(opponents, ranges)]')
            if source.count(original)!=1:raise ValueError('Baseline range override changed; inspect the experiment')
            main.write_text(source.replace(original,replacement))
        record=dict(name=name,baseline=str(BASE.relative_to(ROOT)),baseline_sha256=baseline_hashes,parameter_overrides=changes,
                    status='unselected experiment; no performance improvement established',
                    sampling='mixed variants use the existing private visible-spot hash for repeatable weighted bluff decisions; value logic is unchanged')
        (destination/'variant.json').write_text(json.dumps(record,indent=2))
        result[name]=str(destination.relative_to(ROOT))
    manifest=ROOT/'analysis/results/refresh-20261004/strategy-variants.json'
    prior=json.loads(manifest.read_text()) if manifest.exists() else {}
    manifest.write_text(json.dumps(prior|result,indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only',nargs='+',choices=sorted(VARIANTS))
    build(parser.parse_args().only)
