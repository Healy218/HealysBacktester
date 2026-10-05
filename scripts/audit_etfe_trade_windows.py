"""Reconcile demanded trade edges, raw occurrences and observed minute coverage."""
from collections import Counter,defaultdict
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import pandas as pd
import pyarrow.parquet as pq
from nn_meta.etfe.acquisition import committed,rows,save,sha
from nn_meta.etfe.trade_demand import verify
from nn_meta.etfe.causal_inputs import normalized_partitions
from nn_meta.etfe.causal_pilot import OPTIONS

MINUTE=60_000_000_000


def audit(raw_root,normalized_root):
    raw_root=Path(raw_root).resolve();normalized_root=Path(normalized_root).resolve();plan=verify(raw_root)
    demand_root=Path(plan['parent']['pilot'])
    demand=json.loads((demand_root/'GLOBAL_DEMAND.json').read_text())
    expected={(x['symbol'],a,b) for x in demand['physical'] if x['route']=='option_trades' for a,b in x['uncaptured_intervals']}
    jobs={x['id']:x for x in plan['jobs']};request_edges=set();raw_counts=Counter();intervals=[]
    for item in plan['jobs']:
        params=item['params'];a=pd.Timestamp(params['start']).value;b=pd.Timestamp(params['end']).value+1
        symbols=params['symbols'].split(',');pages,token,done=committed(raw_root,item)
        if not done:raise ValueError('Incomplete trade query')
        counts=Counter()
        for receipt,body,attempt in pages:
            for symbol,row in rows(body,item):
                if symbol not in symbols or not a<=pd.Timestamp(row['t']).value<b:raise ValueError('Raw observation outside exact demand')
                counts[symbol]+=1
        for s in symbols:
            if (s,a,b) in request_edges:raise ValueError('Repeated capture edge')
            request_edges.add((s,a,b));raw_counts[(item['id'],s)]=counts[s]
            intervals.append(dict(symbol=s,start_ns=a,end_exclusive_ns=b,job_id=item['id'],observed_occurrences=counts[s],
                                  absence='unresolved_provider_gap_or_no_trade' if counts[s]==0 else None))
    if expected!=request_edges or len(expected)!=225:raise ValueError('Logical/transport demand mismatch')
    by_minute=defaultdict(list);normalized_counts=Counter();occurrences=set();quality=Counter();conditions=Counter();native_ids=Counter()
    input_receipts=[]
    for meta,path in normalized_partitions(normalized_root,'option_trades'):
        if meta['input_plan_sha256']!=plan['sha256'] or meta['job_id'] not in jobs:raise ValueError('Unrelated normalized input')
        input_receipts.append(dict(path=str(path.relative_to(ROOT)),sha256=sha(path.read_bytes())))
        for batch in pq.ParquetFile(path).iter_batches(batch_size=5000):
            for r in batch.to_pylist():
                identity=r['occurrence_id']
                if identity in occurrences:raise ValueError('Repeated normalized occurrence identity')
                occurrences.add(identity);normalized_counts[(r['job_id'],r['symbol'])]+=1
                quality.update(r['quality_flags']);conditions[r['condition']]+=1
                if r['native_trade_id'] is not None:native_ids[(r['symbol'],r['native_trade_id'])]+=1
                by_minute[(r['symbol'],r['timestamp_ns']//MINUTE*MINUTE)].append(r)
    if any(normalized_counts[key]!=count for key,count in raw_counts.items()) or set(normalized_counts)-set(raw_counts):
        raise ValueError('Normalized edge count mismatch')
    wanted={(s,t) for s,a,b in expected for t in range(a,b,MINUTE)}
    if set(by_minute)-wanted:raise ValueError('Normalized minute outside demand')
    bars=defaultdict(list);bar_inputs=[]
    for root in OPTIONS:
        for meta,path in normalized_partitions(root,'option_bars'):
            relevant=False
            for batch in pq.ParquetFile(path).iter_batches(batch_size=5000,columns=['symbol','timestamp_ns','vwap','volume','trade_count','quality_flags','occurrence_id']):
                for r in batch.to_pylist():
                    key=(r['symbol'],r['timestamp_ns'])
                    if key in wanted:bars[key].append(r);relevant=True
            if relevant:bar_inputs.append(dict(path=str(path.relative_to(ROOT)),sha256=sha(path.read_bytes())))
    records=[];seen=set()
    for edge in intervals:
        for t in range(edge['start_ns'],edge['end_exclusive_ns'],MINUTE):
            key=(edge['symbol'],t)
            if key in seen:raise ValueError('Overlapping requested contract minute')
            seen.add(key);trades=by_minute[key];bar_rows=bars[key]
            valid_bar=bar_rows[0] if len(bar_rows)==1 and not bar_rows[0]['quality_flags'] else None
            missing_sizes=any(x['size'] is None for x in trades)
            records.append(dict(symbol=key[0],minute_open_ns=t,job_id=edge['job_id'],
                observed_trade_occurrences=len(trades),observed_size_sum=None if missing_sizes else sum(x['size'] for x in trades),
                observed_condition_counts=json.dumps(dict(Counter(x['condition'] for x in trades)),sort_keys=True),
                quality_flagged_occurrences=sum(bool(x['quality_flags']) for x in trades),
                missing_native_id_occurrences=sum(x['native_trade_id'] is None for x in trades),
                equal_timestamp_extra_occurrences=len(trades)-len({x['timestamp_ns'] for x in trades}),
                bar_occurrences=len(bar_rows),vendor_bar_vwap=valid_bar['vwap'] if valid_bar else None,
                vendor_bar_volume=valid_bar['volume'] if valid_bar else None,
                vendor_bar_trade_count=valid_bar['trade_count'] if valid_bar else None,
                bar_occurrence_ids=json.dumps([x['occurrence_id'] for x in bar_rows]),
                observation_state='observed_trades' if trades else 'unresolved_provider_gap_or_no_trade',
                transport_complete=True,valid_no_trade_admitted=False,model_feature_admitted=False))
    frame=pd.DataFrame(records).sort_values(['symbol','minute_open_ns'])
    if len(frame)!=4626 or seen!=wanted:raise ValueError('Minute grid census mismatch')
    output=normalized_root/'DEMANDED_MINUTES.parquet'
    if output.exists():raise ValueError('Refusing minute census overwrite')
    frame.to_parquet(output,index=False)
    pilot_membership=[]
    for member in demand['membership']:
        f=member['logical_events'];path=demand_root/f['path']
        if sha(path.read_bytes())!=f['sha256']:raise ValueError('Original logical membership drift')
        pilot_membership.append(dict(path=str(path.relative_to(ROOT)),sha256=f['sha256'],rows=f['rows']))
    counts=dict(trades_and_bar=int((frame.observed_trade_occurrences.gt(0)&frame.bar_occurrences.gt(0)).sum()),
        trades_without_bar=int((frame.observed_trade_occurrences.gt(0)&frame.bar_occurrences.eq(0)).sum()),
        bar_without_trades=int((frame.observed_trade_occurrences.eq(0)&frame.bar_occurrences.gt(0)).sum()),
        neither_observed=int((frame.observed_trade_occurrences.eq(0)&frame.bar_occurrences.eq(0)).sum()))
    result=dict(schema='etfe-trade-window-audit-v1',raw_root=str(raw_root.relative_to(ROOT)),
        normalized_root=str(normalized_root.relative_to(ROOT)),capture_plan_sha256=plan['sha256'],
        demand_sha256=plan['parent']['bindings']['GLOBAL_DEMAND.json'],auditor_sha256=sha(Path(__file__).read_bytes()),
        normalization_audit_sha256=sha((normalized_root/'INDEPENDENT_AUDIT.json').read_bytes()),
        edges=len(expected),queries=len(jobs),symbols=len({s for s,a,b in expected}),
        raw_occurrences=sum(raw_counts.values()),normalized_occurrences=len(occurrences),
        empty_edges=sum(x['observed_occurrences']==0 for x in intervals),intervals=intervals,
        demanded_minutes=len(frame),observed_minute_states=counts,quality_counts=dict(quality),condition_counts=dict(conditions),
        missing_native_ids=int(frame.missing_native_id_occurrences.sum()),repeated_native_id_excess=sum(n-1 for n in native_ids.values()),
        equal_timestamp_extra_occurrences=int(frame.equal_timestamp_extra_occurrences.sum()),
        ambiguous_bar_minutes=int(frame.bar_occurrences.gt(1).sum()),minute_census=dict(path=str(output.relative_to(ROOT)),
        sha256=sha(output.read_bytes()),rows=len(frame)),normalized_inputs=input_receipts,bar_inputs=bar_inputs,
        original_logical_membership=pilot_membership,all_edges_captured=True,all_rows_within_half_open_demand=True,
        missing_trade_transport_intervals=0,valid_no_trade_admitted=False,ready_for_build=False,ready_for_training=False)
    save(normalized_root/'DEMAND_AUDIT.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--raw',required=True,type=Path);p.add_argument('--normalized',required=True,type=Path)
    a=p.parse_args();r=audit(a.raw,a.normalized)
    print(json.dumps({k:v for k,v in r.items() if k not in ('intervals','normalized_inputs','bar_inputs','original_logical_membership')},indent=2))
