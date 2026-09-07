"""Resume a pinned freeze with a measured, automatically reviewed fifth slot.

Only orchestration is replaced; research_local's coverage, campaign fingerprint,
lock, full-shard validation and final merge remain the original implementation.
"""
import argparse
from collections import deque
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from scripts import research_local as research
from scripts.run_v6_parallel_freeze import available_bytes, write_json, lock


def baseline_rate(history):
    records = [r for r in history if sum(p['stage'] == 'freeze' for p in r['processes']) == 4]
    if len(records) < 2:
        raise ValueError('at least two four-worker observations required')
    end = records[-1]
    end_time = datetime.fromisoformat(end['time_utc'])
    records = [r for r in records if 0 <= (end_time-datetime.fromisoformat(r['time_utc'])).total_seconds() <= 7200]
    first = records[0]
    hours = (end_time-datetime.fromisoformat(first['time_utc'])).total_seconds()/3600
    gain = end['counts']['freeze_shards']-first['counts']['freeze_shards']
    if hours < .5 or gain <= 0:
        raise ValueError('insufficient measured four-worker baseline')
    return {'average_per_hour': gain/hours, 'hours': hours, 'completed': gain,
            'start_utc': first['time_utc'], 'end_utc': end['time_utc']}


def reviewed_workers(rate, baseline):
    return 5 if rate > baseline else 4


def memory_pressure():
    full = next(l for l in Path('/proc/pressure/memory').read_text().splitlines() if l.startswith('full '))
    return float(dict(v.split('=') for v in full.split()[1:])['avg60'])


def process_alive(pid, start):
    try:
        fields = (Path('/proc')/str(pid)/'stat').read_text().rsplit(')', 1)[1].split()
        return fields[0] != 'Z' and fields[19] == str(start)
    except FileNotFoundError:
        return False


class Trial:
    def __init__(self, root, baseline, hours):
        self.root, self.baseline, self.hours = root, baseline, hours

    def status(self, **values):
        write_json(self.root/'status.json', {'time_utc': datetime.now(timezone.utc).isoformat(),
                   'supervisor_pid': os.getpid(), 'baseline': self.baseline, **values})

    def parallel(self, commands, *, workers, environment, cwd, log_dir, labels):
        from nn_meta.feature_contract import CONTRACT_VERSION
        from nn_meta import config
        if any('nn_meta.freeze_baseline' not in cmd for cmd in commands):
            raise ValueError('trial supports freeze only')
        pending = deque()
        retained = {}
        for command, label in zip(commands, labels, strict=True):
            out = Path(command[command.index('--out')+1])
            if out.exists():
                research.validate_shards([out], [label], CONTRACT_VERSION)
                retained[str(out)] = hashlib.sha256(out.read_bytes()).hexdigest()
            else:
                pending.append((command, label, out))
        write_json(self.root/'retained-shards.json', retained)
        started = time.monotonic()
        started_utc = datetime.now(timezone.utc)
        target, completed, decision = 5, 0, None
        active = {}
        pressure_since = None
        try:
            while pending or active:
                elapsed = time.monotonic()-started
                available = available_bytes()/1024**3
                pressure = memory_pressure()
                pressure_since = (pressure_since or time.monotonic()) if pressure > 5 else None
                if target == 5 and (available < 4 or (pressure_since and time.monotonic()-pressure_since >= 120)):
                    target, decision = 4, 'return_to_four_memory_headroom'
                if decision is None and elapsed >= self.hours*3600:
                    rate = completed/(elapsed/3600)
                    target = reviewed_workers(rate, self.baseline['average_per_hour'])
                    decision = 'keep_five_improved_rate' if target == 5 else 'return_to_four_no_improvement'
                    write_json(self.root/'review.json', {'decision': decision, 'workers': target,
                               'baseline_per_hour': self.baseline['average_per_hour'],
                               'trial_per_hour': rate, 'elapsed_hours': elapsed/3600, 'completed': completed,
                               'time_utc': datetime.now(timezone.utc).isoformat()})
                while pending and len(active) < target and available >= 4:
                    command, label, out = pending.popleft()
                    stream = (log_dir/f'{label}.log').open('a')
                    process = subprocess.Popen(command, cwd=cwd, env=environment,
                                               stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT)
                    active[label] = process, stream, out
                self.status(phase='running', target_workers=target, active={s:p.pid for s,(p,_,_) in active.items()},
                            started_utc=started_utc.isoformat(), trial_seconds=self.hours*3600,
                            elapsed_seconds=elapsed, completed=completed, retained=len(retained),
                            average_per_hour=completed/(elapsed/3600) if elapsed else 0,
                            decision=decision, available_ram_gib=round(available,2), memory_pressure_avg60=pressure)
                for label, (process, stream, out) in list(active.items()):
                    code = process.poll()
                    if code is None:
                        continue
                    stream.close()
                    del active[label]
                    if code:
                        raise ValueError(f'freeze worker {label} failed: {code}')
                    research.validate_shards([out], [label], CONTRACT_VERSION)
                    completed += 1
                if pending or active:
                    time.sleep(5)
        finally:
            # Drain running symbols on supervisor failure/interrupt; do not
            # kill their current searches or submit any further work.
            for process, stream, _ in active.values():
                process.wait()
                stream.close()
        if any(hashlib.sha256(Path(p).read_bytes()).hexdigest()!=digest for p,digest in retained.items()):
            raise ValueError('retained completed shards changed')
        self.status(phase='merging', target_workers=target, decision=decision, completed=completed,
                    retained=len(retained), active={})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', required=True, type=research.name)
    parser.add_argument('--drain-pid', type=int, required=True)
    parser.add_argument('--drain-start', required=True)
    parser.add_argument('--hours', type=float, default=2)
    args = parser.parse_args()
    if not 0 < args.hours <= 24:
        parser.error('hours must be positive and at most 24')
    repo = Path(__file__).resolve().parents[1]
    prep = repo/'nn_meta/expanded_inputs'/args.campaign
    root = prep/'full-run/worker-trial'
    history = [json.loads(l) for l in (repo/'logs/v6-progress'/args.campaign/'history.jsonl').read_text().splitlines()]
    baseline = baseline_rate(history)
    with lock(root/'supervisor.lock'):
        snapshot = root/'source.txt'
        source = Path(__file__).read_bytes()
        if snapshot.exists():
            raise ValueError('trial already exists; inspect before resuming')
        snapshot.write_bytes(source)
        write_json(root/'baseline.json', baseline)
        trial = Trial(root, baseline, args.hours)
        if not process_alive(args.drain_pid, args.drain_start):
            raise ValueError('original launcher identity changed')
        proc = Path('/proc')/str(args.drain_pid)
        command = (proc/'cmdline').read_bytes().decode().split('\0')
        if 'scripts.research_local' not in command or '--campaign' not in command or command[command.index('--campaign')+1] != args.campaign:
            raise ValueError('not the expected campaign launcher')
        affinity = os.sched_getaffinity(args.drain_pid)
        # Inherit only explicit research settings, never save credential values.
        old_env = dict(item.split('=',1) for item in (proc/'environ').read_bytes().decode().split('\0') if '=' in item)
        environment = {k:v for k,v in old_env.items() if k.startswith('NN_META_') or k in
                       ('MPLCONFIGDIR','NUMBA_CACHE_DIR','PYTHONDONTWRITEBYTECODE','OMP_NUM_THREADS',
                        'OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMBA_NUM_THREADS')}
        write_json(root/'environment.json', environment)
        trial.status(phase='draining_four_workers', original_launcher=args.drain_pid, target_workers=4)
        os.kill(args.drain_pid, signal.SIGINT)
        while process_alive(args.drain_pid, args.drain_start):
            time.sleep(5)
        os.environ.update(environment)
        os.sched_setaffinity(0, affinity)
        trial.status(phase='preflight', target_workers=5)
        research.parallel_commands = trial.parallel
        code = research.main(['--campaign',args.campaign,'--pool','v6','--stage','freeze','--workers','5','--run'])
        if Path(__file__).read_bytes() != source:
            raise ValueError('trial controller changed during freeze')
        write_json(root/'result.json', {'returncode':code,'freeze_completed':code==0})
        trial.status(phase='complete' if code==0 else 'failed', returncode=code, active={})
        return code


if __name__ == '__main__':
    raise SystemExit(main())
