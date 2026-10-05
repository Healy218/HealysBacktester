"""Prepare/capture/normalize/audit finite fresh ETFE historical SIP quotes."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nn_meta.etfe import stock_quote_capture as q, stock_quote_pilot as p
from scripts.expand_etfe_alpaca import credentials


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run', 'normalize', 'audit'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--calendar', type=Path)
    parser.add_argument('--request-budget', type=int, default=128)
    args = parser.parse_args()
    root = args.root.resolve()
    if root.parent != ROOT/'nn_meta/data_cache_etfe' or not root.name.startswith('alpaca-fresh-'):
        parser.error('Isolated fresh ETFE root required')
    if args.command == 'prepare':
        if not args.calendar:
            parser.error('--calendar required')
        r = p.prepare(root, args.calendar)
        print(json.dumps(dict(plan_sha256=r['sha256'], jobs=len(r['jobs']), limits=r['limits'])))
    elif args.command == 'run':
        p.verify(root)
        if not 1 <= args.request_budget <= 128:
            parser.error('Request budget must be 1..128')
        r = q.capture(root, q.HTTP(credentials()), request_budget=args.request_budget)
        print(json.dumps({k:r[k] for k in ('capture_complete', 'requests_this_run', 'stop_reason', 'elapsed_seconds')}))
        if not r['capture_complete'] or r['stop_reason']:
            raise SystemExit(2)
    elif args.command == 'normalize':
        r = p.normalize(root)
        print(json.dumps(dict(rows=r['rows'], pages=len(r['page_receipts']), payload_bytes=r['raw_payload_bytes'])))
    else:
        r = p.audit(root)
        q.save(root/'INDEPENDENT_AUDIT.json', r)
        print(json.dumps(r))
