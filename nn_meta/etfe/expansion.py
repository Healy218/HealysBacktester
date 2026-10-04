"""Bounded fresh stock-history and 0–5 DTE option-stratum acquisition plans."""
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import pandas as pd

from nn_meta.etfe.acquisition import ROOT, SYMBOLS, audit, iter_records, job, load_plan, prepare, save, sha, write_new
from nn_meta.etfe.alpaca_probe import ReadOnlyProbe
from nn_meta.etfe.purchase_policy_v2 import SCOPE, load_scope
from scripts.acquire_etfe_alpaca import interval

STRATA = ('2024-11-29','2025-04-04')
SOURCES = ('nn_meta/etfe/expansion.py','scripts/expand_etfe_alpaca.py',
    'nn_meta/etfe/purchase_policy_v2.py','docs/specs/ETFE_SCOPE_0DTE_20261004.json',
    'docs/specs/ETFE_0DTE_NORMALIZATION_20261004.md')


def capture_calendar(root, credentials):
    client = ReadOnlyProbe(root, credentials, max_requests=1)
    receipt, body = client.get('calendar', dict(start='2024-01-01',end='2026-10-02'))
    if receipt['status_code'] != 200 or receipt['transport_error']:
        raise RuntimeError('Fresh calendar capture failed; raw failure retained')
    validate_calendar(body)
    report = dict(schema='etfe-alpaca-stock-calendar-v1', fetched_at=datetime.now(timezone.utc).isoformat(),
        start='2024-01-01',end='2026-10-02',rows=len(body),source='Alpaca stock calendar; not option hours',
        files={p.name:sha(p.read_bytes()) for p in Path(root).iterdir() if p.is_file()},
        sources={n:sha((ROOT/n).read_bytes()) for n in SOURCES})
    save(Path(root)/'CALENDAR.json', report)
    return report


def validate_calendar(body):
    if not isinstance(body,list) or not body:
        raise ValueError('Nonempty stock calendar required')
    dates = []
    for row in body:
        day = row['date']
        opened = pd.Timestamp(day+' '+row['open'],tz='America/New_York')
        closed = pd.Timestamp(day+' '+row['close'],tz='America/New_York')
        if not opened < closed or not '2024-01-01' <= day <= '2026-10-02':
            raise ValueError('Invalid stock calendar interval')
        dates.append(day)
    if dates != sorted(set(dates)) or dates[-1]!='2026-10-02':
        raise ValueError('Calendar date census invalid')


def read_calendar(root):
    root=Path(root)
    report=json.loads((root/'CALENDAR.json').read_text())
    for name,digest in report['files'].items():
        if sha((root/name).read_bytes()) != digest:
            raise ValueError('Calendar checksum mismatch')
    receipt=json.loads((root/'000-calendar.json').read_text())
    if receipt['status_code']!=200 or receipt['params']!={'start':'2024-01-01','end':'2026-10-02'}:
        raise ValueError('Calendar query identity mismatch')
    body=json.loads((root/receipt['body_path']).read_text())
    if sha((root/receipt['body_path']).read_bytes()) != receipt['body_sha256']:
        raise ValueError('Calendar body mismatch')
    validate_calendar(body)
    return body


def prepare_expansion(root, jobs, kind, **details):
    sources={n:sha((ROOT/n).read_bytes()) for n in SOURCES}
    parent=dict(kind=kind,scope_sha256=sha(SCOPE.read_bytes()),scope=load_scope(),sources=sources,**details)
    plan=prepare(root,jobs,parent=parent)
    for name in SOURCES:
        path=Path(root)/'expansion_source'/name
        path.parent.mkdir(parents=True,exist_ok=True)
        write_new(path,(ROOT/name).read_bytes())
    return plan


def verify_expansion(root):
    plan=load_plan(root)
    for name,digest in plan['parent']['sources'].items():
        if sha((Path(root)/'expansion_source'/name).read_bytes())!=digest or sha((ROOT/name).read_bytes())!=digest:
            raise ValueError('Expansion source mismatch')
    return plan


def stock_jobs():
    edges=pd.date_range('2024-02-01','2026-10-01',freq='MS')
    return [job('stock_bars',dict(symbols=ticker,timeframe='1Min',feed='sip',adjustment='raw',
        asof='-',sort='asc',limit=10000,**interval(str(a.date()),str(b.date()))),
        f'expanded_stock:{ticker}:{a.date()}')
        for ticker in SYMBOLS for a,b in zip(edges[:-1],edges[1:])]


def discovery_jobs(calendar):
    expiries=sorted({r['date'] for r in calendar for day in STRATA
        if 0 <= (pd.Timestamp(r['date'])-pd.Timestamp(day)).days <= 5})
    return [job('contracts',dict(underlying_symbols=ticker,status=status,expiration_date=expiry,
            show_deliverables='true',limit=1000),f'expanded_discovery:{ticker}:{expiry}:{status}')
        for ticker in SYMBOLS for expiry in expiries for status in ('active','inactive')]


def option_jobs(stock_root, discovery_root):
    stocks,discovery=load_plan(stock_root),load_plan(discovery_root)
    for root in (stock_root,discovery_root):
        if not audit(root)['capture_complete']:
            raise ValueError('Expanded parent captures must be complete')
    jobs,selections,missing=[],[],[]
    for ticker in SYMBOLS:
        for day in STRATA:
            opened=pd.Timestamp(day+' 09:30',tz='America/New_York').tz_convert('UTC')
            item=next(j for j in stocks['jobs'] if j['route']=='stock_bars' and
                j['params']['symbols']==ticker and pd.Timestamp(j['params']['start'])<=opened<=pd.Timestamp(j['params']['end']))
            spot_row=next((r for r in iter_records(stock_root,item) if pd.Timestamp(r['raw']['t'])==opened),None)
            if spot_row is None:
                raise ValueError(f'Missing stock opening bar {ticker}/{day}')
            spot=Decimal(str(spot_row['raw']['o']))
            candidates={}
            for item in discovery['jobs']:
                p=item['params']
                if p['underlying_symbols']==ticker and 0<=(pd.Timestamp(p['expiration_date'])-pd.Timestamp(day)).days<=5:
                    for r in iter_records(discovery_root,item):
                        if r['symbol'] in candidates and candidates[r['symbol']]['raw']!=r['raw']:
                            raise ValueError('Conflicting discovery records')
                        candidates[r['symbol']]=r
            selected=set()
            for target in (0,1,5):
                for right in ('call','put'):
                    choices=[r for r in candidates.values() if r['raw']['type']==right]
                    if not choices:
                        missing.append(dict(ticker=ticker,day=day,target=target,right=right,reason='no_returned_0_to_5_DTE_contract'))
                        continue
                    def rank(r):
                        row=r['raw']; dte=(pd.Timestamp(row['expiration_date'])-pd.Timestamp(day)).days
                        return (abs(dte-target),row['expiration_date'],abs(Decimal(row['strike_price'])-spot),Decimal(row['strike_price']),r['symbol'])
                    picked=min(choices,key=rank)
                    selected.add(picked['symbol'])
                    selections.append(dict(ticker=ticker,day=day,target=target,right=right,symbol=picked['symbol'],
                        actual_dte=(pd.Timestamp(picked['raw']['expiration_date'])-pd.Timestamp(day)).days,
                        use='transport_stratum_not_strategy_eligibility',stock_source=spot_row['source'],discovery_source=picked['source']))
            if not selected:
                continue
            params=dict(symbols=','.join(sorted(selected)),sort='asc',limit=10000)
            jobs.append(job('option_bars',dict(params,timeframe='1Min',**interval(day,str((pd.Timestamp(day)+pd.Timedelta(days=1)).date()))),f'expanded_option_bars:{ticker}:{day}'))
            jobs.append(job('option_trades',dict(params,start=opened.isoformat(),
                end=(opened+pd.Timedelta(minutes=30)-pd.Timedelta(1,'ns')).isoformat()),f'expanded_option_trades:{ticker}:{day}'))
    return jobs,dict(stock_plan=stocks['sha256'],discovery_plan=discovery['sha256'],selections=selections,missing_strata=missing)
