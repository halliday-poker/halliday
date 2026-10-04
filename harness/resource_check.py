"""Run actual wire-protocol games with a restricted CPU-only candidate on Linux."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from harness import eval as harness
from macpoker.match import MatchConfig,MatchRunner
from macpoker.transport import SubprocessTransport


class MeasuredTransport(SubprocessTransport):
    def __init__(self,cmd):
        super().__init__(cmd)
        self.think_ms=0.
        self.max_ms=0.
    def act(self,view,timeout_ms):
        action,elapsed=super().act(view,timeout_ms)
        self.think_ms+=elapsed
        self.max_ms=max(self.max_ms,elapsed)
        return action,elapsed


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('bot')
    p.add_argument('--repeats',type=int,default=3)
    p.add_argument('--output',required=True)
    p.add_argument('--pool',default='sparring/competitors/from_data_groups/latest-pool.txt')
    args=p.parse_args()
    bot=harness.resolve_path(args.bot)
    lineups=[['house:call','house:random','sparring/station.py','sparring/tag.py'],
             ['house:allin','house:checkfold','sparring/maniac.py','sparring/nit.py'],
             [spec for spec,_ in harness.read_pool(Path(args.pool),[])][:5]]
    rows=[]
    cpu=min(os.sched_getaffinity(0))
    for repeat in range(args.repeats):
        for li,opponents in enumerate(lineups):
            seed=f'cpu-resource-{repeat}-{li}'
            with tempfile.TemporaryDirectory(prefix='halliday-restricted-') as root:
                cmd=['unshare','--user','--map-root-user','--mount','--net','--fork',
                     sys.executable,'-B',str(harness.ROOT/'harness/limited_bot.py'),
                     '--root',root,'--bot',str(bot),'--cpu',str(cpu)]
                candidate=MeasuredTransport(cmd)
                transports=[candidate]+[harness.TimedTransport(harness.make_bot(s,f'{seed}:{i}'),s) for i,s in enumerate(opponents)]
                cfg=MatchConfig(seats=len(transports),deals=100,offset=repeat%len(transports),seed=seed,
                                base_time_ms=30_000,increment_ms=100)
                result=MatchRunner(cfg,transports).run()
                stderr=candidate.stderr_tail()
                metrics={}
                for line in stderr.splitlines():
                    if line.startswith('RESOURCE_'):
                        key,value=line.split(' ',1)
                        metrics[key]=json.loads(value)
                rows.append(dict(seed=seed,opponents=opponents,verdicts=result.verdicts,
                                 chips=result.chips,think_ms=candidate.think_ms,max_ms=candidate.max_ms,
                                 resources=metrics,stderr=stderr))
                print(seed,result.verdicts,f'{candidate.think_ms:.1f} ms',flush=True)
    sources={str(f.relative_to(bot.parent)):hashlib.sha256(f.read_bytes()).hexdigest()
             for f in sorted(bot.parent.glob('*.py'))}
    passed=all(all(v=='OK' for v in row['verdicts']) and
               'RESOURCE_USAGE' in row['resources'] and
               row['resources']['RESOURCE_USAGE']['max_rss_kib']<512*1024 for row in rows)
    output=dict(bot=args.bot,hash=harness.bot_hash(args.bot),sources=sources,passed=passed,games=rows,
                scope='Actual SDK protocol and clocks; one CPU affinity, 512MiB virtual-memory ceiling, read-only chroot, fresh 64MiB tmpfs, private network namespace. Cooperative-code resource validation, not a hardened judge replica.')
    Path(args.output).write_text(json.dumps(output,indent=2)+'\n')
    print('PASS' if passed else 'FAIL')
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
