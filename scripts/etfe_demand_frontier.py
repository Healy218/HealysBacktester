"""Build the measured ETFE frontier or run its bounded next discovery batch."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nn_meta.etfe import demand_frontier as d
from nn_meta.etfe.acquisition import HTTP
from scripts.expand_etfe_alpaca import credentials


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['build', 'prepare', 'run'])
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--inventory', type=Path)
    p.add_argument('--input', type=Path, action='append', default=[])
    p.add_argument('--frontier', type=Path)
    p.add_argument('--request-budget', type=int, default=128)
    args = p.parse_args()
    root = args.root.resolve()
    parent = ROOT/('nn_meta/validation' if args.command == 'build' else 'nn_meta/data_cache_etfe')
    prefix = 'etfe-demand-frontier-' if args.command == 'build' else 'alpaca-fresh-'
    if root.parent != parent or not root.name.startswith(prefix):
        p.error('Isolated ETFE root required')
    if args.command == 'build':
        if not args.inventory or not args.input:
            p.error('--inventory and --input required')
        r = d.build(root, args.inventory, args.input)
        print(json.dumps(dict(sha256=r['sha256'], **r['summary'], budget=r['budget'])))
    elif args.command == 'prepare':
        if not args.frontier:
            p.error('--frontier required')
        r = d.prepare(root, args.frontier)
        print(json.dumps(dict(sha256=r['sha256'], jobs=len(r['jobs']), limits=r['limits'])))
    else:
        r = d.run(root, HTTP(credentials()), args.request_budget)
        print(json.dumps({k:r[k] for k in ('capture_complete', 'requests_this_run', 'stop_reason', 'elapsed_seconds')}))
        if not r['capture_complete'] or r['stop_reason']:
            raise SystemExit(2)


if __name__ == '__main__':
    main()
