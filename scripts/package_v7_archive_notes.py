#!/usr/bin/env python3
"""Refresh the readable V7 archive guide and a verified compressed notes snapshot."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.archive_v7_cold import DEST, STATE, drive, now


def main():
    drive()
    snapshot = STATE / 'notes-snapshot'
    snapshot.mkdir(parents=True, exist_ok=True)
    for folder in ('docs', 'handoff-history'):
        shutil.copytree(ROOT / folder, snapshot / folder, dirs_exist_ok=True)
    for path in ROOT.glob('*.md'):
        if not path.is_symlink():
            shutil.copy2(path, snapshot / path.name)
    runtime = snapshot / 'archive-runtime'
    runtime.mkdir(exist_ok=True)
    for name in ('scripts/start_v7_cold_archive_fast.sh',
                 'scripts/archive_v7_cold_parallel.py',
                 'scripts/package_v7_archive_notes.py',
                 'deploy/systemd/healys-v7-cold-archive.service'):
        shutil.copy2(ROOT / name, runtime / Path(name).name)
    for name in ('notes', 'data', 'manifests'):
        (DEST / name).mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'docs/reference/V7_COLD_ARCHIVE_README.md', DEST / 'README.md')
    shutil.copy2(ROOT / 'scripts/verify_v7_cold_archive.py', DEST / 'manifests/verify_and_list.py')
    partial = DEST / 'notes/notes.tar.zst.partial'
    subprocess.run(['tar', '--format=pax', '--pax-option=delete=atime,delete=ctime',
                    '--sort=name', '-I', 'zstd --ultra -22 -T1', '-cf', str(partial),
                    '-C', str(snapshot), '.'], check=True)
    subprocess.run(['tar', '-I', 'zstd -d', '-df', str(partial)], cwd=snapshot, check=True)
    with partial.open('rb') as f:
        os.fsync(f.fileno())
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    partial.replace(DEST / 'notes/notes.tar.zst')
    (DEST / 'notes/SHA256SUMS').write_text(digest + '  notes.tar.zst\n')
    receipt = dict(at=now(), sha256=digest, bytes=(DEST / 'notes/notes.tar.zst').stat().st_size,
                   state='notes-snapshot-full-source-compare-passed',
                   files=sum(p.is_file() for p in snapshot.rglob('*')))
    (STATE / 'notes-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
