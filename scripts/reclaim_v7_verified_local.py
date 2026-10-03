#!/usr/bin/env python3
"""User-authorized early reclamation of independently verified local V7 shards.

The active compressor is unchanged. Its controller is briefly stopped only for
each journaled unlink, while compressor children continue. This prevents its
final reclamation phase racing this pass. ExecStopPost recovers an owned stop.
"""
from contextlib import contextmanager
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
from scripts import archive_v7_cold as cold

CONTROLLER = ROOT / 'scripts/archive_v7_cold_staged.py'


class FinalPhase(Exception):
    pass


def identity(pid):
    fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    return dict(pid=pid, start=fields[19], state=fields[0],
                boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip())


def assert_command(pid, expected):
    if expected is None:  # Test-owned child processes only.
        return
    args = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
    if not any((ROOT / os.fsdecode(arg)).resolve() == expected for arg in args if arg):
        raise ValueError('PID is not the selected V7 archive controller')


def marker():
    return cold.STATE / 'early-cleanup-controller-pause.json'


def recover_pause(expected=CONTROLLER):
    path = marker()
    if not path.exists():
        return
    owner = json.loads(path.read_text())
    try:
        fd = os.pidfd_open(owner['pid'])
    except ProcessLookupError:
        path.unlink(); return
    try:
        current = identity(owner['pid'])
        if any(current[k] != owner[k] for k in ('pid', 'start', 'boot')):
            raise ValueError('Pause owner identity changed; do not signal reused PID')
        assert_command(owner['pid'], expected)
        signal.pidfd_send_signal(fd, signal.SIGCONT)
        path.unlink()
    finally:
        os.close(fd)


class Controller:
    def __init__(self, pid, expected=CONTROLLER):
        self.owner = identity(pid)
        self.fd = os.pidfd_open(pid)
        self.expected = expected
        self.check()

    def check(self):
        current = identity(self.owner['pid'])
        if any(current[k] != self.owner[k] for k in ('pid', 'start', 'boot')):
            raise ValueError('Controller identity changed')
        assert_command(self.owner['pid'], self.expected)
        return current

    @contextmanager
    def pause(self):
        if self.check()['state'] in ('T', 't'):
            raise ValueError('Controller was already stopped; preserve that pause')
        cold.save(marker(), self.owner)
        try:
            signal.pidfd_send_signal(self.fd, signal.SIGSTOP)
            deadline = time.monotonic() + 5
            while self.check()['state'] != 'T':
                if time.monotonic() > deadline:
                    raise RuntimeError('Controller did not acknowledge brief stop')
                time.sleep(0.005)
            yield
        finally:
            signal.pidfd_send_signal(self.fd, signal.SIGCONT)
            marker().unlink(missing_ok=True)

    def close(self):
        os.close(self.fd)


def external(group):
    return any(p.startswith('run/media/') for p in group['members'] + group['shallow'])


def phase_guard(plan):
    if (cold.STATE / 'VERIFIED.json').exists():
        raise FinalPhase('Full archive verification reached; final consumer takes over')
    progress = json.loads((cold.STATE / 'progress.json').read_text())
    groups = {g['id']: g for g in plan['groups']}
    active = progress.get('active_groups', [])
    if (progress.get('status') != 'archiving' or progress.get('phase') != 'serial-direct'
            or not active or any(not external(groups[name]) for name in active)):
        raise FinalPhase('Archive is no longer exclusively compressing external inputs')


def candidate_path(item, group, plan):
    path = Path('/') / item['path']
    base = cold.ROOT / 'nn_meta/validation'
    if ('..' in path.parts or not path.is_relative_to(base) or path.is_relative_to(cold.STATE)
            or not path.relative_to(base).parts[0].startswith('v7')
            or not any(path.is_relative_to(Path('/') / root) for root in group['members'])):
        raise ValueError('Candidate is outside the frozen local V7 shard')
    if item['path'] in plan['roots']:
        return None  # Preserve the root census needed by the running consumer.
    if not stat.S_ISREG(item['stamp'][2]) or item['stamp'][3] <= cold.KEEP:
        raise ValueError('Unexpected retirement candidate type/size')
    return path


def local_manifest(plan):
    rows = []
    for group in plan['groups']:
        if external(group):
            continue
        path = cold.STATE / f'{group["id"]}.verified.json'
        receipt = json.loads(path.read_text())
        if receipt['id'] != group['id'] or receipt['state'] != 'full-source-compare-and-member-census-verified':
            raise ValueError('Local shard has not completed full verification')
        if receipt['members'] != {k: receipt['source'][k] for k in receipt['members']}:
            raise ValueError('Local archive member census differs')
        for item in receipt['retire_candidates']:
            candidate_path(item, group, plan)
        rows.append(dict(group=group, receipt_sha256=cold.archive.sha(path)))
    return rows


def status(state, **values):
    cold.save(cold.STATE / 'early-cleanup-progress.json', dict(status=state, at=cold.now(), **values))


def archive_hash(path, mib_per_second):
    digest = hashlib.sha256(); began = time.monotonic(); count = 0
    with path.open('rb') as source:
        while block := source.read(1024**2):
            digest.update(block); count += len(block)
            if mib_per_second:
                delay = count / (mib_per_second * 1024**2) - (time.monotonic() - began)
                if delay > 0:
                    time.sleep(delay)
    return digest.hexdigest()


def retire_one(item, group, plan, controller, journal):
    path = candidate_path(item, group, plan)
    if path is None:
        return False
    intent = cold.STATE / 'retire-intent.json'
    missing = not path.exists() and not path.is_symlink()
    if missing:
        if not intent.exists() or json.loads(intent.read_text()) != item:
            raise ValueError(f'Unexplained missing source: {path}')
    elif cold.stamp(path) != item['stamp'] or cold.archive.sha(path) != item['sha256']:
        raise ValueError(f'Source changed before retirement: {path}')
    # Expensive hashing occurs while the original compressor keeps running.
    # Stop only the controller for the short deletion/journal critical section.
    with controller.pause():
        phase_guard(plan)
        cold.drive()
        if not missing:
            if cold.stamp(path) != item['stamp']:
                raise ValueError('Source metadata changed after hashing')
            cold.save(intent, item)
            path.unlink()
        record = dict(path=item['path'], bytes=item['stamp'][3], sha256=item['sha256'],
                      archive=group['id'], at=cold.now())
        journal.write(json.dumps(record) + '\n'); journal.flush(); os.fsync(journal.fileno())
    return True


def run(rate):
    cold.drive(); cold.validate_plan(json.loads((cold.STATE / 'plan.json').read_text()))
    plan = json.loads((cold.STATE / 'plan.json').read_text())
    if cold.archive.sha(cold.STATE / 'plan.json') != cold.archive.sha(cold.DEST / 'manifests/plan.json'):
        raise ValueError('External plan differs')
    phase_guard(plan)
    rows = local_manifest(plan)
    binding = dict(schema='v7-verified-local-early-reclamation-v1',
                   plan_sha256=cold.archive.sha(cold.STATE / 'plan.json'),
                   source_sha256=cold.archive.sha(Path(__file__)), groups=rows)
    declaration = cold.STATE / 'early-cleanup-declaration.json'
    if declaration.exists() and json.loads(declaration.read_text()) != binding:
        raise ValueError('Early cleanup declaration changed')
    cold.save(declaration, binding)
    cold.save(cold.DEST / 'manifests/early-cleanup-declaration.json', binding)
    shutil.copy2(__file__, cold.DEST / 'manifests/reclaim_v7_verified_local.py')
    recover_pause()
    pid = int(subprocess.check_output(['systemctl', '--user', 'show', 'healys-v7-cold-archive.service',
                                      '-p', 'MainPID', '--value'], text=True))
    controller = Controller(pid)
    journal_path = cold.STATE / 'retired.jsonl'
    done = set()
    if journal_path.exists():
        done = {json.loads(line)['path'] for line in journal_path.read_text().splitlines()}
    initial_free = shutil.disk_usage(cold.ROOT).free
    removed_bytes = 0
    try:
        with journal_path.open('a') as journal:
            for row in rows:
                phase_guard(plan)
                group = row['group']; name = group['id']
                receipt_path = cold.STATE / f'{name}.verified.json'
                if cold.archive.sha(receipt_path) != row['receipt_sha256']:
                    raise ValueError('Frozen local receipt changed')
                receipt = json.loads(receipt_path.read_text())
                items = [item for item in receipt['retire_candidates'] if item['path'] not in done
                         and candidate_path(item, group, plan) is not None]
                if not items:
                    continue
                status('checking-archive', group=name, retired_files=len(done), logical_bytes_removed_this_pass=removed_bytes,
                       local_free=shutil.disk_usage(cold.ROOT).free)
                cold.drive()
                if json.loads((cold.DEST / 'manifests' / receipt_path.name).read_text()) != receipt:
                    raise ValueError('External/local verification receipts differ')
                if archive_hash(cold.DEST / 'data' / f'{name}.tar.zst', rate) != receipt['sha256']:
                    raise ValueError('External archive changed before early retirement')
                for item in items:
                    if retire_one(item, group, plan, controller, journal):
                        done.add(item['path']); removed_bytes += item['stamp'][3]
                status('reclaiming', group=name, retired_files=len(done), logical_bytes_removed_this_pass=removed_bytes,
                       local_free=shutil.disk_usage(cold.ROOT).free)
        result = dict(status='complete', at=cold.now(), retired_files=len(done),
                      logical_bytes_removed_this_pass=removed_bytes, initial_local_free=initial_free,
                      local_free=shutil.disk_usage(cold.ROOT).free, full_archive_complete=False)
        cold.save(cold.STATE / 'LOCAL_CLEANUP_COMPLETE.json', result)
        cold.save(cold.DEST / 'LOCAL_CLEANUP_COMPLETE.json', result)
        shutil.copy2(journal_path, cold.DEST / journal_path.name)
        status('complete', **{k: v for k, v in result.items() if k != 'status'})
    except FinalPhase as exc:
        status('handed-to-final-cleanup', reason=str(exc), retired_files=len(done),
               local_free=shutil.disk_usage(cold.ROOT).free)
    finally:
        controller.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume-controller', action='store_true')
    parser.add_argument('--archive-read-mib', type=float, default=16)
    args = parser.parse_args()
    if args.resume_controller:
        recover_pause(); return
    if args.archive_read_mib <= 0:
        parser.error('Archive read rate must be positive')
    with (cold.STATE / 'early-cleanup.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            run(args.archive_read_mib)
        except Exception as exc:
            status('failed', error=str(exc)); raise


if __name__ == '__main__':
    main()
