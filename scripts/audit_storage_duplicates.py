#!/usr/bin/env python3
"""Hash size-matched large files in named roots; report, never deduplicate/delete."""
import argparse
from collections import defaultdict
from concurrent.futures import as_completed
from datetime import datetime, timezone
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def digest_file(arguments):
    name,expected=arguments
    from nn_meta.v7.storage import sha
    p=Path(name);before=p.stat()
    value=sha(p);after=p.stat()
    if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino) or before.st_size!=expected:
        raise ValueError('File changed while hashing duplicate candidates')
    return dict(path=str(p.relative_to(ROOT)),sha256=value,bytes=before.st_size,
                device=before.st_dev,inode=before.st_ino,links=before.st_nlink,
                allocated_bytes=before.st_blocks*512)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,action='append',required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--workers',type=int,required=True)
    ap.add_argument('--min-bytes',type=int,default=1024**2)
    args=ap.parse_args()
    from nn_meta.v7.runtime import configure_threads,worker_pool
    configure_threads(1)
    from nn_meta.v7.storage import sha,identity,transaction,receipt
    from scripts.download_v7_data import save
    roots=[p.resolve() for p in args.root];output=args.output.resolve()
    if any(not p.is_relative_to(ROOT) for p in roots) or not output.is_relative_to(ROOT/'nn_meta/validation') or output.exists():
        ap.error('Use repo input roots and a new validation output')
    sizes=defaultdict(list);seen=set();scanned=0;aliases=0
    for root in roots:
        for folder,_,files in os.walk(root,followlinks=False):
            for name in files:
                p=Path(folder)/name
                if p.is_symlink():continue
                st=p.stat();scanned+=1
                if st.st_size<args.min_bytes:continue
                key=(st.st_dev,st.st_ino)
                if key in seen:aliases+=1;continue
                seen.add(key);sizes[st.st_size].append(str(p))
    candidates=[(p,size) for size,paths in sizes.items() if len(paths)>1 for p in paths]
    matches=defaultdict(list)
    with worker_pool(args.workers,threads=1) as pool:
        futures=[pool.submit(digest_file,c) for c in candidates]
        for i,future in enumerate(as_completed(futures),1):
            item=future.result();matches[(item['bytes'],item['sha256'])].append(item)
            if i%100==0:
                print(f'Duplicate hashes {i}/{len(candidates)}',flush=True)
                save(output.with_suffix('.status.json'),dict(state='hashing',completed=i,total=len(candidates),
                     updated_at=datetime.now(timezone.utc).isoformat()))
    groups=[dict(bytes=size,sha256=digest,extra_logical_bytes=size*(len(files)-1),files=sorted(files,key=lambda x:x['path']))
            for (size,digest),files in matches.items() if len(files)>1]
    groups.sort(key=lambda g:(-g['extra_logical_bytes'],g['sha256']))
    binding=dict(source_sha256=sha(__file__),roots=[str(p) for p in roots],min_bytes=args.min_bytes)
    report=dict(schema='large-content-duplicate-audit-v1',scanned_files=scanned,already_hardlinked_entries=aliases,
                hashed_files=len(candidates),hashed_bytes=sum(s for _,s in candidates),duplicate_groups=groups,
                extra_identical_logical_bytes=sum(g['extra_logical_bytes'] for g in groups),
                reclaimed_bytes=0,deleted_files=0,
                caveat='Byte-identical files in distinct inodes. May share Btrfs extents; not a reclaimable-space estimate or deletion approval.')
    with transaction(output) as temp:
        save(temp/'binding.json',binding);save(temp/'report.json',report)
        receipt(temp,dict(identity=identity(binding)))
    save(output.with_suffix('.status.json'),dict(state='complete',completed=len(candidates),total=len(candidates)))
    print({k:v for k,v in report.items() if k!='duplicate_groups'},flush=True)


if __name__=='__main__':main()
