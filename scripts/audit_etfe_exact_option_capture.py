"""Independently audit the complete ETFE exact-option capture and its physical union."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nn_meta.etfe import acquisition as a
from nn_meta.etfe.normalization import load_normalization


def merge(intervals):
    out=[]
    for lo,hi in sorted(intervals):
        if lo>=hi:continue
        if out and lo<=out[-1][1]:out[-1][1]=max(out[-1][1],hi)
        else:out.append([lo,hi])
    return [tuple(x) for x in out]


def subtract(base,cut):
    """Half-open interval difference by sweeping both merged lists."""
    out=[];cut=merge(cut)
    for lo,hi in merge(base):
        cur=lo
        for x,y in cut:
            if y<=cur or x>=hi:continue
            if x>cur:out.append((cur,x))
            cur=max(cur,y)
            if cur>=hi:break
        if cur<hi:out.append((cur,hi))
    return merge(out)


def half_open(params):
    return pd.Timestamp(params['start']).value,pd.Timestamp(params['end']).value+1


def union_reconciliation(rawplan):
    parent=rawplan['parent'];demand_root=Path(parent['exact_root']);pilot_root=Path(parent['pilot_root'])
    demand_raw=(demand_root/'DEMAND.json').read_bytes();pilot_raw=(pilot_root/'PLAN.json').read_bytes()
    pilot_audit_raw=(pilot_root/'WINDOW_CHECK_AUDIT.json').read_bytes()
    if (a.sha(demand_raw)!=parent['demand_sha256'] or json.loads(pilot_raw)['sha256']!=parent['pilot_plan_sha256']
            or a.sha(pilot_audit_raw)!=parent['pilot_audit_sha256']):
        raise ValueError('Capture parent binding mismatch')
    demand=json.loads(demand_raw);pilot=json.loads(pilot_raw)
    pending=defaultdict(list);pilot_cover=defaultdict(list);captured=defaultdict(list)
    for item in demand['physical']:
        pending[item['route'],item['symbol']].extend(map(tuple,item['pending_intervals']))
    for j in pilot['jobs']:
        if j['route'] in ('option_bars','option_trades'):
            for s in j['params']['symbols'].split(','):pilot_cover[j['route'],s].append(half_open(j['params']))
    for j in rawplan['jobs']:
        for s in j['params']['symbols'].split(','):captured[j['route'],s].append(half_open(j['params']))
    expected={k:subtract(v,pilot_cover[k]) for k,v in pending.items()}
    expected={k:v for k,v in expected.items() if v}
    observed={k:merge(v) for k,v in captured.items()}
    if expected!=observed:
        missing=sorted(set(expected)-set(observed));extra=sorted(set(observed)-set(expected))
        differ=sorted(k for k in set(expected)&set(observed) if expected[k]!=observed[k])
        raise ValueError(f'Physical union mismatch: missing={missing[:5]} extra={extra[:5]} differ={differ[:5]}')
    ns=lambda d:sum(hi-lo for v in d.values() for lo,hi in v)
    pending_ns=ns({k:merge(v) for k,v in pending.items()})
    return dict(route_symbols=len(observed),pending_symbol_ns=pending_ns,
        captured_symbol_ns=ns(observed),pilot_reused_symbol_ns=pending_ns-ns(observed),
        demand_sha256=parent['demand_sha256'],pilot_plan_sha256=parent['pilot_plan_sha256'])


def audit(root):
    root=Path(root);plan=load_normalization(root)
    if len(plan['inputs'])!=1:raise ValueError('Single capture source expected')
    source=plan['inputs'][0];raw_root=Path(source['root']);rawplan=a.load_plan(raw_root)
    if rawplan['sha256']!=source['sha256']:raise ValueError('Capture plan binding mismatch')
    latest=max((root/'runs').glob('*.json'),key=lambda p:p.stat().st_mtime_ns)
    seal=json.loads(latest.read_text())['partition_receipts']
    expected={a.digest([source['sha256'],j['id']]):j for j in rawplan['jobs']}
    if set(seal)!=set(expected):raise ValueError(f'Normalized census {len(seal)} != capture plan {len(expected)}')
    total=0;routes=Counter();pages=0;quality=Counter()
    for key,digest in sorted(seal.items()):
        meta_path=root/'partitions'/(key+'.json')
        if a.sha(meta_path.read_bytes())!=digest:raise ValueError('Partition receipt hash mismatch')
        meta=json.loads(meta_path.read_text());item=expected[key]
        history,_,complete=a.committed(raw_root,item)
        if not complete or meta['raw_body_hashes']!=[x['body_sha256'] for x,_,_ in history]:
            raise ValueError('Raw page lineage mismatch')
        before=hashlib.sha256();nraw=0
        for _,body,_ in history:
            for symbol,row in a.rows(body,item):
                before.update((symbol+'\t'+json.dumps(row,sort_keys=True,separators=(',',':'))+'\n').encode());nraw+=1
        data=root/meta['data']
        if a.sha(data.read_bytes())!=meta['data_sha256']:raise ValueError('Parquet hash mismatch')
        after=hashlib.sha256();n=0;q=Counter()
        for batch in pq.ParquetFile(data).iter_batches(batch_size=5000,columns=['symbol','raw_json','quality_flags']):
            for row in batch.to_pylist():
                after.update((row['symbol']+'\t'+row['raw_json']+'\n').encode());n+=1;q.update(row['quality_flags'])
        if n!=nraw or n!=meta['rows'] or before.digest()!=after.digest() or dict(q)!=meta['quality_counts']:
            raise ValueError('Occurrence/value/quality mismatch')
        total+=n;routes[item['route']]+=n;pages+=len(history);quality.update(q)
    jobs_by_route=Counter(j['route'] for j in rawplan['jobs'])
    result=dict(schema='etfe-exact-option-capture-independent-audit-v1',
        capture_plan_sha256=rawplan['sha256'],normalization_plan_sha256=plan['sha256'],
        normalization_run=latest.name,terminal_jobs=len(seal),jobs_by_route=dict(jobs_by_route),
        committed_pages=pages,pagination_pages=pages-len(seal),
        normalized_occurrences=total,rows_by_route=dict(routes),quality_counts=dict(quality),
        physical_union=union_reconciliation(rawplan),
        raw_typed_occurrences_and_quality_reconciled=True,capture_equals_pending_union_minus_pilot=True,
        historical_admission=False,realized_holding_paths=False,ready_for_build=False,ready_for_training=False,
        auditor_sha256=a.sha(Path(__file__).read_bytes()))
    a.save(root/'FULL_CAPTURE_INDEPENDENT_AUDIT.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(audit(args.root.resolve()),indent=2))
