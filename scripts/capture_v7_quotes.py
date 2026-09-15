"""Capture a bounded V7 request batch once per shared contract/time interval.

Request generation is separate from capture. Memberships survive unioning;
provider failures and observed-empty responses are never fabricated fills.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def capture_one(arguments):
    item, output, budget_root = arguments
    from dotenv import load_dotenv
    from options.data.massive_ticks import MassiveTicks, canonical_bytes, verify_capture
    from nn_meta.v7.storage import transaction, receipt, verify
    from scripts.download_v7_data import quota_update, tree_bytes, TASK_RESERVATION, disk_guard
    load_dotenv(ROOT / '.env')
    destination = Path(output) / item['capture_id']
    if destination.exists():
        doc = verify(destination, expected_identity=item['capture_id'])
        return {'capture_id': item['capture_id'], 'rows': doc['rows'], 'reused': True}
    root = Path(budget_root)
    disk_guard(root, 100)
    reservation = uuid.uuid4().hex
    quota_update(root, reserve=reservation)
    used = 0
    try:
        records, manifest = MassiveTicks().capture(item['contract'], item['kind'], item['start_ns'], item['end_ns'])
        verify_capture(records, manifest, contract=item['contract'], kind=item['kind'],
                       start_ns=item['start_ns'], end_ns=item['end_ns'])
        data = gzip.compress(canonical_bytes(records), mtime=0)
        if len(data) + len(canonical_bytes(manifest)) + 1024**2 > TASK_RESERVATION:
            raise ValueError('Quote shard exceeds reserved capacity; split its time window')
        with transaction(destination) as temporary:
            (temporary / 'records.json.gz').write_bytes(data)
            (temporary / 'capture.json').write_bytes(canonical_bytes(manifest))
            receipt(temporary, {'identity': item['capture_id'], 'rows': len(records),
                'capture': item, 'format': 'v7-frozen-option-capture-v1',
                'empty_is_unfilled': False, 'full_execution_coverage': False})
            used = tree_bytes(temporary)
        return {'capture_id': item['capture_id'], 'rows': len(records), 'reused': False}
    finally:
        # If transaction fails midway, charge any partial directory as well.
        if not destination.exists():
            used = sum(tree_bytes(p) for p in destination.parent.glob(destination.name + '.partial-*'))
        quota_update(root, finish=(reservation, used))


def main():
    from nn_meta.v7.quotes import capture_union
    from nn_meta.v7.runtime import worker_pool
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--requests', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--budget-root', type=Path, required=True)
    ap.add_argument('--workers', type=int, required=True)
    args = ap.parse_args()
    rows = json.loads(args.requests.read_text())
    if not isinstance(rows, list) or len(rows) > 10000:
        raise ValueError('Provide a bounded request batch of at most 10000 windows')
    output, budget = args.output.resolve(), args.budget_root.resolve()
    if not output.is_relative_to(budget) or not (budget / 'quota.json').exists():
        raise ValueError('Capture output must be inside an initialized acquisition budget')
    union = capture_union(rows)
    from scripts.download_v7_data import quota_update, TASK_RESERVATION, save
    metadata_reservation = uuid.uuid4().hex
    encoded_plan = json.dumps(union, sort_keys=True, indent=2) + '\n'
    if len(encoded_plan.encode()) > TASK_RESERVATION // 2:
        raise ValueError('Request metadata exceeds a bounded batch; split the request list')
    quota_update(budget, reserve=metadata_reservation)
    output.mkdir(parents=True, exist_ok=True)
    plan_path = output / 'requests.json'
    metadata_paths = [plan_path, output / 'report.json']
    before = sum(p.stat().st_size for p in metadata_paths if p.exists())
    try:
        if plan_path.exists() and json.loads(plan_path.read_text()) != union:
            raise ValueError('Capture batch identity changed; use another output')
        save(plan_path, union)
        results = []
        # Pool.map can eagerly queue work, so submit only one bounded worker group.
        with worker_pool(args.workers, threads=1) as pool:
            for start in range(0, len(union['captures']), args.workers):
                group = union['captures'][start:start + args.workers]
                results.extend(pool.map(capture_one, [(c, str(output), str(budget)) for c in group]))
        report = {'requests': len(rows), 'distinct_captures': len(union['captures']),
                  'results': results, 'full_execution_coverage': False}
        save(output / 'report.json', report)
    finally:
        after = sum(p.stat().st_size for p in metadata_paths if p.exists())
        quota_update(budget, finish=(metadata_reservation, max(after - before, 0)))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
