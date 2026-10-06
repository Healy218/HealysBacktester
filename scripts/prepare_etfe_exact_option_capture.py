"""Prepare exact pending option windows, reusing the bounded density pilot."""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.etfe import acquisition as a, exact_windows as e


def prepare(root,demand_root,pilot_root):
    plan=e.load(demand_root)
    demand=json.loads((demand_root/'DEMAND.json').read_text())
    audit=json.loads((pilot_root/'WINDOW_CHECK_AUDIT.json').read_text())
    if audit['plan_sha256'] != json.loads((pilot_root/'PLAN.json').read_text())['sha256']:
        raise ValueError('Pilot audit/plan mismatch')
    pilot_plan=json.loads((pilot_root/'PLAN.json').read_text())
    pilot_windows=defaultdict(list)
    for j in pilot_plan['jobs']:
        if j['route'] not in ('option_bars','option_trades'):
            continue
        pilot_windows[j['params']['symbols'],j['route']].append((
            pd.Timestamp(j['params']['start']).value,
            pd.Timestamp(j['params']['end']).value+1))
    grouped=defaultdict(set); physical_units=0; reused_units=0
    for item in demand['physical']:
        route,symbol=item['route'],item['symbol']
        for start,end in item['pending_intervals']:
            pieces=[(start,end)]
            for lo,hi in pilot_windows[symbol,route]:
                new=[]
                for x,y in pieces:
                    if hi<=x or lo>=y:new.append((x,y))
                    else:
                        reused_units+=max(0,min(y,hi)-max(x,lo))
                        if x<lo:new.append((x,lo))
                        if hi<y:new.append((hi,y))
                pieces=new
            physical_units+=end-start
            for x,y in pieces:
                if x<y:grouped[route,x,y].add(symbol)
    jobs=[]
    for (route,start,end),symbols in sorted(grouped.items()):
        ordered=sorted(symbols)
        for pos in range(0,len(ordered),100):
            batch=ordered[pos:pos+100]
            params=dict(symbols=','.join(batch),sort='asc',limit=10000,
                start=pd.Timestamp(start,tz='UTC').isoformat(),
                end=pd.Timestamp(end-1,tz='UTC').isoformat())
            if route=='option_bars':params['timeframe']='1Min'
            jobs.append(a.job(route,params,'exact_signal_option_window'))
    parent=dict(exact_root=str(demand_root),exact_plan_sha256=plan['sha256'],
        demand_sha256=a.sha((demand_root/'DEMAND.json').read_bytes()),
        pilot_root=str(pilot_root),pilot_plan_sha256=pilot_plan['sha256'],
        pilot_audit_sha256=a.sha((pilot_root/'WINDOW_CHECK_AUDIT.json').read_bytes()),
        unique_exact_intervals=len(jobs),physical_interval_symbol_ns=physical_units,
        pilot_overlap_symbol_ns=reused_units,
        budget='Source-bound tranche; 128 GET/run, 1s pacing, 512 MiB root and free-space guards; historical eligibility false')
    result=a.prepare(root,jobs,parent=parent)
    a.write_new(root/'PREPARE_SOURCE.py',Path(__file__).read_bytes())
    return dict(plan_sha256=result['sha256'],jobs=len(jobs),
        estimated_minimum_gets=len(jobs),pilot_overlap_symbol_minutes=reused_units//60_000_000_000,
        physical_symbol_minutes=physical_units//60_000_000_000)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--demand-root',type=Path,required=True)
    parser.add_argument('--pilot-root',type=Path,required=True)
    args=parser.parse_args();root=args.root.resolve()
    if root.parent!=ROOT/'nn_meta/data_cache_etfe' or not root.name.startswith('alpaca-fresh-'):
        parser.error('Direct isolated Alpaca fresh root required')
    print(json.dumps(prepare(root,args.demand_root.resolve(),args.pilot_root.resolve()),indent=2))
