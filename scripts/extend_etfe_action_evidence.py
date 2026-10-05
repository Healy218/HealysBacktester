"""Capture the process-date tail and inspect bounded action mutations."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from nn_meta.etfe.action_evidence import prepare,verify,run,inspect,HTTP
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['prepare','verify','run','inspect'])
    p.add_argument('--root',type=Path,required=True);p.add_argument('--request-budget',type=int,default=32);a=p.parse_args();root=a.root.resolve()
    if root.parent!=ROOT/'nn_meta/data_cache_etfe' or not root.name.startswith('alpaca-fresh-actions-tail-'):p.error('Isolated tail root required')
    if a.request_budget<1:p.error('Positive request budget required')
    if a.command=='run':
        from dotenv import dotenv_values
        v=dotenv_values(ROOT/'.env');r=run(root,HTTP(v.get('ALPACA_API_KEY'),v.get('ALPACA_API_SECRET')),budget=a.request_budget)
    else:r={'prepare':prepare,'verify':verify,'inspect':inspect}[a.command](root)
    print(json.dumps({k:v for k,v in r.items() if k not in ('inputs','sources','jobs')},indent=2))
    if a.command=='run' and (not r['capture_complete'] or r['stop_reason']):raise SystemExit(2)
