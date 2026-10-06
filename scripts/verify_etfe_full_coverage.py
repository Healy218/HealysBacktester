"""Independently reconcile full-range raw, normalized and calendar occurrences."""
import argparse
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
import json
import re
from pathlib import Path
import sys
import pandas as pd
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.etfe import full_discovery as f
from nn_meta.etfe.full_coverage import load
from nn_meta.etfe.expansion import read_calendar
from nn_meta.etfe.demand import load_inventory


def audit(root):
    root=Path(root);plan=load(root)
    seal=json.loads((root/'CENSUS.json').read_text())
    raw_root=Path(plan['raw_root']);raw_plan=f.load_plan(raw_root)
    symbols={};counts=Counter();flags=Counter();checked={};total=0;quality=Counter()
    for job in raw_plan['jobs']:
        history,_,done=f.committed(raw_root,job)
        if not done:raise ValueError('Incomplete raw range')
        for page,(receipt,body,_) in enumerate(history):
            key=f'{job["id"]}-{page:06d}'
            pointer=root/'partitions'/(key+'.json')
            if f.sha(pointer.read_bytes())!=seal['page_receipts'][key]:raise ValueError('Receipt changed')
            meta=json.loads(pointer.read_text());path=root/meta['data']
            if f.sha(path.read_bytes())!=meta['data_sha256']:raise ValueError('Partition changed')
            actual=pq.read_table(path).to_pylist();expected=body['option_contracts'] or []
            if len(actual)!=len(expected) or len(expected)!=meta['rows']:raise ValueError('Row count')
            for ordinal,(raw,row) in enumerate(zip(expected,actual)):
                symbol=raw['symbol'];symbols[symbol]=raw
                standard=re.fullmatch(r'(SPY|QQQ|VOO)\d{6}[CP]\d{8}',symbol) is not None
                quality.update(row['quality_flags'])
                if not standard and (row['underlying']!=symbol or any(row[k] is not None for k in ('expiration_date','right','strike')) or not {'unparsed_option_identity','contract_identity_mismatch'}<=set(row['quality_flags'])):
                    raise ValueError('Adjusted identity lost its explicit missing state')
                counts[raw['underlying_symbol'],raw['expiration_date'],raw['status']]+=1
                if (row['raw_json']!=json.dumps(raw,sort_keys=True,separators=(',',':'))
                    or row['symbol']!=symbol or (standard and (row['underlying']!=raw['underlying_symbol']
                    or str(row['expiration_date'])!=raw['expiration_date'] or row['right']!=raw['type']
                    or Decimal(str(row['strike']))!=Decimal(raw['strike_price'])))
                    or row['multiplier_raw']!=str(raw['multiplier']) or row['size_raw']!=str(raw['size'])
                    or row['deliverables_json']!=json.dumps(raw.get('deliverables'),sort_keys=True,separators=(',',':'))
                    or row['occurrence_id']!=f.digest([raw_plan['sha256'],job['id'],page,ordinal,receipt['body_sha256']])
                    or row['body_sha256']!=receipt['body_sha256'] or row['job_id']!=job['id']
                    or row['page']!=page or row['ordinal']!=ordinal
                    or row['capture_plan_sha256']!=raw_plan['sha256']
                    or row['received_at_ns']!=pd.Timestamp(receipt['received_at']).value
                    or row['record_use']!='discovery_only_not_historical_feature'
                    or any(row[k] is not None for k in ('timestamp_ns','timestamp_raw','session_date','calendar_dte'))):
                    raise ValueError(f'Typed occurrence mismatch: {key}:{ordinal}')
                flags['current_snapshot_not_dated_contract_terms']+=1
                if not raw.get('effective_at'):flags['terms_effective_at_absent']+=1
                if not raw.get('available_at'):flags['terms_available_at_absent']+=1
                try:valid=Decimal(str(raw.get('multiplier'))).is_finite() and Decimal(str(raw.get('multiplier')))>0
                except Exception:valid=False
                if not valid:flags['nonpositive_or_invalid_raw_multiplier']+=1
                if raw['expiration_date']<'2024-05-28' and any(d.get('settlement_type')=='T+1' for d in raw.get('deliverables',[])):
                    flags['current_T1_delivery_on_pre_transition_expiry']+=1
                if not raw.get('deliverables'):flags['deliverables_absent']+=1
            total+=len(actual);checked[key]=len(actual)
    if set(checked)!=set(seal['page_receipts']):raise ValueError('Partition inventory mismatch')
    required=load_inventory(plan['inventory_root'])['queries']
    if {q['query_key'] for q in seal['exact_queries']}!=set(required):raise ValueError('Calendar query mismatch')
    for q in seal['exact_queries']:
        if q['returned_occurrences']!=counts[q['underlying'],q['expiry'],q['status']]:raise ValueError('Expiry count')
    by_expiry=Counter((r['underlying_symbol'],date.fromisoformat(r['expiration_date'])) for r in symbols.values())
    calendar=read_calendar(plan['calendar_root']);surfaces=[]
    for session in calendar:
        day=date.fromisoformat(session['date'])
        minutes=int((pd.Timestamp(session['date']+' '+session['close'])-pd.Timestamp(session['date']+' '+session['open'])).total_seconds()/60)
        for ticker in f.SYMBOLS:
            sizes=[by_expiry[ticker,day+timedelta(days=i)] for i in range(46)]
            surfaces.append(dict(ticker=ticker,session=session['date'],returned_symbols=sum(sizes),purchase_symbols=sum(sizes[:6]),
                gross_bar_queries=(sum(sizes)+99)//100,regular_minute_scenario_rows=sum(sizes)*minutes))
    if surfaces!=seal['surfaces'] or dict(flags)!=seal['dated_reason_counts']:raise ValueError('Census mismatch')
    if total!=seal['summary']['returned_occurrences'] or len(symbols)!=seal['summary']['unique_symbols']:raise ValueError('Totals mismatch')
    return dict(schema='etfe-independent-full-coverage-v1',plan_sha256=plan['sha256'],census_sha256=f.sha((root/'CENSUS.json').read_bytes()),
        audit_source_sha256=f.sha(Path(__file__).read_bytes()),partitions=len(checked),occurrences=total,unique_symbols=len(symbols),
        calendar_queries=len(required),ticker_sessions=len(surfaces),raw_typed_occurrences_reconciled=True,
        independent_calendar_counts_reconciled=True,quality_counts=dict(quality),dated_reason_counts=dict(flags),ready_for_build=False,ready_for_training=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);a=p.parse_args()
    result=audit(a.root);f.save(a.root/'INDEPENDENT_AUDIT.json',result);print(json.dumps(result,indent=2))
