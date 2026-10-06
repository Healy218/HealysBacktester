"""Audit the bounded option-window density sample and VOO gap rechecks."""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nn_meta.etfe import acquisition as a


def audit(root):
    root = Path(root)
    plan = a.load_plan(root)
    captured = a.audit(root)
    jobs = plan['jobs']
    if not captured['capture_complete'] or len(jobs) != 36:
        raise ValueError('Capture is incomplete or request census changed')
    gap_results, route = [], {'option_bars': [], 'option_trades': []}
    for item in jobs:
        rows = list(a.iter_records(root, item))
        if item['purpose'].startswith('recheck_missing_stock_minute:'):
            stamp = item['purpose'].split(':', 1)[1]
            target = pd.Timestamp(stamp).value
            returned = [pd.Timestamp(row['raw']['t']).value for row in rows]
            gap_results.append(dict(timestamp=stamp, rows=len(rows),
                exact_minute_returned=target in returned,
                controls=[pd.Timestamp(item['params']['start']).isoformat(),
                    pd.Timestamp(item['params']['end']).isoformat()]))
        else:
            route[item['route']].append(dict(job_id=item['id'],
                symbol=item['params']['symbols'], rows=len(rows),
                first_ns=min((pd.Timestamp(x['raw']['t']).value for x in rows), default=None),
                last_ns=max((pd.Timestamp(x['raw']['t']).value for x in rows), default=None)))
    if len(gap_results) != 12 or any(x['exact_minute_returned'] for x in gap_results):
        raise ValueError('Unexpected recheck result; inspect source intervals')
    result = dict(schema='etfe-window-check-audit-v1', plan_sha256=plan['sha256'],
        capture_complete=True, partitions=len(captured['partitions']),
        total_rows=sum(x['rows'] for x in captured['partitions']),
        voo_missing_minutes_rechecked=len(gap_results),
        voo_missing_minutes_recovered=sum(x['exact_minute_returned'] for x in gap_results),
        gap_results=gap_results, density_pilot=route,
        density_pilot_rows={k: sum(x['rows'] for x in v) for k,v in route.items()},
        historical_admission=False, ready_for_build=False, ready_for_training=False,
        auditor_sha256=a.sha(Path(__file__).read_bytes()))
    a.save(root/'WINDOW_CHECK_AUDIT.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.root.resolve()), indent=2))
