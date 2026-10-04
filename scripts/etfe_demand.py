"""Enumerate ETFE calendar demand and capture bounded January option coverage."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.etfe.acquisition import HTTP,capture,save
from nn_meta.etfe.demand import (build_inventory,coverage_report,january_bars,
    january_discovery,load_inventory,prepare_capture,verify_capture)
from scripts.expand_etfe_alpaca import credentials
from nn_meta.etfe.expansion import read_calendar


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['inventory','discovery','boundary','surfaces','run','report'])
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--inventory',type=Path)
    p.add_argument('--calendar',type=Path)
    p.add_argument('--setup',type=Path)
    p.add_argument('--input',type=Path,action='append',default=[])
    p.add_argument('--request-budget',type=int)
    a=p.parse_args();root=a.root.resolve()
    parent=ROOT/('nn_meta/validation' if a.command=='inventory' else 'nn_meta/data_cache_etfe')
    prefix='etfe-demand-' if a.command=='inventory' else 'alpaca-fresh-'
    if root.parent!=parent or not root.name.startswith(prefix):p.error('Isolated ETFE root required')
    if a.command=='inventory':
        if a.calendar is None or a.setup is None:p.error('--calendar and --setup required')
        r=build_inventory(root,a.calendar,a.setup,a.input)
        print(json.dumps(dict(sha256=r['sha256'],**r['summary'])))
    elif a.command=='run':
        verify_capture(root);r=capture(root,HTTP(credentials()),request_budget=a.request_budget)
        print(json.dumps({k:r[k] for k in ('capture_complete','requests_this_run','stop_reason','elapsed_seconds','peak_rss_bytes')}))
        print(json.dumps(dict(partitions=len(r['partitions']),terminal=sum(x['terminal'] for x in r['partitions']),rows=sum(x['rows'] for x in r['partitions']))))
        if not r['capture_complete'] or r['stop_reason']:raise SystemExit(2)
    elif a.command=='report':
        r=coverage_report(root);save(root/'COVERAGE.json',r)
        print(json.dumps({k:v for k,v in r.items() if k not in ('partitions','per_symbol','rows_by_ticker_day')}))
    else:
        if a.inventory is None:p.error('--inventory required')
        inventory=load_inventory(a.inventory)
        jobs,details=january_discovery(inventory) if a.command=='discovery' else january_bars(
            a.input,a.command,read_calendar(inventory['calendar_root']))
        r=prepare_capture(root,jobs,a.command,inventory,**details)
        print(json.dumps(dict(plan_sha256=r['sha256'],jobs=len(jobs),
            discovered_symbols=details.get('discovered_symbols'),symbol_windows=len(details.get('symbol_window_edges',[])),
            reused_symbol_windows=len(details.get('reused_symbol_windows',[])),
            regular_minute_scenario_rows=details.get('regular_minute_scenario_rows'))))


if __name__=='__main__':main()
