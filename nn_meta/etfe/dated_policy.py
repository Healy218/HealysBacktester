"""ETFE-0 dated-input policy v1: contract economics/availability, settlement, actions, VOO rewarm.

Decisions are user-selected on 2026-10-06 (see docs/specs/ETFE_DATED_INPUT_POLICY_20261006.md).
Every resolution is derived from fresh, hash-bound ETFE roots; nothing is backfilled.
"""
import datetime as dt
import glob
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from nn_meta.etfe import acquisition as a

ROOT=Path(__file__).resolve().parents[2]
CACHE=ROOT/'nn_meta/data_cache_etfe'
SCHEMA='etfe-dated-input-policy-v1'
UNDERLYINGS=('SPY','QQQ','VOO')
OCC=re.compile(r'^(SPY|QQQ|VOO)(\d{6})([CP])(\d{8})$')
RESEARCH_START_NS=pd.Timestamp('2024-01-18T14:30:00Z').value
T1_FIRST_TRADE_DATE=dt.date(2024,5,28)
BAR_NS=60_000_000_000
# Provider settlement dates that differ from the regulatory business-day rule, with cause.
SETTLEMENT_EXCEPTIONS={'2025-01-08':'NYSE closed 2025-01-09 (national day of mourning); banks/DTC settled'}
QQQ_PAYABLE_OVERRIDE=('QQQ','2024-03-18')

SOURCES=dict(
    census=ROOT/'nn_meta/validation/etfe-full-coverage-20261005-r0',
    calendar=CACHE/'alpaca-fresh-20261004-calendar-r1',
    announcements=CACHE/'alpaca-fresh-full-announcements-20261006-r1',
    issuer=CACHE/'issuer-fresh-invesco-20261006-r0',
    window_checks=CACHE/'alpaca-fresh-window-checks-20261006-r0')
OPTION_ROOTS=('normalized-20261004-january-boundary-r0','normalized-20261004-january-surfaces-r0',
    'normalized-20261004-main-r0','normalized-20261004-strata-r0','normalized-20261004-trade-windows-r0',
    'normalized-20261006-exact-options-r0')


def resolve_contract(symbol,multiplier_raw,size_raw,deliverables):
    """Economics from the deliverable for standard OCC symbols; anything else is excluded."""
    m=OCC.match(symbol)
    if not m:return dict(status='excluded',reason='nonstandard_symbol',multiplier=None,deliverable_shares=None)
    if len(deliverables)!=1:return dict(status='excluded',reason='multi_deliverable',multiplier=None,deliverable_shares=None)
    d=deliverables[0]
    if (d.get('type')!='equity' or d.get('symbol')!=m.group(1) or d.get('amount')!='100'
            or d.get('allocation_percentage')!='100' or size_raw!='100'):
        return dict(status='excluded',reason='nonstandard_deliverable',multiplier=None,deliverable_shares=None)
    if multiplier_raw=='100':reason='standard'
    elif multiplier_raw=='0':reason='deliverable_override_zero_multiplier'
    else:return dict(status='excluded',reason='multiplier_conflict',multiplier=None,deliverable_shares=None)
    return dict(status='admitted',reason=reason,multiplier=100,deliverable_shares=100)


def regulatory_settlement_days(trade_date):
    return 2 if trade_date<T1_FIRST_TRADE_DATE else 1


def bank_holidays(year):
    """Fed holidays on which NYSE is open: Columbus Day and Veterans Day (Sunday -> Monday)."""
    columbus=[dt.date(year,10,d) for d in range(1,15) if dt.date(year,10,d).weekday()==0][1]
    veterans=dt.date(year,11,11)
    if veterans.weekday()==6:veterans+=dt.timedelta(1)
    return {columbus} if veterans.weekday()==5 else {columbus,veterans}


def regulatory_settlement(trade_date,trading_days):
    """Independent rule: Nth settlement day after the trade, skipping market and bank holidays."""
    holidays=set().union(*(bank_holidays(y) for y in {trade_date.year,trade_date.year+1}))
    later=[d for d in trading_days if d>trade_date and d not in holidays]
    n=regulatory_settlement_days(trade_date)
    return later[n-1] if len(later)>=n else None


def known_from_session(declaration_date,trading_days):
    """First trading session strictly after the declaration date."""
    later=[d for d in trading_days if d>declaration_date]
    return later[0] if later else None


def contract_available(first_available_ns,decision_ns):
    return first_available_ns is not None and first_available_ns<=decision_ns


def rewarm_mask(bar_ns,gap_ns,warmup_bars):
    """True for bars excluded while a recursive indicator re-warms after a missing minute.

    The first `warmup_bars` observed bars after each gap are excluded; nothing is filled.
    """
    bar_ns=np.asarray(bar_ns,dtype=np.int64);mask=np.zeros(len(bar_ns),dtype=bool)
    for g in gap_ns:
        start=int(np.searchsorted(bar_ns,g,side='right'))
        mask[start:start+warmup_bars]=True
    return mask


def read_calendar():
    body=json.loads((SOURCES['calendar']/'000-calendar.body').read_bytes())
    return [(dt.date.fromisoformat(r['date']),dt.date.fromisoformat(r['settlement_date'])) for r in body]


def census_contracts():
    cols=['symbol','underlying','expiration_date','right','strike','status','multiplier_raw','size_raw','deliverables_json']
    parts=sorted(glob.glob(str(SOURCES['census']/'partitions/*.parquet')))
    df=pd.concat([pq.read_table(f,columns=cols).to_pandas() for f in parts],ignore_index=True)
    if df.symbol.duplicated().any():raise ValueError('Census symbol duplicated')
    return df


def first_available():
    """Earliest observation availability per symbol: bar start + 1 minute, trade timestamp."""
    first=defaultdict(lambda:[None,None])
    def note(symbols,stamps,slot):
        s=pd.DataFrame(dict(symbol=symbols,t=stamps)).groupby('symbol').t.min()
        for sym,t in s.items():
            cur=first[sym][slot];first[sym][slot]=int(t) if cur is None else min(cur,int(t))
    for name in OPTION_ROOTS:
        root=CACHE/name
        for meta_path in sorted((root/'partitions').glob('*.json')):
            meta=json.loads(meta_path.read_text())
            if meta['route'] not in ('option_bars','option_trades') or not meta['rows']:continue
            data=root/meta['data']
            if a.sha(data.read_bytes())!=meta['data_sha256']:raise ValueError(f'Hash mismatch {data}')
            t=pq.read_table(data,columns=['symbol','timestamp_ns']).to_pandas()
            bars=meta['route']=='option_bars'
            note(t.symbol,t.timestamp_ns+(BAR_NS if bars else 0),0 if bars else 1)
    pilot=a.load_plan(SOURCES['window_checks'])
    for item in pilot['jobs']:
        if item['route'] not in ('option_bars','option_trades'):continue
        history,_,complete=a.committed(SOURCES['window_checks'],item)
        if not complete:raise ValueError('Incomplete pilot job')
        bars=item['route']=='option_bars';syms=[];stamps=[]
        for _,body,_ in history:
            for sym,row in a.rows(body,item):
                syms.append(sym);stamps.append(pd.Timestamp(row['t']).value+(BAR_NS if bars else 0))
        if syms:note(syms,stamps,0 if bars else 1)
    return first


def resolve_actions(trading_days):
    rec=json.loads((SOURCES['announcements']/'RECONCILIATION.json').read_text())
    issuer=json.loads((SOURCES['issuer']/'QQQ_RESOLUTION.json').read_text())
    out=[]
    for r in rec['records']:
        raw=json.loads(r['raw_json']);decl=dt.date.fromisoformat(r['declaration_date'])
        payable=raw['payable_date'];source='announcement'
        if (r['symbol'],r['ex_date'])==QQQ_PAYABLE_OVERRIDE:
            payable=issuer['resolved_payable_date'];source='issuer_invesco_retrospective'
        known=known_from_session(decl,trading_days)
        out.append(dict(symbol=r['symbol'],ca_type=raw['ca_type'],cash=raw['cash'],
            declaration_date=r['declaration_date'],ex_date=r['ex_date'],record_date=raw['record_date'],
            payable_date=payable,payable_source=source,announcement_payable_date=raw['payable_date'],
            known_from_session=None if known is None else known.isoformat(),
            known_before_ex_date=known is not None and known<=dt.date.fromisoformat(r['ex_date']),
            revisions_modeled=False))
    return sorted(out,key=lambda x:(x['ex_date'],x['symbol']))


def voo_gaps():
    audit=json.loads((SOURCES['window_checks']/'WINDOW_CHECK_AUDIT.json').read_text())
    gaps=sorted(pd.Timestamp(g['timestamp']).value for g in audit['gap_results'] if not g['exact_minute_returned'])
    if len(gaps)!=audit['voo_missing_minutes_rechecked']:raise ValueError('Gap census mismatch')
    return gaps


def source_hashes():
    files=[SOURCES['census']/'CENSUS.json',SOURCES['census']/'INDEPENDENT_AUDIT.json',
        SOURCES['calendar']/'000-calendar.body',SOURCES['announcements']/'RECONCILIATION.json',
        SOURCES['issuer']/'QQQ_RESOLUTION.json',SOURCES['window_checks']/'WINDOW_CHECK_AUDIT.json',
        SOURCES['window_checks']/'PLAN.json']+[CACHE/n/'PLAN.json' for n in OPTION_ROOTS]
    return {str(p.relative_to(ROOT)):a.sha(p.read_bytes()) for p in files}


def build(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    calendar=read_calendar();trading_days=[d for d,_ in calendar];provider=dict(calendar)
    contracts=census_contracts();first=first_available()
    rows=[];reasons=defaultdict(int)
    for r in contracts.itertuples(index=False):
        res=resolve_contract(r.symbol,r.multiplier_raw,r.size_raw,json.loads(r.deliverables_json))
        reasons[res['reason']]+=1
        exp=r.expiration_date;settle=provider.get(exp) if exp is not None else None
        bar,trade=first.get(r.symbol,(None,None))
        avail=min([x for x in (bar,trade) if x is not None],default=None)
        rows.append(dict(symbol=r.symbol,underlying=r.underlying,expiration_date=exp,right=r.right,
            strike=r.strike,status=res['status'],reason=res['reason'],multiplier=res['multiplier'],
            deliverable_shares=res['deliverable_shares'],
            exercise_settlement_date=settle,settlement_source='alpaca_calendar' if settle else 'outside_calendar',
            first_bar_available_ns=bar,first_trade_ns=trade,first_available_ns=avail))
    table=pa.Table.from_pylist(rows)
    pq.write_table(table,out/'CONTRACTS.parquet')
    mism=[]
    for d,s in calendar:
        rule=regulatory_settlement(d,trading_days)
        if rule!=s and not (rule is None and d==trading_days[-1]):mism.append([d.isoformat(),s.isoformat(),None if rule is None else rule.isoformat()])
    if sorted(m[0] for m in mism)!=sorted(SETTLEMENT_EXCEPTIONS):raise ValueError(f'Undeclared settlement mismatch {mism}')
    actions=resolve_actions(trading_days);gaps=voo_gaps()
    a.save(out/'ACTIONS.json',actions)
    a.save(out/'VOO_GAPS.json',dict(gap_ns=gaps,gap_utc=[pd.Timestamp(g,tz='UTC').isoformat() for g in gaps],
        rule='recursive indicators re-warm for their declared warmup bars after each gap; excluded, not filled'))
    admitted=[x for x in rows if x['status']=='admitted']
    summary=dict(schema=SCHEMA,policy_spec='docs/specs/ETFE_DATED_INPUT_POLICY_20261006.md',
        research_start_utc=pd.Timestamp(RESEARCH_START_NS,tz='UTC').isoformat(),
        contracts=len(rows),admitted=len(admitted),reasons=dict(reasons),
        admitted_with_observation=sum(x['first_available_ns'] is not None for x in admitted),
        admitted_outside_settlement_calendar=sum(x['exercise_settlement_date'] is None for x in admitted),
        settlement_rule_mismatches=mism,settlement_exceptions=SETTLEMENT_EXCEPTIONS,
        actions=len(actions),actions_known_before_ex=sum(x['known_before_ex_date'] for x in actions),
        voo_gaps=len(gaps),contracts_sha256=a.sha((out/'CONTRACTS.parquet').read_bytes()),
        sources=source_hashes(),
        open_items=['official exercise reference price','SIP quote size representation',
            'historical publication/corrections (P1)','dated class hours/eligibility (R1/R2)',
            'action revision timelines'],
        ready_for_build=False,ready_for_training=False)
    a.save(out/'RESOLUTION.json',summary)
    return summary
