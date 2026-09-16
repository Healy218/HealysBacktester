"""Full scoped daily option-surface proxies with bounded day workers and resumption."""
from pathlib import Path
import argparse
import json
import sqlite3
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def sources():
    from nn_meta.v7.storage import sha
    names=['scripts/build_v7_surfaces.py','nn_meta/v7/surfaces.py','nn_meta/v7/daily.py',
           'nn_meta/v7/storage.py','nn_meta/v7/runtime.py','nn_meta/v7/scope.py',
           'nn_options_signal/build_dataset.py','nn_options_signal/config.py',
           'scripts/download_v7_data.py','nn_meta/session_calendar.py']
    return {str(ROOT/name):sha(ROOT/name) for name in names}


def save(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def availability_calendar(source_path, extension):
    from nn_meta.v7.storage import verify
    from nn_meta.session_calendar import SessionCalendar
    verify(extension)
    original=SessionCalendar(json.loads(source_path.read_text()))
    doc=json.loads((extension/'calendar.json').read_text())
    if (doc.get('provider')!='alpaca_calendar'
            or doc['sessions']!=json.loads((extension/'calendar.raw.json').read_text())):
        raise ValueError('Captured Alpaca calendar records required')
    calendar=SessionCalendar(doc)
    if (calendar.start>original.start or calendar.end<=original.end
            or {d:b for d,b in calendar.sessions.items() if original.start<=d<=original.end}!=original.sessions):
        raise ValueError('Availability calendar disagrees with stock capture')
    return calendar


def prepare_spots(stock_root,output):
    import pandas as pd
    from nn_meta.v7.storage import sha,verify,identity,transaction,receipt
    binding=json.loads((stock_root/'summary/binding.json').read_text())
    verify(stock_root/'summary',expected_identity=identity(binding))
    parents={**binding['declaration']['inputs'],**binding['declaration']['sources']}
    if any(sha(p)!=digest for p,digest in parents.items()):
        raise ValueError('Stock daily parent input or code changed')
    report=json.loads((stock_root/'summary/report.json').read_text())
    declaration=dict(stock_summary_sha256=sha(stock_root/'summary/complete.json'),
                     shards=binding['shards'],sources=sources(),schema='v7-surface-spots-v1',
                     expected_rows=report['raw_calendar_rows'])
    payloads={}
    for filename,digest in declaration['shards'].items():
        if sha(filename)!=digest:raise ValueError('Stock daily shard receipt changed')
        shard=verify(Path(filename).parent)
        payloads[str(Path(filename).parent/'daily.parquet')]=shard['files']['daily.parquet']
    if output.exists():
        verify(output,expected_identity=identity(declaration));return
    from scripts.download_v7_data import disk_guard
    disk_guard(stock_root,100)
    with transaction(output) as temp:
        con=sqlite3.connect(temp/'spots.sqlite')
        try:
            con.execute('CREATE TABLE spots (date TEXT, stock_ticker TEXT, raw_close REAL, observed_minutes INTEGER, available_ns INTEGER, PRIMARY KEY(date,stock_ticker)) WITHOUT ROWID')
            count=0
            for filename in declaration['shards']:
                path=Path(filename).parent
                frame=pd.read_parquet(path/'daily.parquet',columns=['source_date','stock_ticker','raw_close','observed_minutes','available_ns'])
                # SQLite encodes missing closes as NULL, never zero or a filled price.
                con.executemany('INSERT INTO spots VALUES (?,?,?,?,?)',frame.itertuples(index=False,name=None))
                count+=len(frame)
            con.commit()
        finally:con.close()
        if count!=declaration['expected_rows']:raise ValueError('Incomplete stock daily index')
        for filename,digest in {**declaration['shards'],**payloads,**parents}.items():
            if sha(filename)!=digest:raise ValueError('Stock source changed during daily indexing')
        if sources()!=declaration['sources']:raise ValueError('Surface source changed')
        save(temp/'declaration.json',declaration);save(temp/'report.json',dict(rows=count,research_ready=False))
        receipt(temp,dict(identity=identity(declaration),research_ready=False))


def work(task):
    day,stock_index,source,audit,output,opening_ns,expected=task
    import pandas as pd
    from dataclasses import asdict
    from nn_meta.v7.storage import sha,verify,identity,transaction,receipt
    from nn_meta.v7.surfaces import surface_panel
    from nn_meta.v7.daily import SurfacePolicy
    from scripts.download_v7_data import completed,disk_guard
    path=audit/'options'/day
    doc=verify(path)
    source_receipt=source/f'options/day_aggs/{day}/complete.json'
    raw=json.loads(source_receipt.read_text())
    if (doc.get('kind')!='options' or doc.get('key')!=day
            or raw['task']!={'key':f'options/day_aggs/{day}','kind':'day_aggs',
                             'object':f'us_options_opra/day_aggs_v1/{day[:4]}/{day[5:7]}/{day}.csv.gz'}
            or json.loads((path/'summary.json').read_text())['input_receipt_sha256']!=sha(source_receipt)
            or completed(source,raw['task'])!=raw):
        raise ValueError('Whole-market option audit lineage differs')
    inputs={str(p):sha(p) for p in [stock_index/'complete.json',source_receipt,path/'complete.json']}
    inputs.update({str(source_receipt.parent/p):digest for p,digest in raw['files'].items()})
    inputs.update({str(path/p):digest for p,digest in doc['files'].items()})
    code=sources()
    if code!=expected:raise ValueError('Surface code changed during full build')
    declaration=dict(schema='v7-daily-surface-proxies-v1',day=day,inputs=inputs,sources=code,
        policy=asdict(SurfacePolicy()),available_ns=opening_ns,
        stock_identity='literal raw source ticker; identity assigned only by dated eligible join',research_ready=False)
    target=output/day
    if target.exists():verify(target,expected_identity=identity(declaration));return
    disk_guard(output,100)
    con=sqlite3.connect(f'file:{stock_index}/spots.sqlite?mode=ro',uri=True)
    try:stocks=pd.read_sql_query('SELECT stock_ticker,raw_close,observed_minutes,available_ns FROM spots WHERE date=? ORDER BY stock_ticker',con,params=(day,))
    finally:con.close()
    options=pd.read_parquet(path/'contracts.parquet',columns=['ticker','close','volume'])
    surfaces=surface_panel(day,stocks,options)
    surfaces=surfaces.rename(columns={'available_ns':'stock_available_ns'})
    surfaces['available_ns']=opening_ns
    if not surfaces.stock_available_ns.lt(opening_ns).all():raise ValueError('Daily proxy not available strictly after its stock session')
    with transaction(target) as temp:
        surfaces.to_parquet(temp/'surfaces.parquet',index=False)
        if (any(sha(p)!=digest for p,digest in {**inputs,**code}.items())
                or sources()!=expected):raise ValueError('Surface input changed')
        save(temp/'declaration.json',declaration)
        save(temp/'report.json',dict(rows=len(surfaces),status_counts={str(k):int(v) for k,v in surfaces.surface_status.value_counts().items()},research_ready=False))
        receipt(temp,dict(identity=identity(declaration),research_ready=False))


def main():
    from nn_meta.v7.runtime import configure_threads,worker_pool
    configure_threads(1)
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    from nn_meta.v7.scope import require_active_inputs,HISTORY_START,HISTORY_END
    from nn_meta.v7.storage import sha,verify,identity,transaction,receipt
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ['stock-daily','source','audit','output','availability-calendar']:ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--workers',type=int,required=True)
    args=ap.parse_args()
    if not args.output.resolve().is_relative_to(ROOT/'nn_meta') or not 1<=args.workers<=4:
        raise ValueError('Repository artifact disk and 1–4 workers required')
    require_active_inputs(args.source)
    active_path=ROOT/'docs/specs/V7_ACTIVE_INPUTS_20220315.json'
    active=json.loads(active_path.read_text())
    parent=json.loads((args.stock_daily/'summary/binding.json').read_text())
    if (args.source.resolve()!=(ROOT/active['working_inputs']).resolve()
            or parent['declaration']['inputs'].get(str(active_path))!=sha(active_path)):
        raise ValueError('Surface sources differ from active stock scope')
    calendar_path=args.source/'calendar.json'
    calendar=availability_calendar(calendar_path,args.availability_calendar)
    calendar_receipt=verify(args.availability_calendar)
    calendar_inputs={str(args.availability_calendar/'complete.json'):sha(args.availability_calendar/'complete.json')}
    calendar_inputs.update({str(args.availability_calendar/p):digest for p,digest in calendar_receipt['files'].items()})
    args.output.mkdir(parents=True,exist_ok=True)
    stock_index=args.output/'stock-index'
    prepare_spots(args.stock_daily,stock_index)
    index_receipt=sha(stock_index/'complete.json')
    days=sorted(d for d in calendar.sessions if HISTORY_START<=d<=HISTORY_END)
    con=sqlite3.connect(f'file:{stock_index}/spots.sqlite?mode=ro',uri=True)
    try:stock_days=[r[0] for r in con.execute('SELECT DISTINCT date FROM spots ORDER BY date')]
    finally:con.close()
    if stock_days!=days:raise ValueError('Raw daily stock dates differ from full scope')
    code=sources();inputs={str(p):sha(p) for p in [calendar_path,args.stock_daily/'summary/complete.json',stock_index/'complete.json']}
    inputs.update(calendar_inputs)
    tasks=[]
    for day in days:
        following=next((d for d in sorted(calendar.sessions) if d>day),None)
        if following is None:raise ValueError('Calendar lacks next-session availability')
        opening=int(calendar.bounds(following)[0].tz_localize('UTC').value)
        tasks.append((day,stock_index,args.source,args.audit,args.output/'days',opening,code))
    (args.output/'days').mkdir(exist_ok=True)
    with worker_pool(args.workers,threads=1) as pool:
        for start in range(0,len(tasks),args.workers):
            list(pool.map(work,tasks[start:start+args.workers]))
            done=min(start+args.workers,len(tasks))
            if done%40==0 or done==len(tasks):print(json.dumps(dict(completed_days=done,total_days=len(tasks))),flush=True)
    if sha(stock_index/'complete.json')!=index_receipt:raise ValueError('Stock index receipt changed')
    verify(stock_index)
    shard_inputs={str(args.output/'days'/day/'complete.json'):sha(args.output/'days'/day/'complete.json') for day in days}
    binding=dict(inputs=inputs,sources=code,days=shard_inputs)
    summary=args.output/'summary'
    if summary.exists():verify(summary,expected_identity=identity(binding));print((summary/'report.json').read_text());return
    eligible=pd.read_parquet(args.stock_daily/'summary/eligible_daily.parquet',columns=['date','membership_ticker','stock_ticker','security_id','status'])
    if eligible.duplicated(['date','security_id']).any():raise ValueError('Duplicate eligible identities')
    groups=dict(tuple(eligible.groupby('date')))
    total=0;status={};missing_near=missing_far=missing_ratio=0
    with transaction(summary) as temp:
        writer=None
        try:
            for day in days:
                root=args.output/'days'/day;verify(root)
                surface=pd.read_parquet(root/'surfaces.parquet')
                rows=groups[day].merge(surface,on='stock_ticker',how='left',validate='many_to_one',indicator=True)
                if not rows._merge.eq('both').all():raise ValueError('Eligible security missing from surface history')
                rows=rows.drop(columns='_merge')
                rows['surface_receipt_sha256']=shard_inputs[str(root/'complete.json')]
                table=pa.Table.from_pandas(rows,preserve_index=False)
                if writer is None:writer=pq.ParquetWriter(temp/'eligible_surfaces.parquet',table.schema,compression='zstd')
                writer.write_table(table);total+=len(rows)
                for key,count in rows.surface_status.value_counts().items():status[str(key)]=status.get(str(key),0)+int(count)
                missing_near+=int(rows.atm_iv_near.isna().sum());missing_far+=int(rows.atm_iv_far.isna().sum());missing_ratio+=int(rows.pc_ratio.isna().sum())
        finally:
            if writer is not None:writer.close()
        if total!=len(eligible) or any(sha(p)!=digest for p,digest in {**inputs,**code,**shard_inputs}.items()):
            raise ValueError('Surface output count or source binding changed')
        report=dict(days=len(days),eligible_rows=total,security_ids=int(eligible.security_id.nunique()),
            status_counts=status,missing_near_iv=missing_near,missing_far_iv=missing_far,missing_pc_ratio=missing_ratio,
            research_ready=False,limitations=['European fixed-rate/dividend-yield proxy, not observed IV or executable prices',
                'Literal option roots; not dated standard-deliverable or alias execution proof',
                'No forward-fill, causal return adjustment, or full daily-feature integration yet'])
        save(temp/'binding.json',binding);save(temp/'report.json',report)
        from scripts.download_v7_data import disk_guard
        disk_guard(args.output,100)
        receipt(temp,dict(identity=identity(binding),research_ready=False))
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
