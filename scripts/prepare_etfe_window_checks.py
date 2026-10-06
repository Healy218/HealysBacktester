"""Prepare a finite exact-window density pilot and recheck every VOO stock gap."""
import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nn_meta.etfe import acquisition as a, exact_windows as e, window_demand as w


def prepare(root, demand_root):
    plan = e.load(demand_root)
    path = demand_root / 'DEMAND.json'
    demand = json.loads(path.read_text())
    chart = pq.read_table(Path(plan['source']) / 'VOO-1/chart.parquet').to_pandas()
    # Read the actual chart's missing inputs; never replace them with synthetic bars.
    missing = chart.index[~chart['valid']]
    jobs = []
    for stamp in missing:
        start, end = stamp - pd.Timedelta(minutes=1), stamp + pd.Timedelta(minutes=2)
        jobs.append(a.job('stock_bars', dict(symbols='VOO', timeframe='1Min',
            feed='sip', adjustment='raw', asof='-', sort='asc', limit=10000,
            start=start.isoformat(), end=(end-pd.Timedelta(1,'ns')).isoformat()),
            'recheck_missing_stock_minute:' + stamp.isoformat()))
    selected = []
    # Four duration order statistics per ticker/route, including both extremes.
    # A density pilot is deliberately not an unbiased full-campaign estimate.
    for ticker in a.SYMBOLS:
        for route in ('option_bars', 'option_trades'):
            intervals = sorted((y-x, r['symbol'], x, y)
                for r in demand['physical'] if r['route'] == route and r['symbol'].startswith(ticker)
                for x,y in r['pending_intervals'])
            if not intervals:
                continue
            indices = sorted({0, (len(intervals)-1)//3, 2*(len(intervals)-1)//3, len(intervals)-1})
            for i in indices:
                duration, symbol, start, end = intervals[i]
                params = dict(symbols=symbol, sort='asc', limit=10000,
                    start=pd.Timestamp(start,tz='UTC').isoformat(),
                    end=pd.Timestamp(end-1,tz='UTC').isoformat())
                if route == 'option_bars':
                    params['timeframe'] = '1Min'
                item = a.job(route, params, 'exact_window_density_pilot')
                jobs.append(item)
                selected.append(dict(job_id=item['id'], ticker=ticker, route=route,
                    rank=i, population=len(intervals), symbol_minutes=duration//w.MINUTE))
    if len(missing) != 12 or len(jobs) > 36:
        raise ValueError('Declared twelve gaps / at most 24 option windows changed')
    parent = dict(demand_root=str(demand_root), demand_sha256=a.sha(path.read_bytes()),
        plan_sha256=plan['sha256'], script_sha256=a.sha(Path(__file__).read_bytes()),
        missing_stock_minutes=[s.isoformat() for s in missing], selected=selected,
        budget='36 jobs; existing 128 GET/run, 512 MiB root and reserve guards; no bulk authorization')
    result = a.prepare(root, jobs, parent=parent)
    a.write_new(root/'PREPARE_SOURCE.py', Path(__file__).read_bytes())
    return dict(plan_sha256=result['sha256'], jobs=len(jobs), stock_gap_queries=len(missing),
        option_queries=len(selected))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--demand-root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    if root.parent != ROOT/'nn_meta/data_cache_etfe' or not root.name.startswith('alpaca-fresh-'):
        parser.error('Isolated fresh ETFE root required')
    print(json.dumps(prepare(root, args.demand_root.resolve()), indent=2))
