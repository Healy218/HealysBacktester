#!/usr/bin/env python3
"""Inventory path references in all current V7 declarations, without deleting.

This is a conservative retention aid, not a garbage-collection authorization or
an exhaustive dependency proof for every historical/live system.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    output=args.output.resolve()
    if not output.is_relative_to(ROOT/'nn_meta/validation') or output.exists():
        parser.error('Use a new validation output')
    from nn_meta.v7.storage import verify,sha,identity,transaction,receipt
    from scripts.download_v7_data import save
    audit=ROOT/'nn_meta/validation/v7-3-entry-union-20260926'
    verify(audit)
    universe=json.loads((audit/'binding.json').read_text())['securities']
    base=ROOT/'nn_meta/validation'
    paths=[ROOT/'docs/specs/V7_ACTIVE_INPUTS_20220315_OPTION_RISK.json',
           base/'v7-2-completion-20260925/gate.json',audit/'binding.json',audit/'report.json',
           base/'v7-3-kernel-equivalence-20260925/report.json',
           base/'v7-2-final-deep-gate-20260925.json',
           base/'v7-2-full-daily-audit-20260925.json']
    for sid in universe:
        paths.append(base/'v7-3-scheduler-20260925/demand'/sid/'declaration.json')
        paths.extend(base/'v7-daily-context-20260925-full'/sid/n for n in ('declaration.json','inputs.json'))
        for minutes in ('5','15','30'):
            for kind in ('features','proposals'):
                paths.append(base/'v7-2-full-catalog-20260922-rebuild-5-15-30'/sid/minutes/kind/'declaration/declaration.json')
    pattern=re.compile(rb'"('+re.escape(str(ROOT).encode()+b'/')+rb'[^"\r\n]+)"')
    relative=re.compile(rb'"((?:nn_meta|v3|docs|scripts|fa|incubator)/[^"\r\n]+)"')
    groups=Counter();examples=defaultdict(list);inputs={};read_bytes=0
    for i,path in enumerate(paths,1):
        data=path.read_bytes();read_bytes+=len(data)
        inputs[str(path)]=hashlib.sha256(data).hexdigest()
        candidates=[m.group(1).decode().removeprefix(str(ROOT)+'/') for m in pattern.finditer(data)]
        candidates.extend(m.group(1).decode() for m in relative.finditer(data))
        for name in candidates:
            group='/'.join(name.split('/')[:3])
            groups[group]+=1
            if len(examples[group])<3 and name not in examples[group]:examples[group].append(name)
        if i%100==0:
            save(output.with_suffix('.status.json'),dict(state='scanning',completed=i,total=len(paths),
                 bytes_read=read_bytes,updated_at=datetime.now(timezone.utc).isoformat()))
            print(f'Retention inputs {i}/{len(paths)}',flush=True)
    report=dict(schema='v7-retained-input-path-audit-v1',securities=len(universe),documents=len(paths),
                bytes_read=read_bytes,referenced_groups=dict(groups),examples=dict(examples),inputs=inputs,
                scope='All 591 current demand/daily declarations and all 1773 feature/proposal declarations; current gate and kernel proof.',
                limitations='Path-reference scan, not deletion permission. Does not resolve all transitive historical/live dependencies or verify referenced data content.',
                deleted_files=0)
    binding=dict(source_sha256=sha(__file__),union_receipt_sha256=sha(audit/'complete.json'))
    with transaction(output) as temp:
        save(temp/'report.json',report);save(temp/'binding.json',binding)
        receipt(temp,dict(identity=identity(binding)))
    save(output.with_suffix('.status.json'),dict(state='complete',completed=len(paths),total=len(paths),
         updated_at=datetime.now(timezone.utc).isoformat()))
    print(json.dumps(dict(documents=len(paths),bytes_read=read_bytes,groups=len(groups))),flush=True)


if __name__=='__main__':main()
