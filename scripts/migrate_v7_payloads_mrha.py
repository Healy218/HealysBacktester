#!/usr/bin/env python3
"""Copy sealed V7 payloads to MRHA, verify, then atomically replace files with links."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import sqlite3
import stat
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.v7_capture_storage import verify_mount

MOUNT = Path('/run/media/healy/MRHA')
DRIVE_UUID = '62C9-C390'
SOURCE = ROOT / 'nn_meta/data_v7'
EXTERNAL = MOUNT / 'HealysBacktester/sealed-v7-payloads-20260929'
RESERVE = 20 * 1024**3
EXTENSIONS = ('.sqlite3', '.parquet', '.json.gz', '.csv.gz', '.arrow', '.npy')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024**2), b''):
            h.update(chunk)
    return h.hexdigest()


def stamp(path):
    s = path.stat(follow_symlinks=False)
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns]


def sync_dir(path):
    fd = os.open(path, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_json(path, value):
    path = Path(path)
    temp = path.with_name(path.name + '.tmp')
    with temp.open('w') as f:
        json.dump(value, f, sort_keys=True, indent=2)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(temp, path)
    sync_dir(path.parent)


def connect(state):
    db = sqlite3.connect(state / 'files.sqlite3')
    db.execute('PRAGMA synchronous=FULL')
    db.execute('PRAGMA cache_size=-8192')
    return db


def plan(state):
    if state.exists():
        raise FileExistsError(state)
    state.mkdir(parents=True)
    db = connect(state)
    db.execute('CREATE TABLE files(source TEXT PRIMARY KEY,sha TEXT,size INTEGER,stamp TEXT,header TEXT,header_sha TEXT,mode INTEGER,mtime INTEGER,status TEXT DEFAULT "planned",destination TEXT)')
    skipped = 0
    sidecars = []
    try:
        for header in SOURCE.rglob('complete.json'):
            if any('.partial-' in p for p in header.parts):
                continue
            doc = json.loads(header.read_text())
            if doc.get('complete') is not True or not isinstance(doc.get('files'), dict):
                continue
            anchor = digest(header)
            for name, expected in doc['files'].items():
                part = Path(name)
                if part.is_absolute() or '..' in part.parts:
                    raise ValueError('Unsafe receipt path')
                if not str(part).endswith(EXTENSIONS) or part.name == 'index.sqlite3':
                    continue
                src = header.parent / part
                if src.is_symlink():
                    if not src.exists():
                        raise ValueError('Existing payload link is broken: ' + str(src))
                    skipped += 1
                    continue
                if not src.is_file() or src.resolve() != src:
                    raise ValueError('Unexpected payload type: ' + str(src))
                if any(Path(str(src) + suffix).exists() for suffix in ('-journal', '-wal', '-shm')):
                    sidecars.append(str(src))
                    continue
                s = src.stat()
                if not isinstance(expected, str) or len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
                    raise ValueError('Invalid receipt checksum')
                prior = db.execute('SELECT sha FROM files WHERE source=?', (str(src),)).fetchone()
                if prior:
                    if prior[0] != expected:
                        raise ValueError('Conflicting receipts')
                    continue
                db.execute('INSERT INTO files(source,sha,size,stamp,header,header_sha,mode,mtime) VALUES(?,?,?,?,?,?,?,?)',
                           (str(src), expected, s.st_size, json.dumps(stamp(src)), str(header), anchor, stat.S_IMODE(s.st_mode), s.st_mtime_ns))
        db.commit()
        count, size = db.execute('SELECT count(*),sum(size) FROM files').fetchone()
        unique, unique_bytes = db.execute('SELECT count(*),sum(size) FROM (SELECT sha,max(size) size FROM files GROUP BY sha)').fetchone()
        doc = dict(schema='v7-mrha-payload-migration-v1',source=str(SOURCE),external=str(EXTERNAL),mount_uuid=DRIVE_UUID,
                   files=count,logical_bytes=size,unique_payloads=unique,unique_bytes=unique_bytes,existing_links_skipped=skipped,sqlite_sidecars_skipped=sidecars,
                   authorization='User: lets move as much as we can.',created_at=datetime.now(timezone.utc).isoformat(),
                   producer_sha256=digest(__file__),scope='Only checksum-bound completed V7 raw payloads; keep all logical directories, receipts and active working stores local.')
        write_json(state / 'plan.json', doc)
        print(json.dumps(doc), flush=True)
    finally:
        db.close()


def relocate(src, dst, expected, original_stamp, *, pre_replace=None):
    """Durable verified destination exists before the original inode is unlinked."""
    src, dst = Path(src), Path(dst)
    if src.is_symlink():
        if src.resolve() != dst or digest(dst) != expected:
            raise ValueError('Existing locator differs')
        return 'resumed_link'
    if stamp(src) != original_stamp:
        raise ValueError('Source metadata changed before copy: ' + str(src))
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        if digest(dst) != expected:
            raise ValueError('Existing external payload checksum differs')
    else:
        temp = dst.with_name(dst.name + '.partial-' + uuid.uuid4().hex)
        h = hashlib.sha256()
        with src.open('rb') as reader, temp.open('xb') as writer:
            for chunk in iter(lambda: reader.read(4 * 1024**2), b''):
                h.update(chunk); writer.write(chunk)
            writer.flush(); os.fsync(writer.fileno())
        if h.hexdigest() != expected or digest(temp) != expected:
            raise ValueError('Copied payload differs from sealed receipt')
        os.replace(temp, dst)
        sync_dir(dst.parent)
    # Re-read source even for reused destinations and reject source mutation.
    if digest(src) != expected or stamp(src) != original_stamp:
        raise ValueError('Source changed during migration')
    if pre_replace:
        pre_replace()
    link = src.with_name(src.name + '.mrha-link-' + uuid.uuid4().hex)
    link.symlink_to(dst)
    try:
        if stamp(src) != original_stamp:
            raise ValueError('Source changed before replacement')
        os.replace(link, src)
        sync_dir(src.parent)
    finally:
        if link.is_symlink():
            link.unlink()
    return 'moved'


def run(state, limit=0):
    state = state.resolve()
    lock = (state / 'lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    doc = json.loads((state / 'plan.json').read_text())
    if doc['producer_sha256'] != digest(__file__) or doc['source'] != str(SOURCE) or doc['external'] != str(EXTERNAL):
        raise ValueError('Frozen migration inputs changed')
    verify_mount(MOUNT, DRIVE_UUID)
    EXTERNAL.mkdir(parents=True, exist_ok=True)
    # The externally readable catalog includes original paths/checksums/metadata for restore.
    external_plan = EXTERNAL / 'plan.json'
    if external_plan.exists() and json.loads(external_plan.read_text()) != doc:
        raise ValueError('External migration plan differs')
    write_json(external_plan, doc)
    (EXTERNAL / 'RESTORE.txt').write_text('Keep MRHA mounted at /run/media/healy/MRHA. Original directories and receipts stay local; only payload files link here.\n'
        'files.sqlite3 records original paths, hashes, modes and mtimes. migration.jsonl records published file links.\n'
        'To restore an individual file, copy its destination to a temporary sibling of the original source, verify SHA256, restore recorded mode/mtime, and atomically replace the symlink.\n'
        'Never remove this object store while any local receipt depends on it.\n')
    db = connect(state)
    with sqlite3.connect(EXTERNAL / 'files.sqlite3') as backup:
        db.backup(backup)
    stopping = False
    def stop(*_):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    start = time.monotonic(); done = 0; last_report = 0
    before = dict(local_free=shutil.disk_usage(ROOT).free,external_free=shutil.disk_usage(MOUNT).free)
    if not (state / 'before.json').exists():
        write_json(state / 'before.json', before)
    def report(status, error=None):
        n, total = db.execute('SELECT count(*),coalesce(sum(size),0) FROM files WHERE status="moved"').fetchone()
        value = dict(status=status,files_moved=n,files_required=doc['files'],logical_bytes_moved=total,logical_bytes_required=doc['logical_bytes'],
                     elapsed_seconds=time.monotonic()-start,updated_at=datetime.now(timezone.utc).isoformat(),error=error,
                     local_free=shutil.disk_usage(ROOT).free,external_free=shutil.disk_usage(MOUNT).free)
        write_json(state / 'progress.json', value)
        print(json.dumps(value), flush=True)
    try:
        report('running')
        # Large objects first reclaim space promptly; a content-addressed store avoids duplicate copies.
        cursor = db.execute('SELECT source,sha,stamp,header,header_sha,size FROM files WHERE status="planned" ORDER BY size DESC,source')
        for source, expected, fingerprint, header, anchor, size in cursor:
            if stopping or (limit and done >= limit):
                break
            verify_mount(MOUNT, DRIVE_UUID)
            dst = EXTERNAL / 'objects' / expected[:2] / expected
            if not dst.exists() and shutil.disk_usage(MOUNT).free < RESERVE + size:
                report('capacity_checkpoint'); return
            def validate():
                verify_mount(MOUNT, DRIVE_UUID)
                if digest(header) != anchor:
                    raise ValueError('Original completion receipt changed')
                if any(Path(source + x).exists() for x in ('-journal', '-wal', '-shm')):
                    raise ValueError('SQLite writer appeared')
            validate()
            outcome = relocate(source, dst, expected, json.loads(fingerprint), pre_replace=validate)
            row = dict(source=source,destination=str(dst),sha256=expected,bytes=size,outcome=outcome,at=datetime.now(timezone.utc).isoformat())
            for log in [state / 'migration.jsonl', EXTERNAL / 'migration.jsonl']:
                with log.open('a') as f:
                    f.write(json.dumps(row, sort_keys=True) + '\n'); f.flush(); os.fsync(f.fileno())
            db.execute('UPDATE files SET status="moved",destination=? WHERE source=?', (str(dst),source)); db.commit()
            done += 1
            if time.monotonic() - last_report >= 30:
                report('running'); last_report = time.monotonic()
        remaining = db.execute('SELECT count(*) FROM files WHERE status="planned"').fetchone()[0]
        report('complete' if remaining == 0 else 'checkpointed')
    except BaseException as exc:
        report('failed', type(exc).__name__ + ': ' + str(exc))
        raise
    finally:
        with sqlite3.connect(EXTERNAL / 'files.sqlite3') as backup:
            db.backup(backup)
        db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['plan','run'])
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--limit', type=int, default=0, help='Optional finite pilot file count; zero migrates full plan')
    args = parser.parse_args()
    if not args.state.resolve().is_relative_to(ROOT / 'nn_meta/validation') or args.limit < 0:
        parser.error('Repository validation state and nonnegative pilot limit required')
    if args.mode == 'plan':
        plan(args.state)
    else:
        run(args.state, args.limit)
