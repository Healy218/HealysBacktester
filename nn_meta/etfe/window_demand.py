"""Fresh full-calendar transport inventory and resumable packed signal demand."""
from collections import Counter
from datetime import date
from io import BytesIO
import importlib.metadata
import json
from pathlib import Path
import time
import resource
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from nn_meta.etfe import acquisition as a
from nn_meta.etfe import full_coverage as full
from nn_meta.etfe.causal_pilot import source_files,STOCK,CALENDAR,SETUP,guard
from nn_meta.etfe.causal_inputs import stock_minutes,session_bars
from nn_meta.etfe.expansion import read_calendar
from nn_meta.etfe.signals import signal_batches

CENSUS=a.ROOT/'nn_meta/validation/etfe-full-coverage-20261005-r0'
MINUTE=60_000_000_000


def context_jobs(contracts,calendar):
    """Exact factored regular-session windows; no synthetic contract identities."""
    by_ticker={t:[] for t in a.SYMBOLS}
    for symbol,r in contracts.items():by_ticker[r['underlying_symbol']].append((symbol,date.fromisoformat(r['expiration_date'])))
    for day in calendar:
        d=date.fromisoformat(day['date'])
        start=pd.Timestamp(day['date']+' '+day['open'],tz='America/New_York').value
        end=pd.Timestamp(day['date']+' '+day['close'],tz='America/New_York').value
        for ticker in a.SYMBOLS:
            symbols=sorted(s for s,e in by_ticker[ticker] if 1<=(e-d).days<=45)
            for offset in range(0,len(symbols),100):
                batch=symbols[offset:offset+100]
                value=dict(ticker=ticker,session=day['date'],route='option_bars',symbols=batch,start_ns=start,end_exclusive_ns=end,
                    purpose='daily_context_1_45_DTE',historical_eligibility_admitted=False)
                yield dict(value,window_id=a.digest(value))


def reference_windows(signal_ns,minutes,opening_ns,closing_ns):
    if minutes not in (1,5,15) or not opening_ns<signal_ns<=closing_ns:raise ValueError('Signal clock/timeframe outside session')
    f=(signal_ns-(minutes+1)*MINUTE,signal_ns-MINUTE)
    return dict(feature=f if f[0]>=opening_ns else None,entry=(signal_ns-MINUTE,signal_ns),
                entry_attempt=(signal_ns+10**9,min(signal_ns+60*10**9,closing_ns)))


def holding_frontier(state,now_ns,*,session,cutoff_ns,end_ns):
    """Next observation dependencies only; state must come from a ledger receipt.

    No contract/session fallback or possible hold duration becomes a realized path.
    """
    if not state.get('ledger_receipt_sha256') or len(state['ledger_receipt_sha256'])!=64:raise ValueError('Ledger evidence required')
    if now_ns>=end_ns:return dict(disposition='right_censored_end',requests=[])
    kind=state['kind'];requests=[]
    if kind=='terminal':return dict(disposition='terminal',requests=[])
    if kind=='exercise_pending':return dict(disposition='input_frontier',requests=[dict(route='official_exercise_reference',symbol=state['contract'],at_ns=now_ns)])
    if kind=='settlement_pending':return dict(disposition='await_dated_settlement',requests=[])
    if session is None:return dict(disposition='dated_session_unresolved',requests=[])
    opening,closing=session
    if not opening<=now_ns<closing:return dict(disposition='await_regular_session',requests=[])
    if kind in ('option_held','exit_pending'):
        # Every completed minute whose publication/freshness interval intersects now.
        last_end=(now_ns-10**9)//MINUTE*MINUTE
        if last_end>=opening+MINUTE:
            requests.append(dict(route='option_bars',symbol=state['contract'],start_ns=last_end-MINUTE,end_exclusive_ns=last_end))
        if cutoff_ns is None:return dict(disposition='dated_expiry_cutoff_unresolved',requests=requests)
        if now_ns>=cutoff_ns:requests.append(dict(route='stock_quotes',symbol=state['ticker'],start_ns=now_ns-30*10**9,end_exclusive_ns=now_ns+1))
    elif kind in ('roll_pending','stock_held','stock_exit_pending'):
        requests.append(dict(route='stock_quotes',symbol=state['ticker'],start_ns=max(opening,now_ns-30*10**9),end_exclusive_ns=now_ns+1))
    elif kind=='exercise_pending':requests.append(dict(route='official_exercise_reference',symbol=state['contract'],at_ns=now_ns))
    elif kind=='settlement_pending':return dict(disposition='await_dated_settlement',requests=[])
    else:raise ValueError('Unknown ledger state')
    return dict(disposition='input_frontier',requests=requests)


def prepare(root):
    p=full.load(CENSUS);c=json.loads((CENSUS/'CENSUS.json').read_text())
    if c['summary']['calendar_transport_complete']!=6300:raise ValueError('Full discovery required')
    sources=set(source_files())|{'nn_meta/etfe/window_demand.py','scripts/build_etfe_window_demand.py','docs/specs/ETFE_WINDOW_DEMAND_20261006.md'}
    inputs=[CENSUS/'PLAN.json',CENSUS/'CENSUS.json',CENSUS/'INDEPENDENT_AUDIT.json',CALENDAR/'CALENDAR.json',SETUP/'catalog.json']
    inputs += [STOCK/n for n in ('PLAN.json','NORMALIZED.json','INDEPENDENT_AUDIT.json')]
    plan=dict(schema='etfe-full-window-demand-v1',sources={n:a.sha((a.ROOT/n).read_bytes()) for n in sorted(sources)},
        inputs={str(n):a.sha(n.read_bytes()) for n in inputs},full_census_plan_sha256=p['sha256'],
        packages={n:importlib.metadata.version(n) for n in ('numpy','pandas','pyarrow','vectorbt')},
        limits=dict(max_root_bytes=4*2**30,max_run_seconds=1800,signal_columns=32),
        scopes=[dict(ticker=t,minutes=m) for t in a.SYMBOLS for m in (1,5,15)],ready_for_build=False,ready_for_training=False)
    plan['sha256']=a.digest(plan);root=Path(root);root.mkdir(parents=True,exist_ok=False);a.save(root/'PLAN.json',plan)
    for n in sources:
        dest=root/'source'/n;dest.parent.mkdir(parents=True,exist_ok=True);a.write_new(dest,(a.ROOT/n).read_bytes())
    return plan


def load(root):
    root=Path(root);p=json.loads((root/'PLAN.json').read_text())
    if a.digest({k:v for k,v in p.items() if k!='sha256'})!=p['sha256']:raise ValueError('Plan drift')
    for n,h in p['sources'].items():
        if a.sha((a.ROOT/n).read_bytes())!=h or a.sha((root/'source'/n).read_bytes())!=h:raise ValueError('Source drift; successor required')
    for n,h in p['inputs'].items():
        if a.sha(Path(n).read_bytes())!=h:raise ValueError('Input drift')
    if any(importlib.metadata.version(n)!=v for n,v in p['packages'].items()):raise ValueError('Package drift')
    return p


def table_bytes(frame):
    b=BytesIO();frame.to_parquet(b,index=True,compression='zstd');return b.getvalue()


def context(root):
    root=Path(root);plan=load(root);started=time.monotonic()
    target=root/'CONTEXT.json'
    if target.exists():
        r=json.loads(target.read_text())
        if a.sha((root/r['path']).read_bytes())!=r['sha256']:raise ValueError('Context drift')
        return r
    census=json.loads((CENSUS/'CENSUS.json').read_text());symbols={}
    for key,h in census['page_receipts'].items():
        pointer=CENSUS/'partitions'/(key+'.json')
        if a.sha(pointer.read_bytes())!=h:raise ValueError('Census partition pointer drift')
        meta=json.loads(pointer.read_text());path=CENSUS/meta['data']
        if a.sha(path.read_bytes())!=meta['data_sha256']:raise ValueError('Census partition drift')
        for raw in pq.read_table(path,columns=['raw_json']).column(0).to_pylist():
            r=json.loads(raw);symbols[r['symbol']]=r
    rows=[];edges=0;minutes=0
    for r in context_jobs(symbols,read_calendar(CALENDAR)):
        rows.append(r);edges+=len(r['symbols']);minutes+=len(r['symbols'])*(r['end_exclusive_ns']-r['start_ns'])//MINUTE
        if len(rows)%10000==0:guard(root,plan,started)
    payload=table_bytes(pd.DataFrame(rows));path=root/'CONTEXT.parquet';a.write_new(path,payload)
    result=dict(plan_sha256=plan['sha256'],path=path.name,sha256=a.sha(payload),queries=len(rows),symbol_session_edges=edges,
        requested_symbol_minutes=minutes,elapsed_seconds=time.monotonic()-started,exact_over_returned_symbol_inventory=True,
        historical_listing_complete=False,market_capture_complete=False)
    a.save(target,result);return result


def signals(root,*,max_families=None):
    root=Path(root);p=load(root);started=time.monotonic();processed=0
    calendar=read_calendar(CALENDAR);catalog=json.loads((SETUP/'catalog.json').read_text())['records'];summaries=[]
    for scope in p['scopes']:
        ticker,m=scope['ticker'],scope['minutes'];tag=f'{ticker}-{m}';folder=root/tag;folder.mkdir(exist_ok=True)
        raw=None;chart=None
        for family in sorted({r['strategy'] for r in catalog}):
            receipt=folder/(family+'.json')
            if receipt.exists():
                r=json.loads(receipt.read_text())
                for n,h in r['files'].items():
                    if a.sha((folder/n).read_bytes())!=h:raise ValueError('Signal output drift')
                summaries.append(r);continue
            if max_families is not None and processed>=max_families:return dict(complete=False,processed=processed,checkpoints=len(summaries))
            guard(root,p,started)
            if raw is None:
                raw=stock_minutes(STOCK,ticker);chart=session_bars(raw,calendar,m)
                invalid=np.flatnonzero(~chart.valid.to_numpy());n=int(invalid[0]) if len(invalid) else len(chart)
                # Preserve all clocks in the chart; only the proven uninterrupted prefix is calculable.
                payload=table_bytes(chart);cp=folder/'chart.parquet'
                if cp.exists():
                    if a.sha(cp.read_bytes())!=a.sha(payload):raise ValueError('Chart drift')
                else:a.write_new(cp,payload)
                chart=chart.iloc[:n]
                if not len(chart):raise ValueError('No uninterrupted stock prefix')
            records=[r for r in catalog if r['signal_minutes']==m and r['strategy']==family]
            files={};counts=[];union=np.zeros((len(chart),4),dtype=bool)
            for batch,channels in signal_batches(chart,records,raw,width=p['limits']['signal_columns']):
                guard(root,p,started)
                data=np.stack([f.to_numpy() for f in channels],axis=1)
                union|=data.any(axis=2)
                for i,r in enumerate(batch):counts.append(dict(variant_id=r['variant_id'],events=data[:,:,i].sum(axis=0).tolist()))
                buf=BytesIO();np.savez_compressed(buf,packed=np.packbits(data,axis=0),rows=np.array([len(chart)]),variants=np.array([r['variant_id'] for r in batch]))
                name=family+'-'+str(len(files))+'.npz';payload=buf.getvalue();out=folder/name
                if out.exists():
                    if out.read_bytes()!=payload:raise ValueError('Orphan signal chunk differs')
                else:a.write_new(out,payload)
                files[name]=a.sha(payload)
            buf=BytesIO();np.savez_compressed(buf,packed=np.packbits(union,axis=0),rows=np.array([len(chart)]));payload=buf.getvalue();name=family+'-union.npz'
            out=folder/name
            if out.exists():
                if out.read_bytes()!=payload:raise ValueError('Orphan signal union differs')
            else:a.write_new(out,payload)
            files[name]=a.sha(payload)
            total_rows=pq.ParquetFile(folder/'chart.parquet').metadata.num_rows
            r=dict(plan_sha256=p['sha256'],scope=scope,family=family,variants=len(records),census=counts,files=files,
                calculated_bins=len(chart),unresolved_suffix_bins=total_rows-len(chart),chart_sha256=a.sha((folder/'chart.parquet').read_bytes()),
                price_basis='raw_unadjusted_diagnostics',entry_eligible=False)
            a.save(receipt,r);summaries.append(r);processed+=1
            print(json.dumps(dict(scope=tag,family=family,variants=len(records),calculated_bins=len(chart),unresolved_bins=total_rows-len(chart))),flush=True)
    result=dict(complete=True,plan_sha256=p['sha256'],checkpoints=len(summaries),variants=sum(r['variants'] for r in summaries),
        channel_events=np.sum([x['events'] for r in summaries for x in r['census']],axis=0).tolist(),
        missing_signal_state=any(r['unresolved_suffix_bins'] for r in summaries),elapsed_seconds=time.monotonic()-started,
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,ready_for_build=False,ready_for_training=False)
    if not (root/'SIGNALS.json').exists():a.save(root/'SIGNALS.json',result)
    return result
