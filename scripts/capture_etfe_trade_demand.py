"""Capture the exact missing trade intervals of the audited ETFE component pilot."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from nn_meta.etfe.trade_demand import prepare_trade_capture,run,report,verify


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['prepare','run','report','verify'])
    p.add_argument('--root',required=True,type=Path);p.add_argument('--pilot',type=Path)
    p.add_argument('--request-budget',type=int)
    a=p.parse_args();root=a.root.resolve()
    if root.parent!=ROOT/'nn_meta/data_cache_etfe' or not root.name.startswith('alpaca-fresh-'):
        p.error('Direct fresh ETFE root required')
    if a.request_budget is not None and a.request_budget<1:p.error('Positive request budget required')
    if a.command=='prepare':
        if a.pilot is None:p.error('--pilot required')
        r=prepare_trade_capture(root,a.pilot);print(json.dumps(dict(plan_sha256=r['sha256'],jobs=len(r['jobs']),preflight=r['parent']['preflight']),indent=2))
    elif a.command=='verify':print(json.dumps(dict(plan_sha256=verify(root)['sha256'])))
    elif a.command=='report':
        r=report(root);print(json.dumps({k:v for k,v in r.items() if k!='partitions'},indent=2))
    else:
        from dotenv import dotenv_values
        from nn_meta.etfe.acquisition import HTTP
        values=dotenv_values(ROOT/'.env');pair=(values.get('ALPACA_API_KEY'),values.get('ALPACA_API_SECRET'))
        if not all(pair):p.error('Missing Alpaca data credentials')
        r=run(root,HTTP({'data':pair}),a.request_budget)
        print(json.dumps({k:v for k,v in r.items() if k!='partitions'},indent=2))
        print(json.dumps(dict(partitions=len(r['partitions']),terminal=sum(x['terminal'] for x in r['partitions']),rows=sum(x['rows'] for x in r['partitions']))))
        if not r['capture_complete'] or r['stop_reason']:raise SystemExit(2)


if __name__=='__main__':main()
