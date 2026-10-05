"""Prepare/capture/reconcile bounded ETFE action-event replay."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from nn_meta.etfe.action_replay import prepare,verify,run,reconcile,HTTP
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','verify','run','reconcile']);p.add_argument('--root',required=True,type=Path);p.add_argument('--request-budget',type=int,default=96);a=p.parse_args();root=a.root.resolve()
    if root.parent!=ROOT/'nn_meta/data_cache_etfe' or not root.name.startswith('alpaca-fresh-action-replay-'):p.error('Isolated replay root required')
    if a.request_budget<1:p.error('Positive request budget required')
    if a.command=='run':
        from dotenv import dotenv_values
        v=dotenv_values(ROOT/'.env');r=run(root,HTTP(v.get('ALPACA_API_KEY'),v.get('ALPACA_API_SECRET')),budget=a.request_budget)
    else:r={'prepare':prepare,'verify':verify,'reconcile':reconcile}[a.command](root)
    print(json.dumps({k:v for k,v in r.items() if k not in ('sources','inputs','action_witnesses')},indent=2))
    if a.command=='run' and (not r['transport_complete'] or r['stop_reason']):raise SystemExit(2)
