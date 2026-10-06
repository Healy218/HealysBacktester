"""Reconcile full announcement observations to independently captured action terms."""
import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
import sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.etfe.acquisition import sha,digest,save
from scripts import capture_etfe_full_announcements_v2 as capture


def audit(root):
    root=Path(root);p=json.loads((root/'PLAN.json').read_text())
    if digest({k:v for k,v in p.items() if k!='sha256'})!=p['sha256'] or p['queries']!=capture.inventory():raise ValueError('Plan drift')
    if sha((root/'SOURCE.py').read_bytes())!=sha(Path(capture.__file__).read_bytes()):raise ValueError('Source drift')
    records=[]
    for n,q in enumerate(p['queries']):
        receipt=json.loads((root/f'{n:02d}/receipt.json').read_text());raw=(root/f'{n:02d}/body').read_bytes()
        if receipt['status']!=200 or receipt['error'] or receipt['params']!=q or sha(raw)!=receipt['body_sha256'] or receipt['plan_sha256']!=p['sha256']:raise ValueError('Invalid announcement receipt')
        body=json.loads(raw)
        if not isinstance(body,list):raise ValueError('Response is not a record list')
        for ordinal,r in enumerate(body):
            if r['initiating_symbol']!=q['symbol'] or not q['since']<=r['ex_date']<=q['until']:raise ValueError('Out-of-query action')
            records.append(dict(symbol=r['initiating_symbol'],ex_date=r['ex_date'],declaration_date=r.get('declaration_date'),
                raw_json=json.dumps(r,sort_keys=True,separators=(',',':')),query=n,ordinal=ordinal,body_sha256=receipt['body_sha256'],
                observed_at=receipt['received_at'],historical_available_at=None,historical_revision_history_complete=False))
    sources=[ROOT/'nn_meta/data_cache_etfe/alpaca-fresh-actions-20261005-r0/ACTIONS.parquet',
             ROOT/'nn_meta/data_cache_etfe/alpaca-fresh-actions-tail-20261005-r0/OBSERVATIONS.json']
    prior=[json.loads(x) for x in pd.read_parquet(sources[0]).raw_json]
    prior.extend(x['raw'] for x in json.loads(sources[1].read_text())['tail_occurrences'])
    actions={}
    for r in prior:
        if '2024-01-01'<=r.get('ex_date','')<='2026-10-02':actions[r['symbol'],r['ex_date']]=r
    observed={};conflicts=[]
    for r in records:
        key=r['symbol'],r['ex_date'];raw=json.loads(r['raw_json'])
        if key in observed:raise ValueError('Duplicate action key needs explicit reconciliation')
        observed[key]=raw
        if key in actions:
            a=actions[key]
            if any(raw.get(k)!=a.get(k) for k in ('record_date','payable_date')) or Decimal(raw['cash'])!=Decimal(str(a['rate'])):
                conflicts.append(key)
    result=dict(schema='etfe-full-announcement-reconciliation-v1',plan_sha256=p['sha256'],queries=len(p['queries']),
        transport_complete=True,occurrences=len(records),by_symbol=dict(Counter(r['symbol'] for r in records)),
        by_type=dict(Counter(r['ca_type'] for r in observed.values())),prior_in_window_actions=len(actions),
        missing_prior_actions=sorted(set(actions)-set(observed)),additional_announcements=sorted(set(observed)-set(actions)),term_conflicts=conflicts,
        declaration_date_present=sum(bool(r['declaration_date']) for r in records),
        declaration_before_ex_date=sum(bool(r['declaration_date']) and r['declaration_date']<r['ex_date'] for r in records),
        records=records,source_hashes={str(s.relative_to(ROOT)):sha(s.read_bytes()) for s in sources},
        audit_source_sha256=sha(Path(__file__).read_bytes()),historical_available_at_admitted=False,revision_history_admitted=False)
    target=root/'RECONCILIATION.json'
    if target.exists():
        if json.loads(target.read_text())!=json.loads(json.dumps(result)):raise ValueError('Reconciliation changed')
    else:save(target,result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);a=p.parse_args();r=audit(a.root)
    print(json.dumps({k:v for k,v in r.items() if k!='records'},indent=2))
