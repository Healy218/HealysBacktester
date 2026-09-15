"""Bounded resumable audits and whole-market PIT daily reduction from V7 receipts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def work(item):
    kind, key, source, output, calendar = item
    from nn_meta.v7.storage import transaction, receipt, verify, sha, identity
    from scripts.download_v7_data import completed
    target = Path(output) / kind / key
    inputs = ([Path(source) / f'stock_1m/{b}/{key}/complete.json' for b in ('raw', 'all')]
              if kind == 'stock' else [Path(source) / f'options/day_aggs/{key}/complete.json'])
    fingerprint = identity({'inputs': {str(p): sha(p) for p in inputs}, 'calendar': calendar,
                            'code': {str(p.relative_to(ROOT)): sha(p) for p in
                                     [Path(__file__), ROOT/'nn_meta/v7/coverage.py', ROOT/'nn_meta/universe_pit.py']}})
    if target.exists():
        verify(target, expected_identity=fingerprint)
        return {'kind': kind, 'key': key, 'status': 'reused'}
    with transaction(target) as temporary:
        if kind == 'stock':
            from nn_meta.v7.coverage import audit_pair
            symbol, year = key.split('/')
            summary, sessions, daily = audit_pair(source, symbol, year, calendar)
            sessions.to_parquet(temporary/'sessions.parquet', index=False)
            daily.to_parquet(temporary/'daily.parquet', index=False)
        else:
            import pandas as pd
            from nn_meta.universe_pit import daily_rows_from_day_aggs
            doc = json.loads(inputs[0].read_text())
            if ((Path(source) / doc['task']['key'] / 'complete.json').resolve() != inputs[0].resolve()
                    or completed(Path(source), doc['task']) != doc):
                raise ValueError('Option receipt does not match the verified task path')
            paths = [inputs[0].parent/n for n in doc['files'] if n.endswith('.csv.gz')]
            if len(paths) != 1:
                raise ValueError('Expected one captured daily aggregate')
            raw = pd.read_csv(paths[0])
            for name in ('close', 'volume', 'transactions'):
                import numpy as np
                if not np.isfinite(raw[name]).all() or (raw[name] < 0).any():
                    raise ValueError('Invalid whole-market daily aggregate')
            daily = daily_rows_from_day_aggs(raw, key)
            daily.to_parquet(temporary/'roots.parquet', index=False)
            # Preserve all observed contracts for a prior-date chain, independent of outcomes.
            raw.to_parquet(temporary/'contracts.parquet', index=False)
            summary = {'date': key, 'roots': len(daily), 'contracts': len(raw),
                       'input_receipt_sha256': sha(inputs[0])}
        (temporary/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
        receipt(temporary, {'identity': fingerprint, 'kind': kind, 'key': key, 'research_ready': False})
    return {'kind': kind, 'key': key, 'status': 'audited'}


def main():
    from nn_meta.v7.runtime import worker_pool
    from scripts.download_v7_data import save
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--limit', type=int)
    args = ap.parse_args()
    calendar = json.loads((args.source/'calendar.json').read_text())
    jobs = [('stock', str(p.parent.relative_to(args.source/'stock_1m/raw')))
            for p in sorted((args.source/'stock_1m/raw').glob('*/*/complete.json'))]
    jobs += [('options', p.parent.name) for p in sorted((args.source/'options/day_aggs').glob('*/complete.json'))]
    if args.limit:
        jobs = jobs[:args.limit]
    args.output.mkdir(parents=True, exist_ok=True)
    results = []; started = time.time()
    with worker_pool(args.workers) as pool:
        for first in range(0, len(jobs), args.workers):
            group = jobs[first:first+args.workers]
            for result in pool.map(work, [(k, key, str(args.source), str(args.output), calendar) for k,key in group]):
                results.append(result)
            save(args.output/'status.json', {'total': len(jobs), 'completed':len(results),
                 'seconds': time.time()-started, 'last': results[-1], 'research_ready': False})
            print(json.dumps({'completed':len(results),'total':len(jobs),'last':results[-1]}),flush=True)
    save(args.output/'complete.json', {'total':len(jobs),'completed':len(results), 'research_ready':False})


if __name__ == '__main__':
    main()
