#!/usr/bin/env python3
"""Read-only file/directory inventory; no cleanup or source mutation.

Logical sizes and allocated blocks are different measurements. Hardlinks count
once in unique-file totals. Btrfs shared extents/compression and directory
metadata mean allocated blocks are NOT a claim of reclaimable free space.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import heapq
import json
import os
from pathlib import Path
import shutil
import stat
import time

ROOT = Path(__file__).resolve().parents[1]


def inventory(root, notify=None):
    root = Path(root).resolve()
    root_device = root.stat().st_dev
    totals, sizes, extensions = Counter(), Counter(), defaultdict(Counter)
    levels = {n: defaultdict(Counter) for n in (1,2,3,4)}
    hardlinks = {}
    aliases = Counter()
    largest = []
    errors = []
    began = time.monotonic()
    last_update = began
    stack = [(root, ())]
    while stack:
        folder, parts = stack.pop()
        try:
            entries = os.scandir(folder)
        except OSError as exc:
            errors.append(dict(path=str(folder.relative_to(root)), error=type(exc).__name__))
            continue
        with entries:
            for entry in entries:
                path_parts = (*parts, entry.name)
                relative = '/'.join(path_parts)
                try:
                    info = entry.stat(follow_symlinks=False)
                except OSError as exc:
                    errors.append(dict(path=relative, error=type(exc).__name__))
                    continue
                is_directory = stat.S_ISDIR(info.st_mode)
                delta = Counter()
                if is_directory:
                    delta['directories'] = 1
                    delta['directory_logical_bytes'] = info.st_size
                    if info.st_dev == root_device:
                        stack.append((Path(entry.path), path_parts))
                    else:
                        delta['foreign_device_directories_not_walked'] = 1
                elif stat.S_ISREG(info.st_mode):
                    delta['files'] = 1
                    delta['logical_bytes'] = info.st_size
                    delta['allocated_bytes'] = info.st_blocks*512
                    key = (info.st_dev, info.st_ino)
                    first = None
                    if info.st_nlink > 1:
                        first = hardlinks.get(key)
                        if first is None:
                            hardlinks[key] = ('/'.join(path_parts[:3]), info.st_size)
                        else:
                            delta['hardlink_aliases'] = 1
                            delta['hardlink_alias_logical_bytes'] = info.st_size
                            aliases[(first[0], '/'.join(path_parts[:3]))] += info.st_size
                    if first is None:
                        delta['unique_files'] = 1
                        delta['unique_logical_bytes'] = info.st_size
                        delta['unique_allocated_bytes'] = info.st_blocks*512
                    bucket = 'empty' if info.st_size == 0 else 'le1KiB' if info.st_size <= 1024 else 'le4KiB' if info.st_size <= 4096 else 'le64KiB' if info.st_size <= 65536 else 'le1MiB' if info.st_size <= 1048576 else 'gt1MiB'
                    sizes[bucket] += 1
                    ext = Path(entry.name).suffix.lower() or '(none)'
                    extensions[ext].update(files=1, logical_bytes=info.st_size)
                    item = (info.st_size, relative)
                    if len(largest) < 100:
                        heapq.heappush(largest, item)
                    elif item > largest[0]:
                        heapq.heapreplace(largest, item)
                elif stat.S_ISLNK(info.st_mode):
                    delta['symlinks_not_followed'] = 1
                    delta['symlink_logical_bytes'] = info.st_size
                else:
                    delta['other_entries'] = 1
                totals.update(delta)
                for depth, groups in levels.items():
                    # Files above the grouping depth belong to their directory,
                    # not to millions of individual filename-sized buckets.
                    group_parts = path_parts[:depth] if is_directory or len(parts) >= depth else parts
                    groups['/'.join(group_parts) or '.'].update(delta)
        now = time.monotonic()
        if notify and now-last_update >= 10:
            notify(dict(totals), '/'.join(parts), now-began)
            last_update = now
    return dict(totals=dict(totals), size_buckets=dict(sizes), extensions=dict(extensions),
                groups={str(n):dict(groups) for n,groups in levels.items()},
                hardlink_alias_groups=[dict(first_group=a, alias_group=b, logical_bytes=v)
                                       for (a,b),v in aliases.most_common(100)],
                largest_files=[dict(path=p, logical_bytes=n) for n,p in sorted(largest, reverse=True)],
                errors=errors, elapsed_seconds=time.monotonic()-began)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT/'nn_meta/validation') or output.exists():
        parser.error('Use a new validation output')
    import sys
    sys.path.insert(0,str(ROOT))
    from nn_meta.v7.storage import sha, identity, transaction, receipt
    from scripts.download_v7_data import save
    status_path = output.with_suffix('.status.json')
    started = datetime.now(timezone.utc).isoformat()
    def status(totals, current, elapsed):
        save(status_path, dict(state='scanning', totals=totals, current=current,
                               elapsed_seconds=elapsed, updated_at=datetime.now(timezone.utc).isoformat()))
        print(f"Inventory: {totals.get('files',0):,} files, {totals.get('directories',0):,} directories", flush=True)
    binding = dict(root=str(ROOT), source_sha256=sha(__file__), started_at=started)
    report = inventory(ROOT, status)
    report.update(schema='project-storage-inventory-v1', finished_at=datetime.now(timezone.utc).isoformat(),
                  disk_usage=shutil.disk_usage(ROOT)._asdict(), non_atomic=True,
                  deleted_files=0, reclaimable_space_verified=False,
                  notes=['Unique totals deduplicate inode hardlinks only, not reflinks or content duplicates.',
                         'Allocated file blocks cannot be interpreted as Btrfs space freed by deletion.',
                         'No symlinks followed or foreign devices traversed; no file contents read for inventory.',
                         'Group-level unique-byte attribution depends on first hardlink encountered; root unique totals do not.'])
    with transaction(output) as temporary:
        save(temporary/'binding.json',binding); save(temporary/'report.json',report)
        receipt(temporary,dict(identity=identity(binding)))
    save(status_path,dict(state='complete',totals=report['totals'],updated_at=report['finished_at']))
    print(json.dumps(report['totals'],indent=2),flush=True)


if __name__ == '__main__':
    main()
