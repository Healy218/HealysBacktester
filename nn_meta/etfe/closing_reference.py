"""Closing-auction exercise references: expiry-session windows and official-close extraction."""
import datetime as dt
from decimal import Decimal
import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from nn_meta.etfe import stock_trade_capture as t

ROOT=Path(__file__).resolve().parents[2]
CALENDAR=ROOT/'nn_meta/data_cache_etfe/alpaca-fresh-20261004-calendar-r1/000-calendar.body'
POLICY=ROOT/'nn_meta/validation/etfe-dated-policy-20261006-r0'
LISTING={'SPY':'P','VOO':'P','QQQ':'Q'}  # NYSE Arca / Nasdaq primary listing exchanges
BEFORE=pd.Timedelta(seconds=5)
AFTER=pd.Timedelta(seconds=30)


def sessions():
    """Session date -> regular close as an aware UTC timestamp (early closes included)."""
    body=json.loads(CALENDAR.read_bytes())
    return {dt.date.fromisoformat(r['date']):
            pd.Timestamp(f"{r['date']} {r['close']}",tz='America/New_York').tz_convert('UTC') for r in body}


def expiry_sessions():
    """(underlying, expiry session) pairs with admitted contracts inside the research calendar."""
    c=pq.read_table(POLICY/'CONTRACTS.parquet',columns=['underlying','expiration_date','status']).to_pandas()
    c=c[(c.status=='admitted')&c.expiration_date.notna()]
    closes=sessions();start=dt.date(2024,1,18)
    pairs=sorted({(u,e) for u,e in zip(c.underlying,c.expiration_date) if e>=start and e in closes})
    return pairs,closes


def window_job(symbol,close):
    params=dict(symbols=symbol,start=(close-BEFORE).isoformat(),end=(close+AFTER).isoformat(),
        feed='sip',asof='-',sort='asc',limit=10000)
    return t.job('stock_trades',params,'closing_auction_exercise_reference')


def prepare(root,probe_dates=None,year=None):
    pairs,closes=expiry_sessions()
    if probe_dates is not None:pairs=[p for p in pairs if p[1] in probe_dates]
    if year is not None:pairs=[p for p in pairs if p[1].year==year]
    jobs=[window_job(u,closes[e]) for u,e in pairs]
    parent=dict(policy_resolution_sha256=t.sha((POLICY/'RESOLUTION.json').read_bytes()),
        calendar_sha256=t.sha(CALENDAR.read_bytes()),expiry_sessions=len(pairs),
        window_seconds=[-BEFORE.total_seconds(),AFTER.total_seconds()],
        probe=probe_dates is not None,year=year)
    return t.prepare(root,jobs,parent=parent,max_total_requests=max(64,4*len(jobs)))


def official_close(symbol,rows):
    """Listing-exchange condition-M print, cross-checked against its condition-6 closing print."""
    venue=LISTING[symbol]
    m={(r['p'],r['s']) for r in rows if r['x']==venue and 'M' in r['c']}
    six={(r['p'],r['s']) for r in rows if r['x']==venue and '6' in r['c']}
    if not m:return dict(status='missing',price=None,reason='no_listing_official_close')
    prices={p for p,_ in m}
    if len(prices)>1:return dict(status='ambiguous',price=None,reason='conflicting_official_close')
    price=prices.pop()
    if six and price not in {p for p,_ in six}:
        return dict(status='ambiguous',price=None,reason='closing_print_disagrees')
    return dict(status='resolved',price=price,reason='official_close' if six else 'official_close_without_closing_print')


def exercise_outcome(right,strike,reference,threshold=0.01,pin_band=0.05):
    """OCC exercise-by-exception at $0.01 ITM per share; pins are reported, not excluded."""
    # Exact decimal cents: float subtraction would turn a $0.01 margin into 0.00999...
    ref,k=Decimal(str(reference)),Decimal(str(strike))
    itm=ref-k if right=='C' else k-ref
    return dict(exercised=itm>=Decimal(str(threshold)),intrinsic=float(max(itm,Decimal(0))),
        pin=abs(ref-k)<=Decimal(str(pin_band)))
