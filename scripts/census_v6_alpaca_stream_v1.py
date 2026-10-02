"""Read-only lower-bound subscription census from retained October 1 inputs."""
import json,sys
from pathlib import Path
from datetime import date
import pandas as pd
sys.path.insert(0,'/home/healy/Coding/HealysV6')
from nn_meta.live.v6_market import MassiveMarket
from nn_meta.decision_contracts import DecisionContractSelector
class Cached(MassiveMarket):
 def __init__(self,root):
  self.root=root;self._chains={};self.evidence=[];self.clock=lambda:pd.Timestamp.now(tz='UTC')
 def pages(self,*a,**k):raise ValueError('No retained prior-date reference')
root=Path('/home/healy/Coding/HealysV6/nn_meta/live/v6_alpaca_paper')
release=Path('/home/healy/Coding/HealysV6/deploy/v6/releases/v6-cash-repair-20260913')
spec=json.loads((release/'baseline_spec.json').read_text());data=Path(json.loads((root/'data-index.json').read_text())['path'])
manifest=json.loads((data/'manifest.json').read_text());sel=DecisionContractSelector(Cached(root/'market'))
contracts=set();missing=[];counts={}
for symbol,entry in manifest['symbols'].items():
 try:
  raw=pd.read_parquet(data/entry['files']['raw']['path'],columns=['Close']);spot=float(raw.Close.iloc[-1]);items=set()
  dtes=spec['dte_grid_weekly'] if symbol in spec['weekly_symbols'] else spec['dte_grid']
  for dte in dtes:
   for side in ('C','P'):
    c=sel.select(symbol,as_of=date(2026,10,2),right=side,raw_spot=spot,target_dte=dte)
    if c:items.add(c.symbol)
  contracts.update(items);counts[symbol]=len(items)
 except Exception as e:missing.append(dict(symbol=symbol,error=str(e)))
r=dict(observed_at=pd.Timestamp.now(tz='UTC').isoformat(),basis='October 1 raw closes, retained October 1 catalogue for October 2 selection; no network',symbols_total=len(manifest['symbols']),symbols_with_references=len(counts),missing_references=missing,distinct_atm_contracts=len(contracts),contracts=sorted(contracts),counts=counts,documented_quote_subscription_limit=1000,complete_live_coverage=False)
p=Path('/home/healy/Coding/HealysBacktester/nn_meta/validation/v6-alpaca-provider-20261002-r0/stream-census.json');p.write_text(json.dumps(r,indent=2)+'\n')
print({k:v for k,v in r.items() if k not in ['contracts','counts','missing_references']});print('missing refs',len(missing))
