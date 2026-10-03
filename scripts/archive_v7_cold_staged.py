#!/usr/bin/env python3
"""V7 archive I/O consumer v2: bounded SSD staging, serialized HDD publication.

Original plan, zstd-22, full comparisons and all-before-retirement are retained.
Oversized or externally sourced shards use a later serial direct-stream phase.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import archive_v7_cold as cold

LOCAL_RESERVE = 10 * 1024**3
STAGING_LIMIT = 8 * 1024**3
IO_LOCK = threading.Lock()


class StageLimit(Exception):
    """Retry this shard in the later direct phase; never retire it here."""


class Budget:
    def __init__(self, capacity):
        self.capacity, self.used = capacity, 0
        self.condition = threading.Condition()

    @contextmanager
    def reserve(self, amount):
        if amount > self.capacity:
            raise StageLimit('Shard exceeds total staging allowance')
        with self.condition:
            self.condition.wait_for(lambda: self.used + amount <= self.capacity)
            self.used += amount
        try:
            yield
        finally:
            with self.condition:
                self.used -= amount
                self.condition.notify_all()


def compress(group, stage, bound):
    args = ['tar', '--format=pax', '--pax-option=delete=atime,delete=ctime',
            '--xattrs', '--acls', '-I', 'zstd --ultra -22 -T1', '-cf', str(stage)]
    args += cold.archive.tar_args(group, cold.STATE)
    with (cold.STATE / f'{group["id"]}.pack.log').open('w') as log:
        process = subprocess.Popen(args, cwd='/', stdout=log, stderr=log, start_new_session=True)
        try:
            while process.poll() is None:
                if shutil.disk_usage(cold.ROOT).free < LOCAL_RESERVE:
                    raise RuntimeError('SSD reached its 10-GiB free-space reserve')
                if stage.exists() and stage.stat().st_size > bound:
                    raise StageLimit('Actual staged bytes exceed reservation')
                time.sleep(0.5)
            if process.returncode:
                raise RuntimeError(f'Compression failed: {group["id"]}')
            if stage.stat().st_size > bound:
                raise StageLimit('Actual staged bytes exceed reservation')
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL); process.wait()


def transfer(stage, partial):
    cold.drive()
    with stage.open('rb') as source, partial.open('wb') as dest:
        while block := source.read(4 * 1024**2):
            cold.drive()
            dest.write(block)
        dest.flush(); os.fsync(dest.fileno())


def pack_staged(group, budget):
    name = group['id']
    receipt = cold.STATE / f'{name}.verified.json'
    if receipt.exists():
        with IO_LOCK:
            return cold.pack(group, 1)
    before = cold.archive.fingerprint(group['members'], group['shallow'])
    # Reservation estimate includes generous tar headers; the actual byte limit
    # is enforced during compression, so an underestimate defers without harm.
    bound = int(before['bytes'] * 1.02) + sum(before[k] for k in ('files', 'directories', 'symlinks')) * 16384 + 1024**2
    if bound > budget.capacity:
        return None
    stage = cold.STATE / 'staging' / f'{name}.tar.zst.partial'
    stage.parent.mkdir(exist_ok=True)
    with budget.reserve(bound):
        try:
            retiring = cold.candidates(group)
            compress(group, stage, bound)
            if before != cold.archive.fingerprint(group['members'], group['shallow']):
                raise ValueError(f'Source changed during staged packing: {name}')
            with stage.open('rb') as f:
                os.fsync(f.fileno())
            checksum = cold.archive.sha(stage)
            with IO_LOCK:
                partial = cold.DEST / 'data' / f'{name}.tar.zst.partial'
                transfer(stage, partial)
                if cold.archive.sha(partial) != checksum:
                    raise ValueError(f'External transfer checksum mismatch: {name}')
                compare = cold.STATE / f'{name}.compare.log'
                cold.guarded_run(['tar', '--xattrs', '--acls', '-I', 'zstd -d -T1',
                                  '-df', str(partial)], compare)
                if compare.stat().st_size:
                    raise ValueError(f'Unexpected comparison diagnostics: {compare}')
                actual = cold.archive.archive_census(partial)
                if actual != {key: before[key] for key in actual}:
                    raise ValueError(f'Archive member census mismatch: {name}')
                if before != cold.archive.fingerprint(group['members'], group['shallow']):
                    raise ValueError(f'Source changed during verification: {name}')
                for item in retiring:
                    if cold.stamp(Path('/') / item['path']) != item['stamp']:
                        raise ValueError('Retirement candidate changed')
                output = cold.DEST / 'data' / f'{name}.tar.zst'
                partial.replace(output)
                result = dict(id=name, state='full-source-compare-and-member-census-verified',
                              source=before, members=actual, archive_bytes=output.stat().st_size,
                              sha256=checksum, retire_candidates=retiring, verified_at=cold.now(),
                              consumer='staged-v2')
                cold.save(cold.DEST / 'manifests' / receipt.name, result)
                cold.save(receipt, result)
            print(json.dumps(dict(id=name, archive_bytes=result['archive_bytes'], state='verified-staged-v2')), flush=True)
            return result
        except StageLimit:
            return None
        finally:
            # These are exclusively this consumer's rebuildable staging files.
            stage.unlink(missing_ok=True)


def execute(groups, workers, budget, total):
    results, deferred = [], []
    queue = iter(groups)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = {}
        def submit():
            group = next(queue, None)
            if group is not None:
                pending[pool.submit(pack_staged, group, budget)] = group
        for _ in range(workers):
            submit()
        while pending:
            cold.progress('archiving', consumer='staged-v2', active_groups=sorted(g['id'] for g in pending.values()),
                          completed_groups=len(results), total_groups=total, archive_workers=workers,
                          threads_per_archive=1, staging_reserved_bytes=budget.used,
                          staging_limit_bytes=budget.capacity, deferred_groups=len(deferred))
            done, _ = wait(pending, timeout=15, return_when=FIRST_COMPLETED)
            batch = [(future, future.result()) for future in done]
            for future, result in batch:
                group = pending.pop(future)
                if result is None:
                    deferred.append(group)
                else:
                    results.append(result)
            for _ in done:
                submit()
    return results, deferred


def run(workers, reclaim):
    cold.drive(); cold.archive.ROOT = Path('/')
    plan_path = cold.STATE / 'plan.json'
    plan = json.loads(plan_path.read_text()); cold.validate_plan(plan)
    if cold.archive.sha(plan_path) != cold.archive.sha(cold.DEST / 'manifests/plan.json'):
        raise ValueError('External plan differs')
    binding = dict(schema='v7-cold-archive-staged-consumer-v2', plan_sha256=cold.archive.sha(plan_path),
                   consumer_sha256=cold.archive.sha(Path(__file__)), original_archiver_sha256=plan['source_script_sha256'],
                   staging_limit_bytes=STAGING_LIMIT, local_reserve_bytes=LOCAL_RESERVE)
    receipt = cold.STATE / 'consumer-staged-v2.json'
    if receipt.exists() and json.loads(receipt.read_text()) != binding:
        raise ValueError('Staged consumer binding changed')
    cold.save(receipt, binding); cold.save(cold.DEST / 'manifests' / receipt.name, binding)
    shutil.copy2(__file__, cold.DEST / 'manifests/archive_v7_cold_staged.py')
    staging = cold.STATE / 'staging'; staging.mkdir(exist_ok=True)
    for p in staging.glob('*.tar.zst.partial'):
        if p.is_symlink() or not p.name.split('.')[0].isdigit():
            raise ValueError('Unexpected staging entry')
        p.unlink()
    capacity = min(STAGING_LIMIT, shutil.disk_usage(cold.ROOT).free - LOCAL_RESERVE - 1024**3)
    if capacity <= 0:
        raise RuntimeError('Insufficient SSD staging headroom')
    local, external = [], []
    for group in plan['groups']:
        (external if any(p.startswith('run/media/') for p in group['members'] + group['shallow']) else local).append(group)
    results, deferred = execute(local, workers, Budget(capacity), len(plan['groups']))
    for group in deferred + external:
        cold.progress('archiving', consumer='staged-v2', phase='serial-direct', active_groups=[group['id']],
                      completed_groups=len(results), total_groups=len(plan['groups']), threads_per_archive=workers)
        results.append(cold.pack(group, workers))
    cold.validate_plan(plan)
    result = dict(status='all-archives-verified', at=cold.now(), groups=len(results),
                  plan_sha256=cold.archive.sha(plan_path), archive_bytes=sum(r['archive_bytes'] for r in results),
                  retired_files=0, consumer='staged-v2')
    cold.save(cold.DEST / 'VERIFIED.json', result); cold.save(cold.STATE / 'VERIFIED.json', result)
    if reclaim:
        result['retired_files'] = cold.retire(plan)
    result.update(status='complete', at=cold.now(), local_free=shutil.disk_usage(cold.ROOT).free,
                  external_free=shutil.disk_usage(cold.DEST).free)
    cold.save(cold.DEST / 'COMPLETE.json', result); cold.save(cold.STATE / 'COMPLETE.json', result)
    cold.progress('complete', **{k: v for k, v in result.items() if k != 'status'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, required=True)
    parser.add_argument('--reclaim', action='store_true')
    args = parser.parse_args()
    if args.workers < 1:
        parser.error('workers must be positive')
    with (cold.STATE / 'archive.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            run(args.workers, args.reclaim)
        except Exception as exc:
            cold.progress('failed', consumer='staged-v2', error=str(exc))
            raise


if __name__ == '__main__':
    main()
