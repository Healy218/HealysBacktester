#!/usr/bin/env python3
"""Resource-only parallel consumer of the frozen V7 archive plan.

Reuses the original byte-comparison, publication and reclamation functions.
Local-source shards compress concurrently with one zstd-22 worker per shard.
External-source shards stay sequential to avoid HDD seek contention.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import fcntl
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import archive_v7_cold as cold


def execute_groups(groups, workers, completed=0, total=None):
    """Bound in-flight work and stop submitting after any failed integrity check."""
    results = []
    queue = iter(groups)
    total = total or len(groups)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = {}
        def submit():
            try:
                group = next(queue)
            except StopIteration:
                return False
            pending[pool.submit(cold.pack, group, 1)] = group['id']
            return True
        for _ in range(workers):
            if not submit():
                break
        while pending:
            cold.progress('archiving', consumer='parallel-v1',
                          active_groups=sorted(pending.values()), completed_groups=completed,
                          total_groups=total, archive_workers=workers, threads_per_archive=1)
            finished, _ = wait(pending, timeout=15, return_when=FIRST_COMPLETED)
            # Evaluate every finished future before admitting additional work.
            batch = [future.result() for future in finished]
            for future in finished:
                del pending[future]
            results.extend(batch)
            completed += len(batch)
            for _ in finished:
                submit()
    return results


def run(workers, reclaim):
    cold.drive()
    cold.archive.ROOT = Path('/')
    plan_path = cold.STATE / 'plan.json'
    plan = json.loads(plan_path.read_text())
    cold.validate_plan(plan)
    if cold.archive.sha(plan_path) != cold.archive.sha(cold.DEST / 'manifests/plan.json'):
        raise ValueError('External plan differs; initialize with the original consumer first')
    binding = dict(schema='v7-cold-archive-parallel-consumer-v1',
                   plan_sha256=cold.archive.sha(plan_path),
                   consumer_sha256=cold.archive.sha(Path(__file__)),
                   original_archiver_sha256=plan['source_script_sha256'],
                   source_threads=1, external_workers=1)
    receipt = cold.STATE / 'consumer-parallel-v1.json'
    if receipt.exists() and json.loads(receipt.read_text()) != binding:
        raise ValueError('Parallel consumer binding changed')
    cold.save(receipt, binding)
    cold.save(cold.DEST / 'manifests/consumer-parallel-v1.json', binding)
    shutil.copy2(__file__, cold.DEST / 'manifests/archive_v7_cold_parallel.py')
    local, external = [], []
    for group in plan['groups']:
        paths = group['members'] + group['shallow']
        (external if any(p.startswith('run/media/') for p in paths) else local).append(group)
    results = execute_groups(local, workers, total=len(plan['groups']))
    results += execute_groups(external, 1, completed=len(results), total=len(plan['groups']))
    cold.validate_plan(plan)
    result = dict(status='all-archives-verified', at=cold.now(), groups=len(results),
                  plan_sha256=cold.archive.sha(plan_path),
                  archive_bytes=sum(r['archive_bytes'] for r in results),
                  retired_files=0, consumer='parallel-v1')
    cold.save(cold.DEST / 'VERIFIED.json', result)
    cold.save(cold.STATE / 'VERIFIED.json', result)
    if reclaim:
        result['retired_files'] = cold.retire(plan)
    result.update(status='complete', at=cold.now(), local_free=shutil.disk_usage(cold.ROOT).free,
                  external_free=shutil.disk_usage(cold.DEST).free)
    cold.save(cold.DEST / 'COMPLETE.json', result)
    cold.save(cold.STATE / 'COMPLETE.json', result)
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
            cold.progress('failed', consumer='parallel-v1', error=str(exc))
            raise


if __name__ == '__main__':
    main()
