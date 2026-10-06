"""Capture the full ETFE expiration range with six paginated Alpaca queries."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nn_meta.etfe import full_discovery as f
from scripts.expand_etfe_alpaca import credentials


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['prepare','run','audit'])
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--request-budget', type=int, default=1024)
    args = p.parse_args()
    root = args.root.resolve()
    if root.parent != ROOT/'nn_meta/data_cache_etfe' or not root.name.startswith('alpaca-fresh-'):
        p.error('Fresh isolated ETFE root required')
    if args.command == 'prepare':
        r = f.prepare(root, f.full_jobs(), parent=dict(scope='full_expiry_range_transport',
            calendar_inventory='nn_meta/validation/etfe-demand-20261004-r0', historical_eligibility_admitted=False))
        print(json.dumps(dict(sha256=r['sha256'], queries=len(r['jobs']), limits=r['limits'])))
    elif args.command == 'run':
        if not 1 <= args.request_budget <= 1024:
            p.error('Budget must be 1..1024')
        plan = f.load_plan(root)
        if plan['jobs'] != f.full_jobs():
            p.error('Full-range inventory changed')
        r = f.capture(root, f.HTTP(credentials()), request_budget=args.request_budget)
        print(json.dumps({k:r[k] for k in ('capture_complete','requests_this_run','stop_reason','elapsed_seconds')}))
        print(json.dumps(dict(complete_queries=sum(x['terminal'] for x in r['partitions']),
                              rows=sum(x['rows'] for x in r['partitions']))))
        if not r['capture_complete'] or r['stop_reason']:
            raise SystemExit(2)
    else:
        r = f.audit(root)
        f.save(root/'COVERAGE.json', r)
        print(json.dumps(dict(complete=r['capture_complete'], queries=len(r['partitions']),
                              rows=sum(x['rows'] for x in r['partitions']))))
