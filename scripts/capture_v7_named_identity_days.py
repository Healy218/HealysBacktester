"""Capture a finite list of missing dated listing witnesses under the shared quota."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from nn_meta.v7.runtime import worker_pool
    from nn_meta.v7.daily_identities import EXCHANGES
    from nn_meta.v7.storage import sha
    from scripts.capture_v7_daily_identities import capture
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('requests', 'calendar', 'output', 'budget-root'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--workers', type=int, required=True)
    args = parser.parse_args()
    days = json.loads(args.requests.read_text())
    sessions = {r['date'] for r in json.loads(args.calendar.read_text())['sessions']}
    if (not isinstance(days, list) or not days or len(days) > 10 or len(set(days)) != len(days)
            or any(d not in sessions for d in days) or not 1 <= args.workers <= 4
            or not args.output.resolve().is_relative_to(args.budget_root.resolve())
            or not args.budget_root.resolve().is_relative_to(ROOT/'nn_meta')):
        raise ValueError('One to ten named captured-calendar days and shared repository quota required')
    sources = {str(p): sha(p) for p in [Path(__file__), args.requests, args.calendar,
        ROOT/'scripts/capture_v7_daily_identities.py', ROOT/'scripts/download_v7_data.py',
        *[ROOT/'nn_meta/v7'/(n+'.py') for n in ('daily_identities','runtime','storage','action_inventory')]]}
    tasks = [(day, exchange, args.output, args.budget_root, sources)
             for day in days for exchange in EXCHANGES]
    with worker_pool(args.workers, threads=1) as pool:
        for result in pool.map(capture, tasks, chunksize=1):
            print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
