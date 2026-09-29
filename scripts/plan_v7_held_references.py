#!/usr/bin/env python3
"""Seal only dated reference gaps emitted by actual frozen execution paths."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshot', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    from nn_meta.v7.storage import sha, verify, identity, transaction, receipt
    from nn_meta.v7.packed_references import query
    from incubator.continual.storage import write
    a.snapshot, a.output = a.snapshot.resolve(), a.output.resolve()
    if not a.output.is_relative_to(ROOT / 'nn_meta/validation'):
        p.error('Separate validation plan required')
    verify(a.snapshot)
    binding = dict(schema='v7-actual-held-reference-demand-v1',
                   snapshot=str(a.snapshot), snapshot_sha256=sha(a.snapshot / 'complete.json'),
                   producer_sha256=sha(__file__))
    if a.output.exists(): verify(a.output, expected_identity=identity(binding)); return
    requests = json.loads((a.snapshot / 'requests.json').read_text())
    scopes = defaultdict(set)
    for sid, rid in json.loads((a.snapshot / 'security-requests.json').read_text()):
        row = requests[rid]
        if row['kind'] != 'contract_reference': continue
        if row['provider'] != 'massive': raise ValueError('Unsupported reference provider')
        query(row['contract'], row['date'])
        scopes[sid].add((row['contract'], row['date']))
    checkpoints = {}
    for sid, pairs in sorted(scopes.items()):
        target = a.output.with_suffix('.checkpoints') / sid
        child = dict(parent=binding, security_id=sid, pairs=sorted(pairs))
        if target.exists(): verify(target, expected_identity=identity(child))
        else:
            with transaction(target) as temp:
                with sqlite3.connect(temp / 'references.sqlite3') as db:
                    db.execute('CREATE TABLE requests(contract TEXT,date TEXT,PRIMARY KEY(contract,date)) WITHOUT ROWID')
                    db.executemany('INSERT INTO requests VALUES(?,?)', sorted(pairs))
                write(temp / 'binding.json', child)
                write(temp / 'report.json', dict(security_id=sid, contract_dates=len(pairs)))
                receipt(temp, dict(identity=identity(child), research_ready=False))
        checkpoints[sid] = sha(target / 'complete.json')
    report = dict(securities=len(scopes), contract_dates=sum(map(len, scopes.values())),
                  checkpoints=checkpoints, scope='Actual replay-frontier dated-reference gaps only',
                  full_execution_coverage=False, research_ready=False)
    with transaction(a.output) as temp:
        write(temp / 'binding.json', binding); write(temp / 'report.json', report)
        receipt(temp, dict(identity=identity(binding), research_ready=False))
    print(json.dumps({k: v for k, v in report.items() if k != 'checkpoints'}))


if __name__ == '__main__':
    main()
