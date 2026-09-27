#!/usr/bin/env python3
"""Remove reviewed duplicate allocations using independent copy-on-write files.

Rehash both sides, clone to a sibling, preserve metadata, verify and atomically
replace only the reviewed extra inode. No historical pathname is removed.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FICLONE = 0x40049409


def sha(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def signature(path):
    s = path.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1:
        raise ValueError(f'Not a single-link regular file: {path}')
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def replace_copy(reference, extra, expected, size):
    before_ref, before_extra = signature(reference), signature(extra)
    if before_ref[2] != size or before_extra[2] != size:
        raise ValueError('Size changed')
    if sha(reference) != expected or sha(extra) != expected:
        raise ValueError(f'Content changed: {extra}')
    if signature(reference) != before_ref or signature(extra) != before_extra:
        raise ValueError('Input changed during verification')
    fd, temp_name = tempfile.mkstemp(prefix='.verified-reflink-', dir=extra.parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, 'wb') as dst, reference.open('rb') as src:
            fcntl.ioctl(dst.fileno(), FICLONE, src.fileno())
            os.fsync(dst.fileno())
        shutil.copystat(extra, temp, follow_symlinks=False)
        original = extra.stat()
        if (temp.stat().st_uid, temp.stat().st_gid) != (original.st_uid, original.st_gid):
            os.chown(temp, original.st_uid, original.st_gid)
        if sha(temp) != expected:
            raise ValueError('Clone hash mismatch')
        if signature(reference) != before_ref or signature(extra) != before_extra:
            raise ValueError('Input changed before replacement')
        os.replace(temp, extra)
        with extra.open('rb') as f:
            os.fsync(f.fileno())
        parent_fd = os.open(extra.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        return dict(path=str(extra), reference=str(reference), bytes=size,
                    sha256=expected, original_inode=before_extra[1],
                    replacement_inode=extra.stat().st_ino)
    finally:
        temp.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--review', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--execute', action='store_true', required=True)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    lock = (args.output / 'lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    groups = json.loads(args.review.read_text())['review_groups']
    journal = args.output / 'replacements.jsonl'
    completed = {}
    if journal.exists():
        completed = {r['path']: r for r in map(json.loads, journal.read_text().splitlines())}
    free_before = shutil.disk_usage(ROOT).free
    total = sum(len(g['identical_other_paths']) for g in groups)
    with journal.open('a') as log:
        for group in groups:
            reference = ROOT / group['reference_path']
            for name in group['identical_other_paths']:
                extra = ROOT / name
                for p in (reference, extra):
                    if not p.resolve().is_relative_to(ROOT / 'nn_meta') or p.is_symlink():
                        raise ValueError('Path escaped approved root')
                if str(extra) in completed:
                    if sha(extra) != group['sha256']:
                        raise ValueError('Previously replaced content drifted')
                    continue
                result = replace_copy(reference, extra, group['sha256'], group['bytes'])
                log.write(json.dumps(result) + '\n'); log.flush(); os.fsync(log.fileno())
                completed[str(extra)] = result
                if len(completed) % 25 == 0:
                    print(f'Duplicate allocations removed: {len(completed)}/{total}', flush=True)
    os.sync()
    report = dict(state='complete', reviewed_sha256=sha(args.review),
                  files_replaced=len(completed), pathnames_removed=0,
                  duplicate_logical_bytes=sum(r['bytes'] for r in completed.values()),
                  free_before=free_before, free_after=shutil.disk_usage(ROOT).free,
                  method='verified atomic reflink replacement; independent copy-on-write inodes')
    (args.output / 'complete.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
