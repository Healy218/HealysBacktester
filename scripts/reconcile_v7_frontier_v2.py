#!/usr/bin/env python3
"""Subtract a newer sealed input epoch from an observed immutable frontier."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nn_meta.v7.storage import identity, receipt, sha, transaction, verify
from nn_meta.v7.quotes import capture_union
from scripts.capture_v7_recovery_frontier import subtract
from incubator.continual.storage import write


def missing_ticks(captures, db):
    for item in captures:
        scope = {k: item[k] for k in ('contract', 'kind', 'start_ns', 'end_ns')}
        ranges = db.execute('SELECT start_ns,end_ns FROM ranges WHERE contract=? AND kind=? '
                            'AND start_ns<? AND end_ns>? ORDER BY start_ns',
                            (item['contract'], item['kind'], item['end_ns'], item['start_ns']))
        for part in subtract(scope, ranges):
            yield dict(part, request_id=identity(part))


def reconcile(raw, quotes, references, output):
    raw, quotes, references, output = map(lambda p: Path(p).resolve(), (raw, quotes, references, output))
    for root in (raw, quotes, references):
        verify(root)
    inputs = {str(p / 'complete.json'): sha(p / 'complete.json') for p in (raw, quotes, references)}
    inputs[str(Path(__file__))] = sha(__file__)
    inputs[str(ROOT / 'scripts/capture_v7_recovery_frontier.py')] = sha(ROOT / 'scripts/capture_v7_recovery_frontier.py')
    for name in ('quotes.py', 'storage.py'):
        inputs[str(ROOT / 'nn_meta/v7' / name)] = sha(ROOT / 'nn_meta/v7' / name)
    binding = dict(schema='v7-reconciled-actual-frontier-v2', inputs=inputs,
                   original_snapshot=str(raw), previous_index=str(quotes), references=str(references))
    if output.exists():
        verify(output, expected_identity=identity(binding))
        return json.loads((output / 'report.json').read_text())
    requests = json.loads((raw / 'requests.json').read_text())
    links = json.loads((raw / 'security-requests.json').read_text())
    retained = []
    reused = []
    with sqlite3.connect((references / 'coverage.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
        for sid, rid in links:
            r = requests[rid]
            found = None
            if r['provider'] == 'massive' and r['kind'] == 'contract_reference':
                found = db.execute('SELECT admission,pack,receipt_sha256 FROM observed '
                                   'WHERE security_id=? AND contract=? AND date=?',
                                   (sid, r['contract'], r['date'])).fetchone()
            if found is None:
                retained.append([sid, rid])
            else:
                reused.append(dict(security_id=sid, request_id=rid, admission=found[0],
                                   pack=found[1], row_receipt_sha256=found[2]))
    wanted = {rid for _, rid in retained}
    remaining = {rid: requests[rid] for rid in sorted(wanted)}
    original = json.loads((raw / 'capture-plan.json').read_text())['captures']
    with sqlite3.connect((quotes / 'index.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
        union = capture_union(missing_ticks(original, db), max_span_ns=900_000_000_000)
    unsupported = [r for r in remaining.values() if not
                   (r['provider'] == 'massive' and r['kind'] in ('quotes', 'trades', 'contract_reference'))]
    report = dict(original_pending_rows=len(links), pending_rows=len(retained),
                  distinct_requests=len(remaining), reused_reference_links=len(reused),
                  reference_requests=sum(r['kind'] == 'contract_reference' for r in remaining.values()),
                  capture_windows=len(union['captures']), unsupported_requests=len(unsupported),
                  full_execution_coverage=False, research_ready=False)
    if any(sha(p) != h for p, h in inputs.items()):
        raise ValueError('Reconciliation input changed')
    with transaction(output) as temp:
        for name, value in [('binding', binding), ('report', report), ('requests', remaining),
                            ('security-requests', retained), ('capture-plan', union),
                            ('reused-references', reused), ('unsupported-requests', unsupported)]:
            write(temp / (name + '.json'), value)
        receipt(temp, dict(identity=identity(binding), research_ready=False))
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('raw', 'quotes', 'references', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    if not a.output.resolve().is_relative_to(ROOT / 'nn_meta/validation'):
        p.error('New validation output required')
    print(json.dumps(reconcile(a.raw, a.quotes, a.references, a.output)))
