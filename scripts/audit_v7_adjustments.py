"""Bounded full-cache diagnostic for common daily price factors and cent rounding."""
from pathlib import Path
import argparse
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def work(payload):
    root, relative, output = map(Path, payload)
    from nn_meta.v7.coverage import receipt_frame
    from nn_meta.v7.adjustments import daily_scale_bounds
    from nn_meta.v7.storage import transaction, receipt, verify, identity, sha
    inputs = [root / 'stock_1m' / basis / relative / 'complete.json' for basis in ('raw', 'all')]
    code = [Path(__file__), ROOT / 'nn_meta/v7/adjustments.py', ROOT / 'nn_meta/v7/coverage.py']
    source = {str(p): sha(p) for p in code}
    declaration = {'inputs': {str(p): sha(p) for p in inputs}, 'sources': source,
                   'adjusted_half_unit': .005000001, 'scope': 'diagnostic only; no vintage admission'}
    fingerprint = identity(declaration)
    destination = output / root.name / relative
    if destination.exists():
        verify(destination, expected_identity=fingerprint)
        return json.loads((destination / 'summary.json').read_text())
    _, raw = receipt_frame(root, inputs[0])
    _, adjusted = receipt_frame(root, inputs[1])
    rows = daily_scale_bounds(raw, adjusted, adjusted_half_unit=.005000001)
    summary = {'source': str(root), 'symbol_year': str(relative), 'rows': len(raw), 'days': len(rows),
               'incompatible_days': int((~rows.rounding_compatible.astype(bool)).sum()),
               'price_vintage_verified': False}
    with transaction(destination) as temp:
        rows.to_parquet(temp / 'daily_factors.parquet', index=False)
        (temp / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        (temp / 'declaration.json').write_text(json.dumps(declaration, indent=2) + '\n')
        if {str(p): sha(p) for p in code} != source:
            raise ValueError('Adjustment audit source changed during the run')
        receipt(temp, {'identity': fingerprint, 'research_ready': False})
    return summary


def main():
    from nn_meta.v7.runtime import worker_pool
    from scripts.download_v7_data import save
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sources', type=Path, nargs='+', required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--workers', type=int, required=True)
    args = ap.parse_args()
    if len({p.name for p in args.sources}) != len(args.sources):
        raise ValueError('Source roots must have distinct names')
    tasks = [(str(root), str(p.parent.relative_to(root / 'stock_1m/raw')), str(args.output))
             for root in args.sources for p in sorted((root / 'stock_1m/raw').glob('*/*/complete.json'))]
    summary = {'pairs': 0, 'rows': 0, 'days': 0, 'incompatible_days': 0,
               'total_pairs': len(tasks), 'research_ready': False}
    with worker_pool(args.workers, threads=1) as pool:
        for result in pool.map(work, tasks):
            summary['pairs'] += 1
            for key in ('rows', 'days', 'incompatible_days'):
                summary[key] += result[key]
            if summary['pairs'] % 20 == 0:
                save(args.output / 'status.json', summary)
    save(args.output / 'status.json', summary)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
