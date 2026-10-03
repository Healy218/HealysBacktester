#!/usr/bin/env python3
"""Resumable, lossless V7 cold archive. Never follow source symlinks.

Archive all selected roots before reclaiming verified large local V7 files.
External originals and local files <=1 MiB remain available. No research runs.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import archive_v6_inputs as archive

MOUNT = Path('/run/media/healy/MRHA')
DEST = MOUNT / 'v7'
STATE = ROOT / 'nn_meta/validation/v7-cold-archive-20261002-r0'
RESERVE = 20 * 1024**3
KEEP = 1024**2


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def save(path, value):
    archive.save(path, value)


def drive():
    archive.check_drive(MOUNT)
    if shutil.disk_usage(MOUNT).free < RESERVE:
        raise RuntimeError('MRHA reached its 20-GiB free-space reserve')


def relative(path):
    return str(path.absolute().relative_to('/'))


def entries(group):
    for member in group['members']:
        path = Path('/') / member
        yield path
        if path.is_dir() and not path.is_symlink():
            for base, dirs, files in os.walk(path, followlinks=False):
                for name in sorted(dirs + files):
                    yield Path(base) / name


def stamp(path):
    s = path.lstat()
    return [s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns]


def candidates(group):
    """Only dedicated V7 validation payloads are retired; inputs remain readable.

    Raw data already mostly lives on MRHA. Keep its remaining local receipts,
    symlinks and payloads, research plans, source, logs and all shared trees.
    """
    prefix = ROOT / 'nn_meta/validation'
    result = []
    for path in entries(group):
        s = path.lstat()
        if (path.is_relative_to(prefix) and not path.is_relative_to(STATE) and stat.S_ISREG(s.st_mode)
                and s.st_size > KEEP):
            result.append(dict(path=relative(path), stamp=stamp(path),
                               sha256=archive.sha(path)))
    return result


def guarded_run(args, log):
    drive()
    with log.open('w') as output:
        process = subprocess.Popen(args, cwd='/', stdout=output, stderr=output,
                                   start_new_session=True)
        try:
            while process.poll() is None:
                drive()
                time.sleep(1)
            if process.returncode:
                raise RuntimeError(f'Command failed ({process.returncode}): {log}')
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()


def source_roots():
    roots = [STATE / 'source-snapshot']
    roots += sorted(p for p in (ROOT / 'nn_meta/validation').glob('v7*') if p != STATE)
    roots += sorted((ROOT / 'nn_meta/research_plans').glob('v7*'))
    roots += [ROOT / 'nn_meta/data_v7']
    roots += [MOUNT / 'HealysBacktester/sealed-v7-payloads-20260929',
              MOUNT / 'HealysBacktester/v7-entry-campaign-20260927']
    return roots


def make_plan():
    drive()
    groups = []
    # Subdivide the largest roots at stable existing boundaries, keeping parent
    # directory metadata in shallow-only groups. No cross-shard hardlinks are
    # emitted: each tar invocation stores all its own regular file bytes.
    split = {'v7-2-full-catalog-20260922-rebuild-5-15-30',
             'v7-3-scheduler-20260925', 'v7-execution-campaign-20260928-r1',
             'v7-required-inputs-20261002-perf-r0', 'v7-required-inputs-20260930-r0',
             'v7-performance-20261002-r0', 'sealed-v7-payloads-20260929'}
    def add(members, shallow=()):
        groups.append(dict(id=f'{len(groups):05d}',
                           members=[relative(p) for p in members],
                           shallow=[relative(p) for p in shallow]))
    for root in source_roots():
        if root.name in split and root.is_dir() and not root.is_symlink():
            add([], [root])
            for child in sorted(root.iterdir()):
                if child.name in {'waves', 'demand', 'requests', 'objects',
                                   'discovery-campaign', 'revisions'} and child.is_dir() and not child.is_symlink():
                    add([], [child])
                    for item in sorted(child.iterdir()):
                        add([item])
                else:
                    add([child])
        else:
            add([root])
    return dict(schema='v7-cold-archive-v1', created_at=now(),
                roots=[relative(p) for p in source_roots()], groups=groups,
                destination=str(DEST), uuid=archive.UUID, level=22,
                source_script_sha256=archive.sha(Path(__file__)),
                archive_helper_sha256=archive.sha(Path(archive.__file__)),
                retirement='Only regular files >1 MiB under selected local V7 validation roots; after ALL groups verify.',
                keep='Raw input trees, external originals, symlinks, small files, source, plans, shared/non-V7 trees.')


def validate_plan(plan):
    if plan['destination'] != str(DEST) or plan['uuid'] != archive.UUID:
        raise ValueError('Archive destination/identity changed')
    if plan['source_script_sha256'] != archive.sha(Path(__file__)):
        raise ValueError('Frozen archiver source changed')
    if plan['archive_helper_sha256'] != archive.sha(Path(archive.__file__)):
        raise ValueError('Frozen archive helper source changed')
    expected = {relative(p) for p in source_roots()}
    if set(plan['roots']) != expected:
        raise ValueError('Top-level V7 scope changed since planning')


def progress(status, **kwargs):
    save(STATE / 'progress.json', dict(status=status, updated_at=now(), **kwargs))


def pack(group, threads):
    name = group['id']
    receipt = STATE / f'{name}.verified.json'
    output = DEST / 'data' / f'{name}.tar.zst'
    if receipt.exists():
        result = json.loads(receipt.read_text())
        if output.stat().st_size != result['archive_bytes'] or archive.sha(output) != result['sha256']:
            raise ValueError(f'Verified archive changed: {name}')
        return result
    before = archive.fingerprint(group['members'], group['shallow'])
    retiring = candidates(group)
    partial = DEST / 'data' / f'{name}.tar.zst.partial'
    log = STATE / f'{name}.pack.log'
    guarded_run(['tar', '--format=pax', '--pax-option=delete=atime,delete=ctime',
                 '--xattrs', '--acls', '-I', f'zstd --ultra -22 -T{threads}',
                 '-cf', str(partial)] + archive.tar_args(group, STATE), log)
    if before != archive.fingerprint(group['members'], group['shallow']):
        raise ValueError(f'Source changed during packing: {name}')
    with partial.open('rb') as f:
        os.fsync(f.fileno())
    compare = STATE / f'{name}.compare.log'
    guarded_run(['tar', '--xattrs', '--acls', '-I', 'zstd -d -T1',
                 '-df', str(partial)], compare)
    if compare.stat().st_size:
        raise ValueError(f'Unexpected archive comparison diagnostics: {compare}')
    actual = archive.archive_census(partial)
    if actual != {key: before[key] for key in actual}:
        raise ValueError(f'Archive member counts differ: {name}')
    if before != archive.fingerprint(group['members'], group['shallow']):
        raise ValueError(f'Source changed during verification: {name}')
    for item in retiring:
        path = Path('/') / item['path']
        if stamp(path) != item['stamp']:
            raise ValueError(f'Retirement candidate changed: {path}')
    checksum = archive.sha(partial)
    partial.replace(output)
    result = dict(id=name, state='full-source-compare-and-member-census-verified',
                  source=before, members=actual, archive_bytes=output.stat().st_size,
                  sha256=checksum, retire_candidates=retiring, verified_at=now())
    save(DEST / 'manifests' / receipt.name, result)
    save(receipt, result)
    print(json.dumps({k: result[k] for k in ('id', 'archive_bytes', 'state')}), flush=True)
    return result


def retire(plan):
    # Completed verification is global. Each archive is rehashed immediately
    # before its deletions; each file is independently rehashed before unlink.
    completion = json.loads((DEST / 'VERIFIED.json').read_text())
    if completion['plan_sha256'] != archive.sha(STATE / 'plan.json'):
        raise ValueError('Completion does not bind this plan')
    journal = STATE / 'retired.jsonl'
    done = set()
    if journal.exists():
        done = {json.loads(line)['path'] for line in journal.read_text().splitlines()}
    with journal.open('a') as log:
        for group in plan['groups']:
            result = json.loads((STATE / f'{group["id"]}.verified.json').read_text())
            remaining = [x for x in result['retire_candidates'] if x['path'] not in done]
            if not remaining:
                continue
            drive()
            if archive.sha(DEST / 'data' / f'{group["id"]}.tar.zst') != result['sha256']:
                raise ValueError('Archive changed before reclamation')
            for item in remaining:
                path = Path('/') / item['path']
                if not path.is_relative_to(ROOT / 'nn_meta/validation'):
                    raise ValueError('Retirement escaped validation roots')
                # Journal intent BEFORE unlink, so a crash never leaves an
                # unaccounted missing source. On resume, confirm via archive.
                intent = STATE / 'retire-intent.json'
                if not path.exists() and not path.is_symlink():
                    if not intent.exists() or json.loads(intent.read_text()) != item:
                        raise ValueError(f'Unexplained missing source: {path}')
                else:
                    if stamp(path) != item['stamp'] or archive.sha(path) != item['sha256']:
                        raise ValueError(f'Source changed before retirement: {path}')
                    save(intent, item)
                    path.unlink()
                record = dict(path=item['path'], bytes=item['stamp'][3],
                              sha256=item['sha256'], archive=group['id'], at=now())
                log.write(json.dumps(record) + '\n'); log.flush(); os.fsync(log.fileno())
                done.add(item['path'])
            progress('reclaiming', group=group['id'], retired_files=len(done))
    shutil.copy2(journal, DEST / journal.name)
    return len(done)


def run(threads, reclaim):
    drive(); DEST.mkdir(exist_ok=True)
    (DEST / 'data').mkdir(exist_ok=True)
    (DEST / 'manifests').mkdir(exist_ok=True)
    plan = json.loads((STATE / 'plan.json').read_text())
    validate_plan(plan)
    shutil.copy2(STATE / 'plan.json', DEST / 'manifests/plan.json')
    shutil.copy2(__file__, DEST / 'manifests/archive_v7_cold.py')
    (DEST / 'RESTORE.txt').write_text(
        'V7 paused cold archive, MRHA UUID 62C9-C390. No completed V7 training claim.\n'
        'manifests/plan.json maps numbered tar.zst shards to original absolute paths with the leading / removed.\n'
        'VERIFY all archive hashes against manifests/*.verified.json before restoring.\n'
        'Extract first into a spacious staging directory: tar -I zstd -xf data/NNNNN.tar.zst -C STAGING\n'
        'Preserve symlinks and restore original /home/healy/Coding/HealysBacktester and\n'
        '/run/media/healy/MRHA paths (or explicitly remap all absolute symlinks).\n'
        'Raw external originals remain; local raw data and small receipts remain.\n'
        'Only VERIFIED.json establishes all shards verified; COMPLETE.json also records reclamation.\n'
        'Archived checkpoints are paused; do not auto-start old services or relabel contracts.\n')
    results = []
    for i, group in enumerate(plan['groups']):
        progress('archiving', group=group['id'], members=group['members'],
                 completed_groups=i, total_groups=len(plan['groups']), threads=threads)
        results.append(pack(group, threads))
    validate_plan(plan)
    result = dict(status='all-archives-verified', at=now(), groups=len(results),
                  plan_sha256=archive.sha(STATE / 'plan.json'),
                  archive_bytes=sum(r['archive_bytes'] for r in results),
                  retired_files=0)
    save(DEST / 'VERIFIED.json', result); save(STATE / 'VERIFIED.json', result)
    if reclaim:
        result['retired_files'] = retire(plan)
    result.update(status='complete', at=now(), local_free=shutil.disk_usage(ROOT).free,
                  external_free=shutil.disk_usage(DEST).free)
    save(DEST / 'COMPLETE.json', result); save(STATE / 'COMPLETE.json', result)
    progress('complete', **{k:v for k,v in result.items() if k != 'status'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['plan', 'run'])
    parser.add_argument('--threads', type=int, default=1)
    parser.add_argument('--reclaim', action='store_true')
    args = parser.parse_args()
    if args.threads < 1:
        parser.error('threads must be positive')
    STATE.mkdir(parents=True, exist_ok=True)
    archive.ROOT = Path('/')
    with (STATE / 'archive.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            if args.action == 'plan':
                if (STATE / 'plan.json').exists():
                    raise ValueError('Plan already exists; preserve it')
                plan = make_plan(); save(STATE / 'plan.json', plan)
                print(json.dumps(dict(groups=len(plan['groups']), roots=len(plan['roots']))))
            else:
                run(args.threads, args.reclaim)
        except Exception as exc:
            progress('failed', error=str(exc))
            raise


if __name__ == '__main__':
    main()
