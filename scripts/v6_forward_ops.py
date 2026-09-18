"""Refresh, relay and monitor the frozen V6 paper runtime without broker orders."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

from nn_meta.live.v6_market import read, save, utcnow
from nn_meta.live.v6_release import sha

ROOT=Path(__file__).resolve().parents[1]


def publish_data(root, release, anchor, pointer):
    from nn_meta.live.v6_forward_inputs import ForwardData
    digest=sha(root/'manifest.json')
    data=ForwardData(root,expected_sha256=digest,release=release,anchor=anchor)
    document={'schema':'v6-forward-data-index-v1','path':str(root.absolute()),'sha256':digest,
        'release_sha256':anchor,'through':data.document['through'],'published_at':utcnow().isoformat()}
    save(pointer,document)
    return document


def refresh(args):
    from scripts.run_v6_forward import configure
    from nn_meta.session_calendar import SessionCalendar
    configure(args.release,args.anchor)
    calendar=SessionCalendar(read(args.source/'exchange_calendar.json'))
    now=utcnow()
    through=max(day for day in calendar.sessions if calendar.bounds(day)[1].tz_localize('UTC')<now)
    current=read(args.state/'data-index.json') if (args.state/'data-index.json').exists() else None
    if current and current['through']==through:
        # Verify bytes even on a no-op; a stale/broken pointer never gets a pass.
        return publish_data(Path(current['path']),args.release,args.anchor,args.state/'data-index.json')
    output=args.data_root/through
    if not (output/'manifest.json').exists():
        if current:
            # Reuse immutable whole-market daily captures; fetch only new days.
            previous=Path(current['path'])/'option_daily'
            for path in previous.glob('*'):
                dest=output/'option_daily'/path.name
                dest.parent.mkdir(parents=True,exist_ok=True)
                if not dest.exists(): os.link(path,dest)
        from scripts.prepare_v6_forward_data import prepare
        prepare(argparse.Namespace(source=args.source,release=args.release,anchor=args.anchor,
            output=output,through=through,env=args.env))
    return publish_data(output,args.release,args.anchor,args.state/'data-index.json')


def relay(args):
    public=args.state/'published'
    public.mkdir(parents=True,exist_ok=True)
    for name in ('status.json','refresh.json','activation.json','data-index.json'):
        source=args.state/name
        if source.exists(): save(public/name,read(source))
    database=args.state/'portfolio.sqlite3'
    if database.exists():
        temp=public/'portfolio.tmp'
        with sqlite3.connect(f'file:{database}?mode=ro',uri=True,timeout=30) as src, sqlite3.connect(temp) as dst:
            src.backup(dst)
        temp.replace(public/'portfolio.sqlite3')
    (public/'alert-spool').mkdir(exist_ok=True)
    for source in (args.state/'alert-spool').glob('*.json'):
        dest=public/'alert-spool'/source.name
        if dest.exists():
            if sha(dest)!=sha(source): raise ValueError('immutable relay event changed')
        else:
            save(dest,read(source))
    # rsync's normal temporary-file rename keeps partial JSON invisible.
    subprocess.run(['rsync','-az','--timeout=45','-e','ssh -o BatchMode=yes -o ConnectTimeout=10',
        str(public)+'/',args.remote],check=True,timeout=55)
    receipt={'status':'sent','at':utcnow().isoformat(),'events':len(list((public/'alert-spool').glob('*.json')))}
    save(args.state/'relay.json',receipt)
    return receipt


def access(args):
    """Read-only check of current SIP stock and MASSIVE option access."""
    import pandas as pd
    from dotenv import load_dotenv
    from nn_meta.live.v6_market import alpaca_bars, MassiveMarket
    from nn_meta.decision_contracts import DecisionContractSelector
    load_dotenv(args.env)
    now=utcnow()
    bars=alpaca_bars(['SPY'],now-pd.Timedelta(minutes=5),now,timeframe='1Min',adjustment='raw')
    if bars.empty: raise ValueError('fresh SPY reference stock unavailable')
    market=MassiveMarket(args.state/'market')
    contract=DecisionContractSelector(market).select('SPY',as_of=now.date(),right='C',
        raw_spot=float(bars.sort_values('timestamp').Close.iloc[-1]),target_dte=1)
    if contract is None: raise ValueError('SPY reference option unavailable')
    return market.verify_current_access(contract.symbol)


def held_quote_gap_only(status):
    """A held-position quote gap withholds entries but is not a process crash."""
    gaps = status.get('monitoring_gaps') or status.get('exit_errors') or []
    if not gaps:
        return False
    messages = [str(item.get('error', '')) for item in gaps if isinstance(item, dict)]
    return len(messages) == len(gaps) and all(
        message.endswith('no fresh post-decision option quote')
        or message.endswith('option quote is stale, crossed, empty or invalid')
        for message in messages)


def health(status,calendar,now):
    """Current-bar results are due six minutes after close, including 16:00."""
    import pandas as pd
    day=now.tz_convert('America/New_York').date().isoformat()
    bounds=calendar.bounds(day)
    if bounds is None: return {'status':'idle','reason':'non-session'}
    opening,closing=(value.tz_localize('UTC') for value in bounds)
    if now<opening+pd.Timedelta(minutes=21) or now>closing+pd.Timedelta(minutes=15):
        return {'status':'idle','reason':'outside monitoring window'}
    due=calendar.closed_starts(day,now-pd.Timedelta(minutes=6))
    if not len(due): return {'status':'idle','reason':'first result not due'}
    expected=due[-1].tz_localize('UTC')+pd.Timedelta(minutes=15)
    signal=pd.Timestamp(status.get('signal_clock')) if status.get('signal_clock') else None
    if signal is None or signal.tzinfo is None or signal<expected or status.get('replay'):
        return {'status':'failed','reason':'current paper pass missing','expected_close':expected.isoformat()}
    if status.get('status')=='failed' and held_quote_gap_only(status):
        return {'status':'degraded','reason':'held-position quote gap; new entries withheld',
                'expected_close':expected.isoformat()}
    if status.get('status')=='failed':
        return {'status':'failed','reason':status.get('error','paper pass failed'),'expected_close':expected.isoformat()}
    if signal<expected+pd.Timedelta(minutes=15) and status.get('phase')!='complete':
        return {'status':'failed','reason':'paper pass exceeded its deadline','expected_close':expected.isoformat()}
    return {'status':'healthy','expected_close':expected.isoformat()}


def watch(args):
    from dotenv import load_dotenv
    from nn_meta.session_calendar import SessionCalendar
    load_dotenv(args.env)
    now=utcnow()
    source=args.state/'incoming/status.json'
    status=read(source) if source.exists() else {}
    result=health(status,SessionCalendar(read(args.calendar)),now)
    result.update(checked_at=now.isoformat(),producer='home',delivery='server',broker_orders=False)
    # Delivery failures remain visible even when the producer is healthy.
    if result['status']!='idle' and args.queue.exists():
        with sqlite3.connect(args.queue) as db:
            tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'v6_notices' in tables:
                rows=db.execute("SELECT created_at FROM v6_notices WHERE status='pending'").fetchall()
                import pandas as pd
                if any((now-pd.Timestamp(row[0])).total_seconds()>300 for row in rows):
                    result.update(status='failed',reason='paper alerts pending delivery for over five minutes')
    previous=read(args.state/'health.json') if (args.state/'health.json').exists() else {}
    last=previous.get('last_notification_at')
    result['last_notification_at']=last
    if result['status']=='failed' and args.notify:
        import pandas as pd
        if last is None or (now-pd.Timestamp(last)).total_seconds()>=3600:
            from nn_meta.live.notifier import get_notifier
            title='[v6] Paper runtime needs attention'
            if get_notifier().send(f"{title}\n{result['reason']}\nNo new V6 entries are assumed; inspect the saved paper status.",title=title):
                result['last_notification_at']=now.isoformat()
    save(args.state/'health.json',result)
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action',choices=['refresh','relay','watch','publish-data','access'])
    ap.add_argument('--state',type=Path,required=True)
    ap.add_argument('--env',type=Path,default=ROOT/'.env')
    ap.add_argument('--release',type=Path)
    ap.add_argument('--anchor')
    ap.add_argument('--source',type=Path)
    ap.add_argument('--data-root',type=Path)
    ap.add_argument('--data',type=Path)
    ap.add_argument('--remote')
    ap.add_argument('--calendar',type=Path)
    ap.add_argument('--queue',type=Path)
    ap.add_argument('--notify',action='store_true')
    args=ap.parse_args()
    args.state.mkdir(parents=True,exist_ok=True)
    with (args.state/f'.{args.action}.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            if args.action=='publish-data':
                result=publish_data(args.data,args.release,args.anchor,args.state/'data-index.json')
            else: result=globals()[args.action](args)
            if args.action=='refresh': save(args.state/'refresh.json',{'status':'passed','at':utcnow().isoformat(),**result})
            print(json.dumps(result,sort_keys=True))
        except Exception as exc:
            save(args.state/f'{args.action}.json',{'status':'failed','at':utcnow().isoformat(),
                'error':f'{type(exc).__name__}: {exc}'})
            raise


if __name__=='__main__': main()
