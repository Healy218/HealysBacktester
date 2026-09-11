"""Read-only, bounded dashboard adapters. Never imports scanner or notifier code."""
from __future__ import annotations
import argparse
from contextlib import closing
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
from urllib.parse import quote
from zoneinfo import ZoneInfo

UTC=timezone.utc

def iso(value):
    if value is None:return None
    try:
        if isinstance(value,(float,int)): dt=datetime.fromtimestamp(value,UTC)
        else: dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        if dt.tzinfo is None:dt=dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC).isoformat()
    except (ValueError,TypeError,OverflowError):return None

def finite(value):
    try:
        n=float(value)
        return n if math.isfinite(n) else None
    except (ValueError,TypeError):return None

def read_json(path,limit=8_000_000):
    with Path(path).open('rb') as f:raw=f.read(limit+1)
    if len(raw)>limit:raise ValueError('Input exceeds size limit')
    return json.loads(raw)

def tail(path,limit=2_000_000):
    with Path(path).open('rb') as f:
        f.seek(0,2);size=f.tell();f.seek(max(0,size-limit));raw=f.read(limit)
    return raw.decode('utf-8',errors='replace').splitlines()[1:] if size>limit else raw.decode('utf-8',errors='replace').splitlines()

def scanner(path,name):
    # Completion prints have no timestamp. Preserve preceding timestamp as an
    # approximation and never replace it with capture time or logfile mtime.
    out=dict(id=name,observedAt=None,lastCompletionAt=None,scanned=None,queued=None,errors=None,filtered=None,note='No completion in bounded log tail',source=f'logs/{path.name}')
    timestamp=None;filtered=0
    for line in tail(path):
        m=re.match(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)(?:,\d+)?',line)
        if m:timestamp=iso(m[1]);out['observedAt']=timestamp
        if 'filtered (' in line:filtered+=1
        m=re.match(r'^\[v[45]\] scanned (\d+) · alerted (\d+) · delivered (\d+) · errors (\d+)',line)
        simple=line.startswith('No fresh signals this pass') or bool(re.match(r'^\d+ signal\(s\) alerted:',line))
        if m or simple:
            out.update(lastCompletionAt=timestamp,scanned=int(m[1]) if m else None,queued=int(m[3]) if m else (0 if line.startswith('No fresh') else None),errors=int(m[4]) if m else None,filtered=filtered if m else None,note='Completed; preceding log timestamp (UTC)')
            filtered=0
    return out

def market(calendar,now):
    try:
        cal=read_json(calendar);sessions=cal['sessions'];ny=now.astimezone(ZoneInfo('America/New_York'))
        dates=[s['date'] for s in sessions]
        if not dates or not min(dates)<=str(ny.date())<=max(dates):return 'unknown'
        session=next((s for s in sessions if s['date']==str(ny.date())),None)
        if session is None:return 'closed'
        return 'open' if session['open']<=ny.strftime('%H:%M')<session['close'] else 'closed'
    except (OSError,ValueError,KeyError,TypeError):return 'unknown'

def connect(path):
    db=sqlite3.connect(f'file:{quote(str(Path(path).resolve()))}?mode=ro',uri=True,timeout=2)
    db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON');db.execute('BEGIN')
    return db

def queue(db,now):
    start=now.astimezone(ZoneInfo('America/Chicago')).replace(hour=0,minute=0,second=0,microsecond=0).timestamp()
    # Batches represent candidate cohorts. There is no trustworthy send timestamp
    # in this schema, so never call this a count by delivery time.
    counts={r['status']:r['n'] for r in db.execute('SELECT status, COUNT(*) n FROM candidates WHERE batch>=? AND batch<=? GROUP BY status',(start,now.timestamp()))}
    rows=db.execute('SELECT key,trade_ref,symbol,side,expert,score,status,batch,trade_context FROM candidates WHERE batch>=? AND batch<=? ORDER BY batch DESC,key LIMIT 100',(start,now.timestamp())).fetchall()
    result=[]
    for r in rows:
        context=json.loads(r['trade_context'] or '{}')
        result.append(dict(id=r['trade_ref'] or hashlib.sha256(r['key'].encode()).hexdigest()[:12],symbol=r['symbol'] or 'Unknown',side=r['side'] or 'Unknown',expert=r['expert'],score=finite(r['score']),status=r['status'],candidateAt=iso(r['batch']),strategy=str(context.get('strategy','')),source='alert queue / candidates'))
    return counts,result

def positions(db,quotes):
    rows=db.execute('SELECT * FROM taken_trades ORDER BY taken_at DESC LIMIT 100').fetchall();out=[]
    for r in rows:
        context=json.loads(r['context']);contract=str(context.get('contract','Unknown'));q=quotes.get(contract.removeprefix('O:'),{})
        sales=db.execute('SELECT quantity,premium,fees FROM taken_sales WHERE trade_id=? ORDER BY update_id',(r['id'],)).fetchall()
        sold=sum(s['quantity'] for s in sales);gross=net=None
        if sales and r['quantity'] and r['fill_price'] is not None:
            gross=sum((Decimal(s['premium'])-Decimal(str(r['fill_price'])))*s['quantity']*100 for s in sales)
            if r['actual_entry_fees'] is not None and all(s['fees'] is not None for s in sales):
                net=gross-Decimal(r['actual_entry_fees'])*sold/r['quantity']-sum(Decimal(s['fees']) for s in sales)
        bid,ask=finite(q.get('bid')),finite(q.get('ask'))
        if bid is None or ask is None or bid<0 or ask<bid:bid=ask=None
        out.append(dict(id=r['id'],symbol=str(context.get('symbol','Unknown')),contract=contract,status=r['status'],quantity=r['quantity'],remaining=None if r['quantity'] is None else r['quantity']-sold,entry=finite(r['fill_price']),realizedGross=finite(gross),realizedNet=finite(net),bid=bid,ask=ask,quoteAt=iso(q.get('ts')),takenAt=iso(r['taken_at']),checkedAt=iso(r['last_checked']),exitNotice=str(r['exit_notice'])[:1500] if r['exit_notice'] else None,monitorError=str(r['monitor_error'])[:250] if r['monitor_error'] else None))
    return out

def collect_server(root,now=None):
    root=Path(root);now=now or datetime.now(UTC);issues=[]
    out=dict(schemaVersion=1,source='server',observedAt=now.isoformat(),market=market(root/'nn_meta/live/exchange_calendar.json',now),scanners=[],feeds=[],signals=[],positions=[],queueCounts={},queueAvailable=False,positionsAvailable=False,openPositionCount=None,scope='Counts cover today’s Chicago candidate cohorts; table shows the newest 100. Candidate time is not send time.',issues=issues)
    for name,filename in [('v3','live_cron.log'),('v31','v31_cron.log'),('v4','v4_cron.log'),('v5','v5_cron.log')]:
        try:out['scanners'].append(scanner(root/'logs'/filename,name))
        except (OSError,ValueError):issues.append(f'{name}: scanner log unavailable')
    for name,prefix in [('stocks','stock'),('options','option')]:
        path=root/f'nn_meta/live/feeds/data/{prefix}_stream.heartbeat.json'
        try:
            hb=read_json(path);out['feeds'].append(dict(id=name,observedAt=iso(hb.get('ts')),state=str(hb.get('state','running')),count=finite(hb.get('symbols' if name=='stocks' else 'contracts')),lastBar=iso(hb.get('last_bar')),source=f'{prefix}_stream.heartbeat.json'))
        except (OSError,ValueError,TypeError):issues.append(f'{name}: heartbeat unavailable')
    try:quotes=read_json(root/'nn_meta/live/feeds/data/option_quotes.json')
    except (OSError,ValueError):quotes={}
    try:
        with closing(connect(root/'nn_meta/live/.alert_batches.sqlite3')) as db:
            try:out['queueCounts'],out['signals']=queue(db,now);out['queueAvailable']=True
            except (sqlite3.Error,ValueError,KeyError):issues.append('Alert queue schema or contents unavailable')
            try:
                out['positions']=positions(db,quotes);out['positionsAvailable']=True
                out['openPositionCount']=db.execute("SELECT COUNT(*) FROM taken_trades WHERE status IN ('open','exit_due')").fetchone()[0]
            except (sqlite3.Error,ValueError,KeyError):issues.append('Position accounting unavailable')
    except sqlite3.Error:issues.append('Alert database unavailable')
    return out

def collect_home(root,progress=None,now=None):
    root=Path(root);now=now or datetime.now(UTC);issues=[]
    out=dict(schemaVersion=1,source='home',observedAt=now.isoformat(),jobs=[],fa=dict(cutoff=None,symbols=None,uniqueNews=None,coverage={},rows=[],evaluationStatus='unavailable',labeledRows=None),research=None,issues=issues)
    for path in sorted((root/'logs/job-health').glob('*/latest.json'))[:100]:
        try:
            j=read_json(path);out['jobs'].append(dict(id=j['job'],state=j['state'],observedAt=iso(j['updated']),source=f'job-health/{path.parent.name}/latest.json'))
        except (OSError,ValueError,KeyError):issues.append('Invalid job receipt')
    snapshots=sorted((root/'fa/artifacts/enrichment').glob('20*T*Z/manifest.json'))
    if snapshots:
        try:
            import pandas as pd
            path=snapshots[-1];m=read_json(path);file=path.parent/'features.parquet'
            if hashlib.sha256(file.read_bytes()).hexdigest()!=m['files']['features.parquet']:raise ValueError('Snapshot hash mismatch')
            df=pd.read_parquet(file)
            if len(df)>400 or df.ticker.duplicated().any():raise ValueError('Invalid FA rows')
            out['fa'].update(cutoff=iso(m['cutoff']),symbols=m['symbols'],uniqueNews=m['unique_news'],coverage=m['coverage'],rows=[dict(ticker=r['ticker'],sentiment=finite(r.get('sentiment_mean_7d')),newsCount=finite(r.get('news_count_7d')),revenueGrowth=finite(r.get('revenue_yoy')),shortInterest=finite(r.get('short_interest')),floatPercent=finite(r.get('free_float_percent'))) for r in df.to_dict('records')])
        except (OSError,ValueError,KeyError,ImportError):issues.append('FA snapshot unavailable or failed integrity check')
    else:issues.append('No FA feature snapshot found')
    reports=sorted((root/'fa/artifacts/enrichment_reports').glob('20*T*Z.json'))
    if reports:
        try:
            report=read_json(reports[-1]);out['fa'].update(evaluationStatus=report['status'],labeledRows=report['labeled_rows'])
        except (OSError,ValueError,KeyError):issues.append('FA evaluation report unavailable')
    if progress:
        try:
            p=read_json(progress);out['research']=dict(campaign=p['campaign'],observedAt=iso(p['time_utc']),counts={k:v for k,v in p['counts'].items() if finite(v) is not None},totalSymbols=finite(p['total_symbols']),stages=sorted({x['stage'] for x in p['processes']}),evidence=p['evidence_present'])
        except (OSError,ValueError,KeyError):issues.append('Configured campaign receipt unavailable')
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',choices=['server','home']);p.add_argument('--root',required=True,type=Path);p.add_argument('--progress',type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();data=collect_server(a.root) if a.source=='server' else collect_home(a.root,a.progress)
    a.output.parent.mkdir(parents=True,exist_ok=True);tmp=a.output.with_suffix('.tmp');tmp.write_text(json.dumps(data,allow_nan=False));tmp.chmod(0o600);tmp.replace(a.output)
    print(json.dumps({'source':a.source,'observedAt':data['observedAt'],'issues':data['issues']}))
if __name__=='__main__':main()
