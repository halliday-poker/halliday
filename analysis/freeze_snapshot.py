"""Freeze and validate a completed collector upload without changing its files."""
import argparse
from collections import Counter,defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess


def fingerprint(path, reject_nul=False):
    digest = sha256()
    offset = 0
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            if reject_nul and b'\0' in chunk:
                raise ValueError(f'{path}: NUL at byte {offset + chunk.index(0)}; upload is incomplete or corrupt')
            digest.update(chunk)
            offset += len(chunk)
    return digest.hexdigest()


def freeze(source, directory, recover_state=False):
    destination = directory/'source'
    destination.mkdir(parents=True, exist_ok=False)
    required = ('actions.jsonl', 'matches.json', 'state.json')
    names = list(required) + [n for n in ('match-meta.json', 'names-cache.json') if (source/n).exists()]
    before = {name: (source/name).stat() for name in names}
    for name in names:
        shutil.copyfile(source/name, destination/name)
    files = {}
    for name in names:
        old, now = before[name], (source/name).stat()
        if (old.st_size, old.st_mtime_ns) != (now.st_size, now.st_mtime_ns):
            raise ValueError(f'{name} changed during copying; wait for the upload to finish')
        files[name] = dict(bytes=old.st_size, sha256=fingerprint(destination/name, True),
                           source_mtime_ns=old.st_mtime_ns)
    metadata = json.loads((destination/'matches.json').read_text())
    state = json.loads((destination/'state.json').read_text())
    known = {m['id'] for m in metadata}
    if len(known) != len(metadata):
        raise ValueError('Duplicate match metadata')
    counts = Counter()
    orphan_events=defaultdict(list)
    with (destination/'actions.jsonl').open() as stream:
        for number, line in enumerate(stream, 1):
            try:
                event = json.loads(line)
                counts[event['match']] += 1
                if recover_state and state['collected'].get(event['match'],{}).get('status')!='collected':
                    orphan_events[event['match']].append(event)
            except (ValueError, KeyError) as exc:
                raise ValueError(f'Invalid action record at line {number}') from exc
    missing = sorted(set(counts) - known)
    no_state = sorted(mid for mid in counts if state['collected'].get(mid, {}).get('status') != 'collected')
    recovered=[]
    if no_state and recover_state and not missing:
        import sys
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
        from opponent_model.data import reconstruct_hand
        by_id={m['id']:m for m in metadata}
        for mid in no_state:
            item=by_id[mid];events=orphan_events[mid];groups=defaultdict(list)
            for event in events:groups[event['hand']].append(event)
            if sorted(groups)!=list(range(len(groups))) or (item['kind']=='ladder' and len(groups)!=100):
                raise ValueError(f'{mid}: cannot recover incomplete replay state')
            totals=[0]*len(item['names']);stats=defaultdict(lambda:[0,0,0,0])
            for hand,group in sorted(groups.items()):
                reconstruct_hand(group,item,0,stats)
                end=group[-1]
                if end.get('deltas_bot_names')!=item['names'] or sum(end['deltas_by_bot'])!=0:
                    raise ValueError(f'{mid}: cannot recover inconsistent settlement')
                totals=[a+b for a,b in zip(totals,end['deltas_by_bot'])]
            if totals!=item['chips'] or not isinstance(item.get('collected_at'),(int,float)):
                raise ValueError(f'{mid}: cannot recover inconsistent metadata')
            state['collected'][mid]=dict(status='collected',collected_at=item['collected_at'],
                source='recovered from complete normalized replay and metadata; original collector state preserved')
            recovered.append(dict(match=mid,hands=len(groups),records=len(events),chips=totals))
        shutil.copyfile(destination/'state.json',destination/'state-collector.json')
        files['state-collector.json']=dict(files['state.json'])
        (destination/'state.json').write_text(json.dumps(state,indent=2)+'\n')
        files['state.json']=dict(bytes=(destination/'state.json').stat().st_size,
            sha256=fingerprint(destination/'state.json',True),derived=True,
            original_collector_sha256=files['state-collector.json']['sha256'])
        no_state=[]
    if missing or no_state:
        raise ValueError(f'Metadata/state upload is incomplete: {len(missing)} missing metadata, {len(no_state)} missing collected state')
    result = dict(frozen_at=datetime.now(timezone.utc).isoformat(), source=str(source), files=files,
                  rows=sum(counts.values()), matches_with_actions=len(counts), metadata_matches=len(metadata),
                  metadata_without_actions=sorted(known-set(counts)), missing_metadata=missing, missing_state=no_state,
                  recovered_collector_state=recovered)
    (directory/'snapshot-manifest.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def baseline(ref, destination):
    commit = subprocess.check_output(['git', 'rev-parse', ref], text=True).strip()
    files = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', commit, 'bot'], text=True).splitlines()
    if not files:
        raise ValueError(f'No bot tree at {ref}')
    destination.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for name in files:
        relative = Path(name).relative_to('bot')
        path = destination/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        contents = subprocess.check_output(['git', 'show', f'{commit}:{name}'])
        path.write_bytes(contents)
        hashes[str(relative)] = sha256(contents).hexdigest()
    return dict(main_commit=commit, baseline=str(destination), files=hashes,
                scope='Exact bot tree from the supplied Git commit; no analysis-branch engine modifications.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--baseline-ref')
    parser.add_argument('--baseline-output', type=Path)
    parser.add_argument('--recover-state',action='store_true',help='Recover missing collector-state entries only from fully validated complete replays; preserve original state')
    args = parser.parse_args()
    if bool(args.baseline_ref) != bool(args.baseline_output):
        parser.error('Supply both --baseline-ref and --baseline-output')
    result = freeze(args.source, args.directory,args.recover_state)
    if args.baseline_ref:
        record = baseline(args.baseline_ref, args.baseline_output)
        (args.directory/'baseline-manifest.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps(result, indent=2))
