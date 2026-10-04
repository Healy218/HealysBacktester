"""Fresh phase-A calendar demand and bounded January option coverage census."""
from collections import Counter, defaultdict
from datetime import date, timedelta
import json
from pathlib import Path

import pandas as pd

from nn_meta.etfe.acquisition import (
    ROOT, SYMBOLS, committed, digest, iter_records, job, load_plan, prepare,
    save, sha, write_new,
)
from nn_meta.etfe.expansion import read_calendar
from nn_meta.etfe.purchase_policy_v2 import SCOPE, load_scope
from scripts.acquire_etfe_alpaca import interval
from scripts.prepare_etfe_0dte import verify as verify_setup

SOURCES = ('nn_meta/etfe/demand.py', 'scripts/etfe_demand.py',
           'docs/specs/ETFE_DEMAND_20261004.md',
           'docs/specs/ETFE_SCOPE_0DTE_20261004.json',
           'docs/specs/ETFE_FEATURE_MAP_20261003.json',
           'docs/specs/ETFE_FEATURES_20261003.md',
           'docs/specs/ETFE_EXECUTION_20261003.md')
JANUARY_START = '2024-01-01'
JANUARY_EXPIRY_END = '2024-03-04'
SURFACE_DAYS = ('2024-01-18', '2024-01-19')


def dates(start, end):
    a, b = date.fromisoformat(start), date.fromisoformat(end)
    return [(a + timedelta(days=i)).isoformat() for i in range((b-a).days+1)]


def discovery_job(ticker, expiry, status):
    return job('contracts', dict(underlying_symbols=ticker, status=status,
        expiration_date=expiry, show_deliverables='true', limit=1000),
        f'phase_a_discovery:{ticker}:{expiry}:{status}')


def query_key(item):
    return digest([item['route'], item['params']])


def source_hashes():
    return {n: sha((ROOT/n).read_bytes()) for n in SOURCES}


def snapshot(root):
    for n in SOURCES:
        p=Path(root)/'demand_source'/n
        p.parent.mkdir(parents=True, exist_ok=True)
        write_new(p, (ROOT/n).read_bytes())


def verified_inputs(roots):
    """Verify each complete page chain; index transport identity, not purpose."""
    inputs, inventory = [], {}
    for root in roots:
        root=Path(root).resolve(); plan=load_plan(root)
        if any(x['sha256']==plan['sha256'] for x in inputs):
            raise ValueError('Repeated input plan')
        inputs.append(dict(root=str(root), sha256=plan['sha256']))
        for item in plan['jobs']:
            _, _, complete = committed(root, item)
            if not complete:
                raise ValueError('Demand reuse requires complete input captures')
            key=query_key(item)
            if key in inventory:
                raise ValueError('Overlapping query vintages require an explicit selection')
            inventory[key]=dict(root=str(root), plan_sha256=plan['sha256'],
                                job_id=item['id'], item=item)
    return inputs, inventory


def calendar_demand(calendar):
    edges, physical = [], {}
    for session in calendar:
        day=session['date']; origin=date.fromisoformat(day)
        for ticker in SYMBOLS:
            expiry_edges=[]
            for dte in range(46):
                expiry=(origin+timedelta(days=dte)).isoformat()
                keys=[]
                for status in ('active','inactive'):
                    item=discovery_job(ticker, expiry, status); key=query_key(item)
                    physical[key]=item; keys.append(key)
                expiry_edges.append(dict(expiry=expiry, calendar_dte=dte,
                    purposes=(['purchase_discovery'] if dte<=5 else [])+
                             (['daily_context'] if dte>=1 else []), query_keys=keys))
            edges.append(dict(ticker=ticker, session=day, expiries=expiry_edges))
    return edges, physical


def build_inventory(root, calendar_root, setup_root, reuse_roots):
    calendar=read_calendar(calendar_root); setup=verify_setup(setup_root)
    inputs, reused=verified_inputs(reuse_roots)
    edges, physical=calendar_demand(calendar)
    queries={k:dict(item=item, disposition='captured' if k in reused else 'planned',
                   capture=reused.get(k)) for k,item in sorted(physical.items())}
    catalog=json.loads((Path(setup_root)/'catalog.json').read_text())
    report=dict(schema='etfe-calendar-demand-v1', sources=source_hashes(),
        scope=load_scope(), setup_sha256=setup['plan_sha256'],
        catalog_sha256=sha((Path(setup_root)/'catalog.json').read_bytes()),
        families=sorted(catalog['families']), ticker_variant_combinations=25353,
        calendar_root=str(Path(calendar_root).resolve()),
        calendar_sha256=sha((Path(calendar_root)/'CALENDAR.json').read_bytes()),
        inputs=inputs, session_edges=edges, queries=queries,
        collection_start=calendar[0]['date'], collection_end=calendar[-1]['date'],
        summary=dict(sessions=len(calendar), ticker_sessions=len(edges),
            logical_expiry_status_edges=len(edges)*46*2,
            physical_discovery_queries=len(queries), reused_queries=sum(k in reused for k in queries)),
        unresolved_frontiers=['pre_2024_history_and_exact_usable_start',
            'historical_listing_completeness_and_dated_terms_actions_option_hours',
            'phase_B_registered_signals_and_exact_feature_trade_windows',
            'phase_C_holding_roll_settlement_stock_quote_windows',
            'full_symbol_session_surface_inventory_after_discovery',
            'integrated_resource_and_recovery_pilot'],
        full_demand_complete=False, ready_for_build=False, ready_for_training=False)
    report['sha256']=digest(report)
    root=Path(root);root.mkdir(parents=True, exist_ok=False)
    save(root/'DEMAND.json',report);snapshot(root)
    return report


def load_inventory(root):
    root=Path(root); r=json.loads((root/'DEMAND.json').read_text())
    if digest({k:v for k,v in r.items() if k!='sha256'})!=r['sha256']:
        raise ValueError('Demand inventory changed')
    check_sources(root,r['sources'])
    if sha((Path(r['calendar_root'])/'CALENDAR.json').read_bytes())!=r['calendar_sha256']:
        raise ValueError('Demand calendar changed')
    for p in r['inputs']:
        if load_plan(p['root'])['sha256']!=p['sha256']:raise ValueError('Demand input changed')
    return r


def check_sources(root, sources):
    for n,h in sources.items():
        if sha((ROOT/n).read_bytes())!=h or sha((Path(root)/'demand_source'/n).read_bytes())!=h:
            raise ValueError('Demand source changed; successor required')


def prepare_capture(root, jobs, kind, inventory, **details):
    plan=prepare(root,jobs,parent=dict(kind=kind,demand_sha256=inventory['sha256'],
        sources=source_hashes(), **details))
    snapshot(root)
    return plan


def verify_capture(root):
    plan=load_plan(root);check_sources(root,plan['parent']['sources'])
    return plan


def january_discovery(inventory):
    jobs,reused=[],[]
    for ticker in SYMBOLS:
        for expiry in dates(JANUARY_START,JANUARY_EXPIRY_END):
            for status in ('active','inactive'):
                item=discovery_job(ticker,expiry,status);key=query_key(item)
                prior=inventory['queries'].get(key,{})
                if prior.get('disposition')=='captured':reused.append(prior['capture'])
                else:jobs.append(item)
    return jobs, dict(reused_discovery=reused)


def returned_contracts(roots):
    inputs, inventory=verified_inputs(roots)
    contracts={}; completed=set()
    for entry in inventory.values():
        item=entry['item'];p=item['params']
        if item['route']!='contracts':continue
        expiry=p['expiration_date'];ticker=p['underlying_symbols']
        if not JANUARY_START<=expiry<=JANUARY_EXPIRY_END:continue
        completed.add((ticker,expiry,p['status']))
        for row in iter_records(entry['root'],item):
            raw=row['raw']
            if raw['expiration_date']!=expiry:
                raise ValueError('Discovery expiry mismatch')
            symbol=row['symbol']
            value=dict(ticker=ticker,expiry=expiry,symbol=symbol,
                source=dict(root=entry['root'],plan_sha256=entry['plan_sha256'],
                    job_id=item['id'],**row['source']))
            if symbol in contracts:
                raise ValueError('Multiple current discovery records for one symbol')
            contracts[symbol]=value
    expected={(s,d,status) for s in SYMBOLS for d in dates(JANUARY_START,JANUARY_EXPIRY_END)
              for status in ('active','inactive')}
    if expected!=completed:
        raise ValueError('Incomplete January discovery grid')
    return inputs, contracts, inventory


def bars_job(symbols, start, end, purpose):
    return job('option_bars',dict(symbols=','.join(symbols),timeframe='1Min',
        sort='asc',limit=10000,**interval(start,end)),purpose)


def january_bars(roots, kind, calendar):
    inputs, contracts, inventory=returned_contracts(roots)
    if kind not in ('boundary','surfaces'):raise ValueError('Unknown January bar study')
    jobs, edges, reused=[],[],[]
    for ticker in SYMBOLS:
        for day in (('2024-01-01',) if kind=='boundary' else SURFACE_DAYS):
            end='2024-01-18' if kind=='boundary' else (date.fromisoformat(day)+timedelta(days=1)).isoformat()
            window=interval(day,end); covered={}
            for entry in inventory.values():
                item=entry['item'];p=item['params']
                if item['route']=='option_bars' and all(p[k]==v for k,v in window.items()):
                    for symbol in p['symbols'].split(','):
                        if symbol in covered:raise ValueError('Multiple bar vintages require explicit selection')
                        covered[symbol]=entry
            selected=sorted(s for s,c in contracts.items() if c['ticker']==ticker and
                (kind=='boundary' or 0<=(date.fromisoformat(c['expiry'])-date.fromisoformat(day)).days<=45))
            missing=[]
            for symbol in selected:
                c=contracts[symbol];dte=(date.fromisoformat(c['expiry'])-date.fromisoformat(day)).days
                edge=dict(symbol=symbol,ticker=ticker,day=day,expiry=c['expiry'],
                    discovery=c['source'],purposes=['history_diagnostic'] if kind=='boundary' else
                        (['purchase_discovery'] if dte<=5 else [])+(['daily_context'] if dte>=1 else []),
                    capture=covered.get(symbol))
                if symbol in covered:reused.append(dict(symbol=symbol,day=day,capture=covered[symbol]))
                else:missing.append(symbol)
                edges.append(edge)
            for offset in range(0,len(missing),100):
                jobs.append(bars_job(missing[offset:offset+100],day,end,
                    f'january_{kind}:{ticker}:{day}:{offset//100}'))
    physical={(s,j['params']['start']):j['id'] for j in jobs for s in j['params']['symbols'].split(',')}
    for edge in edges:
        if edge['capture'] is None:
            edge['job_id']=physical[(edge['symbol'],interval(edge['day'],
                '2024-01-18' if kind=='boundary' else
                (date.fromisoformat(edge['day'])+timedelta(days=1)).isoformat())['start'])]
    boundary_sessions=sum('2024-01-01'<=r['date']<'2024-01-18' for r in calendar)
    return jobs,dict(inputs=inputs,discovered_symbols=len(contracts),symbol_window_edges=edges,
        reused_symbol_windows=reused,minimum_gets=len(jobs),
        regular_minute_scenario_rows=sum(len(j['params']['symbols'].split(','))*390*
            (boundary_sessions if kind=='boundary' else 1) for j in jobs),
        estimate_boundary='Scenario only; absent bars and extended hours change pagination; no admission')


def coverage_report(root):
    plan=verify_capture(root);counts=Counter();first={};last={};daily=Counter();parts=[]
    for item in plan['jobs']:
        _,_,complete=committed(root,item)
        if not complete:raise ValueError('Coverage requires completed page chains')
        seen=Counter()
        for r in iter_records(root,item):
            s=r['symbol'];raw=r['raw'];counts[s]+=1;seen[s]+=1
            if 't' in raw:
                ns=pd.Timestamp(raw['t']).value
                first[s]=min(first.get(s,ns),ns);last[s]=max(last.get(s,ns),ns)
                daily[(s[:3],str(pd.Timestamp(ns,tz='UTC').tz_convert('America/New_York').date()))]+=1
        params=item['params']
        expected=params['symbols'].split(',') if item['route']!='contracts' else []
        parts.append(dict(job_id=item['id'],rows=sum(seen.values()),observed_symbols=len(seen),
            absent_symbols=[s for s in expected if not seen[s]],
            absence='empty_response_unresolved_not_no_trade'))
    by_ticker={}
    for ticker in SYMBOLS:
        stamps=[v for s,v in first.items() if s.startswith(ticker)]
        by_ticker[ticker]=dict(first_observed_utc=pd.Timestamp(min(stamps),tz='UTC').isoformat() if stamps else None,
                              verified_usable_start=None,complete_history=False)
    return dict(schema='etfe-january-coverage-v1',plan_sha256=plan['sha256'],
        rows=sum(counts.values()),symbols_observed=len(counts),partitions=parts,
        by_ticker=by_ticker,rows_by_ticker_day=[dict(ticker=t,day=d,rows=n) for (t,d),n in sorted(daily.items())],
        per_symbol=[dict(symbol=s,rows=n,first_ns=first.get(s),last_ns=last.get(s)) for s,n in sorted(counts.items())],
        complete_history=False,ready_for_build=False)
