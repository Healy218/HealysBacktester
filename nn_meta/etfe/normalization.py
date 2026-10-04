"""Typed, lossless-occurrence ETFE normalization with stock-session gap reports."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import fcntl
import json
import math
import os
from pathlib import Path
import re
import resource
import shutil
import time
import uuid

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from nn_meta.etfe.acquisition import ROOT, committed, digest, load_plan, resources, rows, save, sha, write_new
from nn_meta.etfe.expansion import read_calendar
from nn_meta.etfe.purchase_policy_v2 import SCOPE, load_scope

MINUTE = 60_000_000_000
SOURCES = ('nn_meta/etfe/normalization.py','scripts/normalize_etfe.py',
    'nn_meta/etfe/acquisition.py','nn_meta/etfe/expansion.py',
    'docs/specs/ETFE_SCOPE_0DTE_20261004.json','docs/specs/ETFE_0DTE_NORMALIZATION_20261004.md')
COMMON = [('occurrence_id',pa.string()),('symbol',pa.string()),('underlying',pa.string()),
    ('timestamp_ns',pa.int64()),('timestamp_raw',pa.string()),('session_date',pa.date32()),
    ('stock_session',pa.string()),('calendar_dte',pa.int16()),('expiration_date',pa.date32()),
    ('right',pa.string()),('strike',pa.float64()),('capture_plan_sha256',pa.string()),
    ('job_id',pa.string()),('page',pa.int32()),('ordinal',pa.int32()),('body_sha256',pa.string()),
    ('received_at_ns',pa.int64()),('quality_flags',pa.list_(pa.string())),('raw_json',pa.string())]
BAR_SCHEMA=pa.schema(COMMON+[('open',pa.float64()),('high',pa.float64()),('low',pa.float64()),
    ('close',pa.float64()),('volume',pa.int64()),('trade_count',pa.int64()),('vwap',pa.float64())])
TRADE_SCHEMA=pa.schema(COMMON+[('price',pa.float64()),('size',pa.int64()),('condition',pa.string()),
    ('exchange',pa.string()),('native_trade_id',pa.string())])
CONTRACT_SCHEMA=pa.schema(COMMON+[('record_use',pa.string()),('status',pa.string()),
    ('multiplier_raw',pa.string()),('size_raw',pa.string()),('deliverables_json',pa.string())])


def schema_for(route):
    return CONTRACT_SCHEMA if route=='contracts' else TRADE_SCHEMA if route=='option_trades' else BAR_SCHEMA


def session_map(calendar):
    return {r['date']:(pd.Timestamp(r['date']+' '+r['open'],tz='America/New_York').value,
                      pd.Timestamp(r['date']+' '+r['close'],tz='America/New_York').value) for r in calendar}


def number(value, name, flags, *, integer=False, positive=True):
    try:
        if isinstance(value,bool):raise ValueError()
        d=Decimal(str(value))
        if not d.is_finite() or (d<=0 if positive else d<0):raise ValueError()
        if integer:
            if d != d.to_integral_value() or d>2**63-1:raise ValueError()
            return int(d)
        result=float(d)
        if not math.isfinite(result):raise ValueError()
        return result
    except (InvalidOperation,ValueError,TypeError,OverflowError):
        flags.append('invalid_'+name)
        return None


def typed_row(symbol, raw, *, route, plan_sha, job_id, page, ordinal, receipt, sessions):
    flags=[]
    stamp=pd.Timestamp(raw['t']) if 't' in raw else None
    local=stamp.tz_convert('America/New_York') if stamp is not None else None
    day=str(local.date()) if local is not None else None
    classification='discovery_only'
    if day is not None:
        bounds=sessions.get(day)
        classification=('stock_regular' if bounds[0]<=stamp.value<bounds[1] else 'outside_stock_regular') if bounds else 'no_stock_session'
    match=re.fullmatch(r'(SPY|QQQ|VOO)(\d{6})([CP])(\d{8})',symbol)
    expiry=right=strike=None
    underlying=symbol
    if match:
        underlying=match[1]
        try:expiry=datetime.strptime(match[2],'%y%m%d').date()
        except ValueError:flags.append('invalid_expiration_identity')
        right={'C':'call','P':'put'}[match[3]];strike=int(match[4])/1000
    elif route!='stock_bars':
        flags.append('unparsed_option_identity')
    dte=(expiry-local.date()).days if expiry and local is not None else None
    if dte is not None and dte<0:flags.append('observation_after_expiry_date')
    result=dict(occurrence_id=digest([plan_sha,job_id,page,ordinal,receipt['body_sha256']]),symbol=symbol,
        underlying=underlying,timestamp_ns=stamp.value if stamp is not None else None,
        timestamp_raw=raw.get('t'),session_date=local.date() if local is not None else None,
        stock_session=classification,calendar_dte=dte,expiration_date=expiry,right=right,strike=strike,
        capture_plan_sha256=plan_sha,job_id=job_id,page=page,ordinal=ordinal,
        body_sha256=receipt['body_sha256'],received_at_ns=pd.Timestamp(receipt['received_at']).value,
        quality_flags=flags,raw_json=json.dumps(raw,sort_keys=True,separators=(',',':')))
    if route=='contracts':
        if str(expiry)!=raw.get('expiration_date') or right!=raw.get('type'):
            flags.append('contract_identity_mismatch')
        result.update(record_use='discovery_only_not_historical_feature',status=raw.get('status'),
            multiplier_raw=str(raw['multiplier']) if raw.get('multiplier') is not None else None,
            size_raw=str(raw['size']) if raw.get('size') is not None else None,
            deliverables_json=json.dumps(raw.get('deliverables'),sort_keys=True,separators=(',',':')))
    elif route=='option_trades':
        result.update(price=number(raw['p'],'price',flags),size=number(raw['s'],'size',flags,integer=True),
            condition=str(raw['c']),exchange=str(raw['x']),native_trade_id=str(raw['i']) if raw.get('i') is not None else None)
        if not isinstance(raw['c'],str) or len(raw['c'])!=1 or raw['c'] not in 'ABCDEFGHIJSabcdefghijklmnopqrstuv':
            flags.append('unmapped_trade_condition')
    else:
        result.update({name:number(raw[key],name,flags) for name,key in
            [('open','o'),('high','h'),('low','l'),('close','c'),('vwap','vw')]})
        result.update(volume=number(raw['v'],'volume',flags,integer=True),
                      trade_count=number(raw['n'],'trade_count',flags,integer=True))
        if all(result[k] is not None for k in ('open','high','low','close')):
            if not result['low']<=min(result['open'],result['close'])<=max(result['open'],result['close'])<=result['high']:
                flags.append('inconsistent_ohlc')
        if stamp.value % MINUTE:flags.append('unaligned_minute_bar')
    return result


def minute_ranges(values):
    ranges=[]
    for stamp in sorted(values):
        if ranges and ranges[-1][1]+MINUTE==stamp:ranges[-1][1]=stamp
        else:ranges.append([stamp,stamp])
    return ranges


def stock_gaps(item, sessions, observed, valid):
    if item['route']!='stock_bars':return []
    start,end=pd.Timestamp(item['params']['start']).value,pd.Timestamp(item['params']['end']).value
    report=[]
    for day,(opened,closed) in sorted(sessions.items()):
        expected={t for t in range(opened,closed,MINUTE) if start<=t<=end}
        if not expected:continue
        present=observed.get(day,set()) & expected
        good=valid.get(day,set()) & expected
        missing=expected-present
        report.append(dict(date=day,expected_minutes=len(expected),observed_minutes=len(present),
            valid_price_minutes=len(good),missing_minutes=len(missing),
            invalid_observed_minutes=len(present-good),missing_ranges_ns=minute_ranges(missing),
            missing_classification='unresolved_provider_gap_or_no_trade' if missing else 'none'))
    return report


def prepare_normalization(root, inputs, calendar_root):
    root=Path(root);inputs=[Path(p).resolve() for p in inputs];calendar_root=Path(calendar_root).resolve()
    if len(inputs)!=len(set(inputs)):raise ValueError('Duplicate capture roots')
    read_calendar(calendar_root)
    plans=[load_plan(p) for p in inputs]
    plan=dict(schema='etfe-normalization-plan-v1',scope=load_scope(),scope_sha256=sha(SCOPE.read_bytes()),
        inputs=[dict(root=str(r),sha256=p['sha256']) for r,p in zip(inputs,plans)],
        calendar_root=str(calendar_root),calendar_sha256=sha((calendar_root/'CALENDAR.json').read_bytes()),
        sources={n:sha((ROOT/n).read_bytes()) for n in SOURCES},
        versions=dict(pyarrow=pa.__version__,pandas=pd.__version__),
        limits=dict(batch_rows=5000,max_root_bytes=2*2**30,max_elapsed_seconds=7200),
        ready_for_build=False,ready_for_training=False)
    plan['sha256']=digest(plan)
    root.mkdir(parents=True,exist_ok=False);save(root/'PLAN.json',plan)
    for name in SOURCES:
        target=root/'source'/name;target.parent.mkdir(parents=True,exist_ok=True)
        write_new(target,(ROOT/name).read_bytes())
    return plan


def load_normalization(root):
    root=Path(root);plan=json.loads((root/'PLAN.json').read_text())
    if digest({k:v for k,v in plan.items() if k!='sha256'})!=plan['sha256']:
        raise ValueError('Normalization plan changed')
    for name,h in plan['sources'].items():
        if sha((ROOT/name).read_bytes())!=h or sha((root/'source'/name).read_bytes())!=h:
            raise ValueError('Normalization code changed; use a successor')
    if sha((Path(plan['calendar_root'])/'CALENDAR.json').read_bytes())!=plan['calendar_sha256']:
        raise ValueError('Calendar binding changed')
    read_calendar(plan['calendar_root'])
    for source in plan['inputs']:
        if load_plan(source['root'])['sha256']!=source['sha256']:
            raise ValueError('Capture input changed')
    return plan


def storage_guard(root, plan):
    r=resources(root)
    if r['disk_free']<max(100*2**30,.2*r['disk_total'])+256*2**20:
        raise RuntimeError('disk_reserve')
    if r['ram_available']<max(2*2**30,.2*r['ram_total'])+2**30:
        raise RuntimeError('memory_reserve')
    if sum(p.stat().st_size for p in Path(root).rglob('*') if p.is_file())+256*2**20>plan['limits']['max_root_bytes']:
        raise RuntimeError('normalization_storage_budget')


def partition_receipt(root, key):
    path=Path(root)/'partitions'/(key+'.json')
    if not path.exists():return None
    r=json.loads(path.read_text());data=(Path(root)/r['data']).resolve()
    if not data.is_relative_to(Path(root).resolve()) or sha(data.read_bytes())!=r['data_sha256']:
        raise ValueError('Normalized partition checksum mismatch')
    parquet=pq.ParquetFile(data)
    if parquet.metadata.num_rows!=r['rows'] or parquet.schema_arrow!=schema_for(r['route']):
        raise ValueError('Normalized partition census/schema mismatch')
    return r


def normalize_partition(root, source, item, plan, sessions):
    history,_,complete=committed(source['root'],item)
    if not complete:raise RuntimeError('input_partition_incomplete')
    root=Path(root);key=digest([source['sha256'],item['id']])
    attempts=root/'attempts';attempts.mkdir(exist_ok=True)
    data=attempts/(uuid.uuid4().hex+'.parquet')
    schema=schema_for(item['route']);batch=[];count=0;quality=Counter();classes=Counter()
    observed,valid=defaultdict(set),defaultdict(set)
    bar_seen,trade_seen={},set();identical_trades=0;minimum=maximum=None
    writer=pq.ParquetWriter(data,schema,compression='zstd')
    try:
        for page,(receipt,body,_) in enumerate(history):
            for ordinal,(symbol,raw) in enumerate(rows(body,item)):
                row=typed_row(symbol,raw,route=item['route'],plan_sha=source['sha256'],
                    job_id=item['id'],page=page,ordinal=ordinal,receipt=receipt,sessions=sessions)
                if row['timestamp_ns'] is not None:
                    t=row['timestamp_ns'];minimum=t if minimum is None else min(minimum,t);maximum=t if maximum is None else max(maximum,t)
                content=sha(row['raw_json'].encode())
                if item['route'].endswith('bars'):
                    identity=(symbol,row['timestamp_ns'])
                    if identity in bar_seen:
                        row['quality_flags'].append('duplicate_bar_identical' if bar_seen[identity]==content else 'duplicate_bar_conflicting')
                    else:bar_seen[identity]=content
                elif item['route']=='option_trades':
                    identity=(symbol,content)
                    identical_trades+=int(identity in trade_seen);trade_seen.add(identity)
                classes[row['stock_session']]+=1;quality.update(row['quality_flags'])
                if item['route']=='stock_bars' and row['stock_session']=='stock_regular':
                    day=str(row['session_date']);observed[day].add(row['timestamp_ns'])
                    if 'duplicate_bar_conflicting' in row['quality_flags']:
                        valid[day].discard(row['timestamp_ns'])
                    if not row['quality_flags']:valid[day].add(row['timestamp_ns'])
                batch.append(row);count+=1
                if len(batch)>=plan['limits']['batch_rows']:
                    storage_guard(root,plan)
                    writer.write_table(pa.Table.from_pylist(batch,schema=schema));batch=[]
        if batch:writer.write_table(pa.Table.from_pylist(batch,schema=schema))
    finally:writer.close()
    with data.open('rb') as f:os.fsync(f.fileno())
    result=dict(key=key,normalization_plan_sha256=plan['sha256'],input_plan_sha256=source['sha256'],
        input_root=source['root'],job_id=item['id'],route=item['route'],purpose=item['purpose'],
        data=str(data.relative_to(root)),data_sha256=sha(data.read_bytes()),rows=count,pages=len(history),
        schema=str(schema),quality_counts=dict(quality),session_counts=dict(classes),
        identical_trade_content_occurrences_retained=identical_trades,min_timestamp_ns=minimum,max_timestamp_ns=maximum,
        stock_session_coverage=stock_gaps(item,sessions,observed,valid),
        raw_body_hashes=[r['body_sha256'] for r,_,_ in history],ready_for_build=False)
    output=root/'partitions';output.mkdir(exist_ok=True);save(output/(key+'.json'),result)
    return result


def normalize(root, *, max_partitions=None):
    root=Path(root);plan=load_normalization(root);sessions=session_map(read_calendar(plan['calendar_root']))
    started=time.monotonic();processed=0;results=[];stop=None
    with (root/'writer.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for source in plan['inputs']:
            for item in load_plan(source['root'])['jobs']:
                key=digest([source['sha256'],item['id']]);r=partition_receipt(root,key)
                if r:
                    history,_,complete=committed(source['root'],item)
                    if (not complete or r['normalization_plan_sha256']!=plan['sha256']
                            or r['raw_body_hashes']!=[x['body_sha256'] for x,_,_ in history]):
                        raise ValueError('Normalized partition lineage changed')
                    results.append(r);continue
                if max_partitions is not None and processed>=max_partitions:
                    stop='partition_budget';break
                if time.monotonic()-started>plan['limits']['max_elapsed_seconds']:
                    stop='elapsed_budget';break
                storage_guard(root,plan)
                try:r=normalize_partition(root,source,item,plan,sessions)
                except RuntimeError as exc:stop=str(exc);break
                results.append(r);processed+=1
            if stop:break
        report=dict(schema='etfe-normalized-inputs-v1',plan_sha256=plan['sha256'],
            normalized_complete=stop is None,stop_reason=stop,partitions=len(results),
            rows=sum(r['rows'] for r in results),processed_this_run=processed,
            elapsed_seconds=time.monotonic()-started,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            partition_receipts={r['key']:sha((root/'partitions'/(r['key']+'.json')).read_bytes()) for r in results},
            ready_for_build=False,ready_for_training=False)
        runs=root/'runs';runs.mkdir(exist_ok=True);save(runs/(uuid.uuid4().hex+'.json'),report)
        if report['normalized_complete']:
            if not (root/'NORMALIZED.json').exists():save(root/'NORMALIZED.json',report)
            else:
                seal=json.loads((root/'NORMALIZED.json').read_text())
                if seal['partition_receipts']!=report['partition_receipts']:raise ValueError('Normalization seal changed')
    return report
