"""Prepare/capture/audit fresh daily option bars establishing dated ETFE contract existence."""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.etfe import existence_census as e, option_daily_capture as o
from scripts.expand_etfe_alpaca import credentials


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','run','audit'])
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--request-budget',type=int,default=128)
    args=parser.parse_args();root=args.root.resolve()
    if root.parent!=ROOT/'nn_meta/data_cache_etfe' or not root.name.startswith('alpaca-fresh-'):
        parser.error('Isolated fresh ETFE root required')
    if args.command=='prepare':
        r=e.prepare(root);print(json.dumps(dict(plan_sha256=r['sha256'],jobs=len(r['jobs']),limits=r['limits'])))
    elif args.command=='run':
        if not 1<=args.request_budget<=128:parser.error('Request budget must be 1..128')
        r=o.capture(root,o.HTTP(credentials()),request_budget=args.request_budget)
        print(json.dumps({k:r[k] for k in ('capture_complete','requests_this_run','stop_reason','elapsed_seconds')}))
        print(json.dumps(dict(partitions=len(r['partitions']),terminal=sum(p['terminal'] for p in r['partitions']),
            rows=sum(p['rows'] for p in r['partitions']))))
        if not r['capture_complete'] or r['stop_reason']:raise SystemExit(2)
    else:
        print(json.dumps(o.audit(root),indent=2))
