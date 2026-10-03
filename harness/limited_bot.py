"""Linux-only subprocess launcher, invoked inside a private user/mount/net namespace.

This validates a cooperative submission under resource limits; it is not a
security boundary for hostile code. No host mount or filesystem is modified.
"""
import argparse
import json
import os
from pathlib import Path
import resource
import subprocess
import sys


def mount(*args):
    subprocess.run(['mount', *map(str,args)], check=True, stdout=subprocess.DEVNULL)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--bot', required=True)
    parser.add_argument('--cpu', type=int, required=True)
    args=parser.parse_args()
    root=Path(args.root).resolve()
    bot=Path(args.bot).resolve()
    mount('--make-rprivate','/')
    mount('-t','tmpfs','-o','size=4m,nosuid,nodev','tmpfs',root)
    for name in ('usr','lib','lib64','etc'):
        source=Path('/')/name
        if source.exists():
            target=root/name
            target.mkdir()
            mount('--bind',source,target)
            mount('-o','remount,bind,ro',target)
    # Bind only Python dependencies and this workspace, avoiding unrelated
    # host mounts below /home and /mnt. Recursive workspace binding preserves
    # the outer sandbox's already read-only .git/.agents mount protections.
    workspace=Path(__file__).resolve().parents[1]
    sources=[Path(sys.base_prefix)]+[Path(p) for p in sys.path if p.startswith('/home/') and Path(p).is_dir()]+[workspace]
    mounted=[]
    for source in sources:
        if any(source==p or p in source.parents for p in mounted):
            continue
        target=root/str(source).lstrip('/')
        target.mkdir(parents=True,exist_ok=True)
        mount('--rbind' if source==workspace else '--bind',source,target)
        mount('-o','remount,bind,ro',target)
        mounted.append(source)
    # Make every inherited filesystem mount under the workspace read-only.
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        columns=line.split()
        target=columns[4].replace('\\040',' ')
        if target.startswith(str(root)+'/mnt/') and 'rw' in columns[5].split(','):
            mount('-o','remount,bind,ro',target)
    (root/'tmp').mkdir()
    mount('-t','tmpfs','-o','size=64m,nosuid,nodev','tmpfs',root/'tmp')
    (root/'dev').mkdir()
    for name in ('null','urandom'):
        target=root/'dev'/name
        target.touch()
        mount('--bind',Path('/dev')/name,target)
        mount('-o','remount,bind,ro',target)
    mount('-o','remount,bind,ro',root)
    os.chroot(root)
    os.chdir(bot.parent)
    os.sched_setaffinity(0,{args.cpu})
    limit=512*1024*1024
    resource.setrlimit(resource.RLIMIT_AS,(limit,limit))
    resource.setrlimit(resource.RLIMIT_FSIZE,(64*1024*1024,64*1024*1024))
    os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',
                      PYTHONDONTWRITEBYTECODE='1',TMPDIR='/tmp')
    sys.dont_write_bytecode=True
    # Fail before play if isolation does not have the requested properties.
    readonly={}
    for directory in (Path('/'),bot.parent,Path('/home'),Path('/mnt')):
        probe=directory/'.halliday-resource-probe'
        try:
            with probe.open('x'):
                pass
        except OSError as exc:
            readonly[str(directory)]=exc.errno==30  # EROFS
        else:
            probe.unlink()
            readonly[str(directory)]=False
    fs=os.statvfs('/tmp')
    tmp_bytes=fs.f_blocks*fs.f_frsize
    assert all(readonly.values()) and tmp_bytes<=64*1024*1024
    assert not list(Path('/tmp').iterdir())
    setup=dict(cpu_affinity=sorted(os.sched_getaffinity(0)),address_space_limit=limit,
               tmp_bytes=tmp_bytes,tmp_initially_empty=True,readonly=readonly,
               network='private network namespace; no configured external interfaces')
    print('RESOURCE_SETUP '+json.dumps(setup),file=sys.stderr,flush=True)
    sys.path.insert(0,str(bot.parent))
    sys.argv=[str(bot)]
    try:
        from macpoker.sdk import load_bot_from_file,run_bot
        run_bot(load_bot_from_file(str(bot)))
    finally:
        usage=resource.getrusage(resource.RUSAGE_SELF)
        print('RESOURCE_USAGE '+json.dumps(dict(max_rss_kib=usage.ru_maxrss,
              user_s=usage.ru_utime,system_s=usage.ru_stime)),file=sys.stderr,flush=True)


if __name__=='__main__':
    main()
