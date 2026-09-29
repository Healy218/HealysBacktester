#!/usr/bin/env python3
"""Remove only byte-equivalent SQLite scratch copies after sealed publication."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def fingerprints(path):
    original=hashlib.sha256();normalized=hashlib.sha256();size=0
    with Path(path).open('rb') as stream:
        head=stream.read(100)
        if len(head)!=100 or head[:16]!=b'SQLite format 3\0':raise ValueError('Not SQLite scratch')
        original.update(head);size+=len(head);head=bytearray(head)
        # SQLite backup resets only transaction/schema-version counters. Every
        # schema/table/index/payload byte and all other header fields must match.
        for lo,hi in [(24,28),(40,44),(92,96)]:head[lo:hi]=bytes(hi-lo)
        normalized.update(head)
        for block in iter(lambda:stream.read(4*1024**2),b''):
            size+=len(block);original.update(block);normalized.update(block)
    return size,original.hexdigest(),normalized.hexdigest()


def compact(root):
    from nn_meta.v7.storage import verify,sha
    from incubator.continual.storage import write
    root=Path(root)
    released=0
    for scratch in sorted((root/'working').glob('*/jobs.sqlite3')):
        final=root/'jobs'/scratch.parent.name
        if not (final/'complete.json').exists():continue
        header=verify(final)
        left,right=fingerprints(scratch),fingerprints(final/'jobs.sqlite3')
        if right[1]!=header['files']['jobs.sqlite3'] or (left[0],left[2])!=(right[0],right[2]):
            raise ValueError('Scratch is not equivalent to its sealed replacement')
        if sha(scratch)!=left[1]:raise ValueError('Scratch changed during comparison')
        record=dict(scratch=str(scratch),scratch_sha256=left[1],retained=str(final/'jobs.sqlite3'),
                    retained_sha256=right[1],retained_receipt_sha256=sha(final/'complete.json'),bytes=left[0],
                    normalized_sqlite_sha256=left[2],observed_at=datetime.now(timezone.utc).isoformat())
        write(root/'scratch-compaction'/f'{scratch.parent.name}.json',record)
        scratch.unlink()
        released+=left[0]
    return released


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--watch-seconds',type=int,default=0)
    a=p.parse_args();end=time.monotonic()+a.watch_seconds
    if not a.root.resolve().is_relative_to(ROOT/'nn_meta/validation'):p.error('Validation scratch root required')
    while True:
        print(json.dumps(dict(released_bytes=compact(a.root))),flush=True)
        status=json.loads((a.root/'progress.json').read_text()).get('status')
        if time.monotonic()>=end or status in ('planned','failed'):break
        time.sleep(30)


if __name__=='__main__':main()
