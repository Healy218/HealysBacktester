#!/usr/bin/env python3
"""Read-only MRHA/v7 checksum verifier and ordered restoration command listing."""
import hashlib
import json
from pathlib import Path
import shlex


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def verify(folder):
    folder = Path(folder)
    complete = json.loads((folder / 'VERIFIED.json').read_text())
    plan_path = folder / 'manifests/plan.json'
    if sha(plan_path) != complete['plan_sha256']:
        raise ValueError('Plan checksum mismatch')
    plan = json.loads(plan_path.read_text())
    if len(plan['groups']) != complete['groups']:
        raise ValueError('Incomplete group census')
    total = 0
    for group in plan['groups']:
        name = group['id']
        if not name.isdigit():
            raise ValueError('Unexpected shard name')
        receipt = json.loads((folder / f'manifests/{name}.verified.json').read_text())
        archive = folder / f'data/{name}.tar.zst'
        if archive.stat().st_size != receipt['archive_bytes'] or sha(archive) != receipt['sha256']:
            raise ValueError(f'Archive checksum/size mismatch: {name}')
        total += archive.stat().st_size
        print(f'# verified {name}', flush=True)
    if total != complete['archive_bytes']:
        raise ValueError('Archive byte census mismatch')
    def rank(group):
        paths = group['members'] + group['shallow']
        if any('/source-snapshot' in p for p in paths):
            return 0
        if any(p.startswith('run/media/') for p in paths):
            return 1
        if any('/data_v7' in p or '/research_plans/' in p for p in paths):
            return 2
        return 3
    print('# All archives verified. Create STAGING on a spacious Linux filesystem.')
    print('# Run commands from the v7 archive folder; replace /path/to/staging.')
    for group in sorted(plan['groups'], key=rank):
        print('# ' + ', '.join(group['members'] + group['shallow']))
        print('tar -I zstd -xf ' + shlex.quote(f'data/{group["id"]}.tar.zst')
              + ' -C /path/to/staging')
    return len(plan['groups'])


if __name__ == '__main__':
    verify(Path(__file__).resolve().parents[1])
